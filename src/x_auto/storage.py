"""Simple SQLite persistence layer.

Three append-only tables plus a schema-version table:

  metrics_history  — daily/hourly KPI snapshots per account
  trends_history   — each trend observation at a point in time
  incidents        — kill switch / rate limit / challenge events

No Alembic. Migrations are a plain list of SQL scripts applied in order;
``schema_version`` tracks which versions have been applied. New migrations
should be **appended** to the list — never reorder or mutate existing ones,
since that would corrupt databases in the wild.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from .analytics import AccountMetrics
from .trend_scout import Trend


# Each migration is a complete script applied under a single executescript call.
# Append-only — never edit existing entries.
MIGRATIONS: list[str] = [
    # v1 — metrics history
    """
    CREATE TABLE IF NOT EXISTS metrics_history (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        handle             TEXT NOT NULL,
        collected_at       TEXT NOT NULL,
        followers          INTEGER,
        following          INTEGER,
        verified_followers INTEGER,
        posts              INTEGER,
        UNIQUE(handle, collected_at)
    );
    CREATE INDEX IF NOT EXISTS idx_metrics_handle_time
        ON metrics_history(handle, collected_at);
    """,
    # v2 — trend observations
    """
    CREATE TABLE IF NOT EXISTS trends_history (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        collected_at TEXT NOT NULL,
        rank         INTEGER NOT NULL,
        word         TEXT NOT NULL,
        category     TEXT,
        post_count   INTEGER,
        source       TEXT NOT NULL DEFAULT 'x'
    );
    CREATE INDEX IF NOT EXISTS idx_trends_time
        ON trends_history(collected_at);
    CREATE INDEX IF NOT EXISTS idx_trends_word
        ON trends_history(word);
    """,
    # v3 — incidents
    """
    CREATE TABLE IF NOT EXISTS incidents (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        occurred_at    TEXT NOT NULL,
        account_handle TEXT,
        kind           TEXT NOT NULL,
        detail         TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_incidents_time
        ON incidents(occurred_at);
    CREATE INDEX IF NOT EXISTS idx_incidents_account
        ON incidents(account_handle);
    """,
]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MetricsRow:
    handle: str
    collected_at: str
    followers: int | None
    following: int | None
    verified_followers: int | None
    posts: int | None


class Storage:
    """Thin SQLite wrapper. One instance per database file."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    # ---- connection management ------------------------------------------

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        """Apply any pending migrations. Idempotent."""
        with self._conn() as conn:
            # Bootstrap schema_version independently of MIGRATIONS so the
            # version tracker itself is never subject to versioning.
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version    INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_version"
            ).fetchone()
            current = int(row[0])
            for version, sql in enumerate(MIGRATIONS, start=1):
                if version <= current:
                    continue
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (version, _utcnow_iso()),
                )

    def schema_version(self) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_version"
            ).fetchone()
            return int(row[0])

    # ---- metrics --------------------------------------------------------

    def record_metrics(self, metrics: AccountMetrics) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO metrics_history
                    (handle, collected_at, followers, following, verified_followers, posts)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    metrics.handle,
                    metrics.collected_at,
                    metrics.followers,
                    metrics.following,
                    metrics.verified_followers,
                    metrics.posts,
                ),
            )

    def latest_metrics(self, handle: str) -> MetricsRow | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT handle, collected_at, followers, following, verified_followers, posts
                FROM metrics_history
                WHERE handle = ?
                ORDER BY collected_at DESC
                LIMIT 1
                """,
                (handle,),
            ).fetchone()
            return _row_to_metrics(row)

    def previous_metrics(self, handle: str, before: str) -> MetricsRow | None:
        """Most recent snapshot strictly before ``before`` (ISO timestamp)."""
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT handle, collected_at, followers, following, verified_followers, posts
                FROM metrics_history
                WHERE handle = ? AND collected_at < ?
                ORDER BY collected_at DESC
                LIMIT 1
                """,
                (handle, before),
            ).fetchone()
            return _row_to_metrics(row)

    def metrics_history(self, handle: str, limit: int = 100) -> list[MetricsRow]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT handle, collected_at, followers, following, verified_followers, posts
                FROM metrics_history
                WHERE handle = ?
                ORDER BY collected_at DESC
                LIMIT ?
                """,
                (handle, limit),
            ).fetchall()
            return [_row_to_metrics(r) for r in rows if r is not None]  # type: ignore[list-item]

    # ---- trends ---------------------------------------------------------

    def record_trends(
        self,
        trends: Iterable[Trend],
        *,
        collected_at: str | None = None,
        source: str = "x",
    ) -> int:
        """Insert a batch of trend observations. Returns the number inserted."""
        ts = collected_at or _utcnow_iso()
        count = 0
        with self._conn() as conn:
            for t in trends:
                conn.execute(
                    """
                    INSERT INTO trends_history
                        (collected_at, rank, word, category, post_count, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (ts, t.rank, t.word, t.category, t.post_count, source),
                )
                count += 1
        return count

    def trends_in_range(
        self,
        since: str,
        until: str | None = None,
    ) -> list[dict[str, Any]]:
        until = until or _utcnow_iso()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT collected_at, rank, word, category, post_count, source
                FROM trends_history
                WHERE collected_at >= ? AND collected_at <= ?
                ORDER BY collected_at DESC, rank ASC
                """,
                (since, until),
            ).fetchall()
            return [dict(r) for r in rows]

    def top_trend_words(self, since: str, limit: int = 20) -> list[dict[str, Any]]:
        """Most-frequently-seen trend words since ``since``.

        Useful for answering "which words have been trending persistently?".
        """
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT word, COUNT(*) AS appearances, MIN(rank) AS best_rank
                FROM trends_history
                WHERE collected_at >= ?
                GROUP BY word
                ORDER BY appearances DESC, best_rank ASC
                LIMIT ?
                """,
                (since, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    # ---- incidents ------------------------------------------------------

    def record_incident(
        self,
        kind: str,
        *,
        account: str | None = None,
        detail: dict[str, Any] | None = None,
        occurred_at: str | None = None,
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO incidents (occurred_at, account_handle, kind, detail)
                VALUES (?, ?, ?, ?)
                """,
                (
                    occurred_at or _utcnow_iso(),
                    account,
                    kind,
                    json.dumps(detail, ensure_ascii=False) if detail else None,
                ),
            )
            return int(cur.lastrowid or 0)

    def recent_incidents(
        self,
        limit: int = 50,
        *,
        account: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._conn() as conn:
            if account:
                rows = conn.execute(
                    """
                    SELECT id, occurred_at, account_handle, kind, detail
                    FROM incidents
                    WHERE account_handle = ?
                    ORDER BY occurred_at DESC
                    LIMIT ?
                    """,
                    (account, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, occurred_at, account_handle, kind, detail
                    FROM incidents
                    ORDER BY occurred_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                if d.get("detail"):
                    try:
                        d["detail"] = json.loads(d["detail"])
                    except json.JSONDecodeError:
                        pass
                out.append(d)
            return out


def _row_to_metrics(row: sqlite3.Row | None) -> MetricsRow | None:
    if row is None:
        return None
    return MetricsRow(
        handle=row["handle"],
        collected_at=row["collected_at"],
        followers=row["followers"],
        following=row["following"],
        verified_followers=row["verified_followers"],
        posts=row["posts"],
    )
