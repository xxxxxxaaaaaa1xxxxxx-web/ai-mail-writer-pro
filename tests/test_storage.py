"""Tests for the SQLite persistence layer.

All tests operate on ephemeral DBs under ``tmp_path`` so there is no risk of
corrupting a developer's real state store.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from x_auto.analytics import AccountMetrics
from x_auto.storage import MIGRATIONS, Storage
from x_auto.trend_scout import Trend


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ---- schema / migrations ---------------------------------------------------


def test_fresh_db_applies_all_migrations(tmp_path: Path) -> None:
    db = tmp_path / "x.db"
    storage = Storage(db)
    assert storage.schema_version() == len(MIGRATIONS)

    # Sanity: the expected tables exist.
    with sqlite3.connect(db) as c:
        tables = {
            r[0]
            for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert "metrics_history" in tables
    assert "trends_history" in tables
    assert "incidents" in tables
    assert "schema_version" in tables


def test_reopen_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "x.db"
    Storage(db)
    Storage(db)
    Storage(db)
    # schema_version should have one row per migration, not 3x.
    with sqlite3.connect(db) as c:
        count = c.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
    assert count == len(MIGRATIONS)


# ---- metrics ---------------------------------------------------------------


def test_record_and_latest_metrics(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "x.db")
    m = AccountMetrics(
        handle="me",
        followers=100,
        following=50,
        verified_followers=10,
        posts=200,
        collected_at=_iso(datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)),
    )
    storage.record_metrics(m)

    latest = storage.latest_metrics("me")
    assert latest is not None
    assert latest.handle == "me"
    assert latest.followers == 100
    assert latest.verified_followers == 10

    assert storage.latest_metrics("nobody") is None


def test_record_metrics_idempotent_on_same_timestamp(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "x.db")
    ts = _iso(datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc))
    storage.record_metrics(
        AccountMetrics(handle="me", followers=100, collected_at=ts)
    )
    storage.record_metrics(
        AccountMetrics(handle="me", followers=150, collected_at=ts)
    )
    history = storage.metrics_history("me")
    assert len(history) == 1
    assert history[0].followers == 150  # REPLACE, not duplicate


def test_metrics_history_order(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "x.db")
    base = datetime(2026, 4, 10, tzinfo=timezone.utc)
    for i, f in enumerate([100, 110, 120, 130]):
        storage.record_metrics(
            AccountMetrics(
                handle="me",
                followers=f,
                collected_at=_iso(base + timedelta(hours=i)),
            )
        )
    history = storage.metrics_history("me", limit=10)
    assert [r.followers for r in history] == [130, 120, 110, 100]

    limited = storage.metrics_history("me", limit=2)
    assert [r.followers for r in limited] == [130, 120]


def test_previous_metrics_strictly_before(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "x.db")
    base = datetime(2026, 4, 10, tzinfo=timezone.utc)
    for i, f in enumerate([100, 110, 120]):
        storage.record_metrics(
            AccountMetrics(
                handle="me",
                followers=f,
                collected_at=_iso(base + timedelta(hours=i)),
            )
        )
    # "previous" for the last snapshot should be the middle one.
    current_ts = _iso(base + timedelta(hours=2))
    prev = storage.previous_metrics("me", before=current_ts)
    assert prev is not None
    assert prev.followers == 110

    # Before everything => None.
    oldest_ts = _iso(base - timedelta(days=1))
    assert storage.previous_metrics("me", before=oldest_ts) is None


# ---- trends ----------------------------------------------------------------


def test_record_and_query_trends(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "x.db")
    ts1 = _iso(datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc))
    ts2 = _iso(datetime(2026, 4, 10, 13, 0, tzinfo=timezone.utc))

    storage.record_trends(
        [
            Trend(rank=1, word="#入社式", post_count=12_000, category="日本"),
            Trend(rank=2, word="お花見", post_count=8_000),
        ],
        collected_at=ts1,
    )
    storage.record_trends(
        [
            Trend(rank=1, word="#入社式", post_count=15_000, category="日本"),
            Trend(rank=2, word="新学期", post_count=5_000),
        ],
        collected_at=ts2,
    )

    rows = storage.trends_in_range(since=ts1, until=ts2)
    assert len(rows) == 4
    # Default order: latest first, rank asc within.
    assert rows[0]["collected_at"] == ts2
    assert rows[0]["rank"] == 1


def test_top_trend_words(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "x.db")
    base = datetime(2026, 4, 10, tzinfo=timezone.utc)
    for i in range(3):
        storage.record_trends(
            [
                Trend(rank=1, word="persistent"),
                Trend(rank=5, word="one_hit" if i == 0 else "persistent"),
            ],
            collected_at=_iso(base + timedelta(hours=i)),
        )
    top = storage.top_trend_words(since=_iso(base - timedelta(days=1)), limit=5)
    by_word = {r["word"]: r for r in top}
    assert by_word["persistent"]["appearances"] == 5
    assert by_word["persistent"]["best_rank"] == 1
    assert by_word["one_hit"]["appearances"] == 1


# ---- incidents -------------------------------------------------------------


def test_record_and_list_incidents(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "x.db")
    storage.record_incident("manual_test", account="me", detail={"reason": "x"})
    storage.record_incident("rate_limit", account="other")
    storage.record_incident("shadow_ban_suspect", account="me")

    all_rows = storage.recent_incidents(limit=10)
    assert len(all_rows) == 3
    # Newest first.
    assert all_rows[0]["kind"] == "shadow_ban_suspect"

    me_rows = storage.recent_incidents(limit=10, account="me")
    assert len(me_rows) == 2
    assert {r["kind"] for r in me_rows} == {"manual_test", "shadow_ban_suspect"}


def test_incident_detail_json_roundtrip(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "x.db")
    storage.record_incident(
        "kill_switch",
        account="me",
        detail={"reason": "challenge detected", "selector": "iframe[title*=captcha]"},
    )
    rows = storage.recent_incidents(limit=1)
    assert rows[0]["detail"] == {
        "reason": "challenge detected",
        "selector": "iframe[title*=captcha]",
    }
