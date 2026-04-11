"""Command-line interface.

Commands:
    x-auto status                        — show kill switch + schedule state
    x-auto kill      --reason "..."      — trip the kill switch
    x-auto reset                         — clear the kill switch
    x-auto smoke     --account path.yml  — browser smoke test against example.com
    x-auto trends    --account path.yml  — fetch X trends via a scout account
    x-auto analytics --account path.yml  — fetch self-account KPIs
    x-auto history   --account path.yml  — show KPI time series from DB
    x-auto incidents [--account ...]     — show recent incidents from DB

``smoke`` hits example.com only.
``trends``, ``analytics`` hit X itself — use a dedicated scout account.

Every command that modifies state (``kill``, ``trends``, ``analytics``)
auto-records to the SQLite DB at ``--db`` (default ``./state/x_auto.db``).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .analytics import (
    DEFAULT_TTL_SECONDS as ANALYTICS_DEFAULT_TTL,
    AccountMetrics,
    ProfileMetricsScraper,
)
from .browser import BrowserSessionPool
from .config import AccountConfig
from .kill_switch import KillSwitch
from .schedule import is_active
from .storage import MetricsRow, Storage
from .trend_scout import DEFAULT_TTL_SECONDS, XTrendScout

DEFAULT_STATE = Path("./state/kill_switch.json")
DEFAULT_DB = Path("./state/x_auto.db")
DEFAULT_TRENDS_CACHE = Path("./state/trends")
DEFAULT_METRICS_CACHE = Path("./state/metrics")


def _storage(args: argparse.Namespace) -> Storage:
    return Storage(Path(args.db))


def _kill_switch(args: argparse.Namespace, storage: Storage | None = None) -> KillSwitch:
    callback = None
    if storage is not None:
        def callback(payload: dict[str, Any]) -> None:
            storage.record_incident(
                "kill_switch",
                account=payload.get("account"),
                detail=payload,
            )
    return KillSwitch(Path(args.state_file), on_trigger=callback)


# ---- status / kill / reset -------------------------------------------------


def cmd_status(args: argparse.Namespace) -> int:
    ks = _kill_switch(args)
    if ks.is_tripped():
        print("kill_switch: TRIPPED")
        state = ks.state() or {}
        for k, v in state.items():
            print(f"  {k}: {v}")
    else:
        print("kill_switch: ok")

    if args.account:
        account = AccountConfig.from_yaml(Path(args.account))
        now = datetime.now(ZoneInfo(account.timezone))
        active = is_active(
            account.circadian_start,
            account.circadian_end,
            account.timezone,
            now=now,
        )
        print(f"account: {account.handle}")
        print(f"  mode: {account.mode}  stage: {account.stage}")
        print(f"  tz: {account.timezone}  now: {now.isoformat(timespec='seconds')}")
        print(
            f"  quiet: [{account.circadian_start}, {account.circadian_end})  "
            f"active: {active}"
        )
    return 0


def cmd_kill(args: argparse.Namespace) -> int:
    storage = _storage(args)
    ks = _kill_switch(args, storage=storage)
    ks.trigger(reason=args.reason, account=args.account_handle)
    print(f"kill switch tripped: {args.reason}")
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    ks = _kill_switch(args)
    if not ks.is_tripped():
        print("kill switch was already clear")
        return 0
    ks.reset()
    print("kill switch cleared")
    return 0


# ---- smoke -----------------------------------------------------------------


async def _smoke(account_path: Path, state_file: Path) -> int:
    account = AccountConfig.from_yaml(account_path)
    ks = KillSwitch(state_file)
    if ks.is_tripped():
        print("refusing to run smoke: kill switch is tripped", file=sys.stderr)
        return 2
    pool = BrowserSessionPool(kill_switch=ks)
    try:
        session = await pool.get(account)
        await session.goto("https://example.com")
        title = await session.page.title()
        print(f"smoke ok: title={title!r}")
        return 0
    finally:
        await pool.close_all()


def cmd_smoke(args: argparse.Namespace) -> int:
    return asyncio.run(_smoke(Path(args.account), Path(args.state_file)))


# ---- trends ----------------------------------------------------------------


async def _trends(
    account_path: Path,
    state_file: Path,
    db_path: Path,
    cache_dir: Path,
    limit: int,
    ttl_seconds: int,
    force: bool,
) -> int:
    account = AccountConfig.from_yaml(account_path)
    storage = Storage(db_path)
    ks = KillSwitch(
        state_file,
        on_trigger=lambda p: storage.record_incident(
            "kill_switch", account=p.get("account"), detail=p
        ),
    )
    if ks.is_tripped():
        print("refusing to run trends: kill switch is tripped", file=sys.stderr)
        return 2

    pool = BrowserSessionPool(kill_switch=ks)
    try:
        session = await pool.get(account)
        scout = XTrendScout(session, cache_dir=cache_dir, ttl_seconds=ttl_seconds)
        trends = await scout.fetch(limit=limit, use_cache=not force)
        storage.record_trends(trends)
        for t in trends:
            count = f"  ({t.post_count:,} posts)" if t.post_count else ""
            cat = f"  [{t.category}]" if t.category else ""
            print(f"{t.rank:3d}. {t.word}{count}{cat}")
        return 0
    finally:
        await pool.close_all()


def cmd_trends(args: argparse.Namespace) -> int:
    return asyncio.run(
        _trends(
            account_path=Path(args.account),
            state_file=Path(args.state_file),
            db_path=Path(args.db),
            cache_dir=Path(args.cache_dir),
            limit=args.limit,
            ttl_seconds=args.ttl,
            force=args.force,
        )
    )


# ---- analytics -------------------------------------------------------------


_BAR_WIDTH = 33


def _progress_bar(ratio: float, width: int = _BAR_WIDTH) -> str:
    filled = int(round(ratio * width))
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def _delta_str(current: int | None, previous: int | None) -> str:
    if current is None or previous is None:
        return ""
    diff = current - previous
    if diff == 0:
        return "  (±0)"
    sign = "+" if diff > 0 else ""
    return f"  ({sign}{diff})"


def _render_metrics(
    m: AccountMetrics,
    previous: MetricsRow | None = None,
) -> str:
    lines = [f"@{m.handle}"]
    followers_str = str(m.followers) if m.followers is not None else "?"
    following_str = str(m.following) if m.following is not None else "?"
    lines.append(
        f"  followers:          {followers_str}"
        f"{_delta_str(m.followers, previous.followers if previous else None)}"
    )
    lines.append(
        f"  following:          {following_str}"
        f"{_delta_str(m.following, previous.following if previous else None)}"
    )

    target = m.premium_followers_target
    if m.verified_followers is not None:
        progress = m.premium_progress() or 0.0
        pct = progress * 100
        lines.append(
            f"  verified followers: {m.verified_followers} / {target}  ({pct:.1f}%)"
            f"{_delta_str(m.verified_followers, previous.verified_followers if previous else None)}"
        )
        lines.append(f"    {_progress_bar(progress)}")
    else:
        lines.append(f"  verified followers: ? / {target}")

    posts_str = str(m.posts) if m.posts is not None else "?"
    lines.append(
        f"  posts:              {posts_str}"
        f"{_delta_str(m.posts, previous.posts if previous else None)}"
    )

    ratio = m.follow_ratio()
    if ratio is not None:
        warn = "  ⚠ above 1.1 guard" if ratio > 1.1 else ""
        lines.append(f"  follow ratio:       {ratio:.2f}{warn}")

    if previous is not None:
        lines.append(f"  Δ since:            {previous.collected_at}")
    lines.append(f"  collected_at:       {m.collected_at}")
    return "\n".join(lines)


async def _analytics(
    account_path: Path,
    state_file: Path,
    db_path: Path,
    cache_dir: Path,
    ttl_seconds: int,
    force: bool,
) -> int:
    account = AccountConfig.from_yaml(account_path)
    storage = Storage(db_path)
    ks = KillSwitch(
        state_file,
        on_trigger=lambda p: storage.record_incident(
            "kill_switch", account=p.get("account"), detail=p
        ),
    )
    if ks.is_tripped():
        print("refusing to run analytics: kill switch is tripped", file=sys.stderr)
        return 2

    pool = BrowserSessionPool(kill_switch=ks)
    try:
        session = await pool.get(account)
        scraper = ProfileMetricsScraper(
            session, cache_dir=cache_dir, ttl_seconds=ttl_seconds
        )
        metrics = await scraper.fetch(use_cache=not force)
        # Capture previous *before* inserting current so the delta is meaningful.
        previous = storage.previous_metrics(metrics.handle, metrics.collected_at)
        storage.record_metrics(metrics)
        print(_render_metrics(metrics, previous=previous))
        return 0
    finally:
        await pool.close_all()


def cmd_analytics(args: argparse.Namespace) -> int:
    return asyncio.run(
        _analytics(
            account_path=Path(args.account),
            state_file=Path(args.state_file),
            db_path=Path(args.db),
            cache_dir=Path(args.cache_dir),
            ttl_seconds=args.ttl,
            force=args.force,
        )
    )


# ---- history ---------------------------------------------------------------


def cmd_history(args: argparse.Namespace) -> int:
    account = AccountConfig.from_yaml(Path(args.account))
    storage = _storage(args)
    rows = storage.metrics_history(account.handle, limit=args.limit)
    if not rows:
        print(f"no snapshots for @{account.handle}")
        return 0
    print(f"@{account.handle} metrics history (latest {len(rows)})")
    for r in rows:
        f = r.followers if r.followers is not None else "?"
        v = r.verified_followers if r.verified_followers is not None else "?"
        p = r.posts if r.posts is not None else "?"
        print(
            f"  {r.collected_at}  followers={f:>6}  verified={v:>4}  posts={p:>5}"
        )
    return 0


# ---- incidents -------------------------------------------------------------


def cmd_incidents(args: argparse.Namespace) -> int:
    storage = _storage(args)
    rows = storage.recent_incidents(limit=args.limit, account=args.account)
    if not rows:
        scope = f" for @{args.account}" if args.account else ""
        print(f"no incidents{scope}")
        return 0
    for r in rows:
        handle = f"@{r['account_handle']}" if r.get("account_handle") else "-"
        detail = r.get("detail")
        if isinstance(detail, dict):
            summary = detail.get("reason") or json.dumps(detail, ensure_ascii=False)
        else:
            summary = detail or ""
        print(f"{r['occurred_at']}  {r['kind']:<16}  {handle:<24}  {summary}")
    return 0


# ---- parser ----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="x-auto")
    p.add_argument(
        "--state-file",
        default=str(DEFAULT_STATE),
        help="path to the kill-switch state file",
    )
    p.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help="path to the SQLite database (auto-created)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status", help="show kill switch and schedule state")
    s.add_argument("--account", help="optional account YAML to report on")
    s.set_defaults(func=cmd_status)

    k = sub.add_parser("kill", help="trip the kill switch")
    k.add_argument("--reason", required=True)
    k.add_argument("--account-handle", default=None)
    k.set_defaults(func=cmd_kill)

    r = sub.add_parser("reset", help="clear the kill switch")
    r.set_defaults(func=cmd_reset)

    sm = sub.add_parser("smoke", help="open browser and visit example.com")
    sm.add_argument("--account", required=True)
    sm.set_defaults(func=cmd_smoke)

    tr = sub.add_parser(
        "trends",
        help="fetch X trends via a scout account (TTL-cached + DB-recorded)",
    )
    tr.add_argument("--account", required=True, help="scout-only account YAML")
    tr.add_argument("--limit", type=int, default=30)
    tr.add_argument(
        "--ttl",
        type=int,
        default=DEFAULT_TTL_SECONDS,
        help="cache TTL in seconds (default: 900)",
    )
    tr.add_argument(
        "--cache-dir",
        default=str(DEFAULT_TRENDS_CACHE),
        help="directory for cached trend JSON",
    )
    tr.add_argument(
        "--force",
        action="store_true",
        help="bypass cache and hit X even if cache is fresh",
    )
    tr.set_defaults(func=cmd_trends)

    an = sub.add_parser(
        "analytics",
        help="fetch self-account KPIs (followers / verified / posts)",
    )
    an.add_argument("--account", required=True)
    an.add_argument(
        "--ttl",
        type=int,
        default=ANALYTICS_DEFAULT_TTL,
        help="cache TTL in seconds (default: 1800)",
    )
    an.add_argument(
        "--cache-dir",
        default=str(DEFAULT_METRICS_CACHE),
        help="directory for cached metrics JSON",
    )
    an.add_argument(
        "--force",
        action="store_true",
        help="bypass cache and hit X even if cache is fresh",
    )
    an.set_defaults(func=cmd_analytics)

    h = sub.add_parser("history", help="show KPI time series from DB")
    h.add_argument("--account", required=True)
    h.add_argument("--limit", type=int, default=30)
    h.set_defaults(func=cmd_history)

    ic = sub.add_parser("incidents", help="show recent incidents from DB")
    ic.add_argument("--account", default=None, help="filter by handle")
    ic.add_argument("--limit", type=int, default=50)
    ic.set_defaults(func=cmd_incidents)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
