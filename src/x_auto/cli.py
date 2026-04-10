"""Command-line interface.

Commands:
    x-auto status                      — show kill switch + schedule state
    x-auto kill   --reason "..."       — trip the kill switch
    x-auto reset                       — clear the kill switch
    x-auto smoke  --account path.yml   — open a browser, visit example.com,
                                         print the title, shut down
    x-auto trends --account path.yml   — fetch X trends via a scout account
                                         (TTL-cached on disk)

``smoke`` hits example.com only and is safe to run any time.
``trends`` hits X itself — use a **scout-only** account, never a posting one.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .browser import BrowserSessionPool
from .config import AccountConfig
from .kill_switch import KillSwitch
from .schedule import is_active
from .trend_scout import DEFAULT_TTL_SECONDS, XTrendScout

DEFAULT_STATE = Path("./state/kill_switch.json")
DEFAULT_TRENDS_CACHE = Path("./state/trends")


def _kill_switch(args: argparse.Namespace) -> KillSwitch:
    return KillSwitch(Path(args.state_file))


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
    ks = _kill_switch(args)
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


async def _trends(
    account_path: Path,
    state_file: Path,
    cache_dir: Path,
    limit: int,
    ttl_seconds: int,
    force: bool,
) -> int:
    account = AccountConfig.from_yaml(account_path)
    ks = KillSwitch(state_file)
    if ks.is_tripped():
        print("refusing to run trends: kill switch is tripped", file=sys.stderr)
        return 2

    pool = BrowserSessionPool(kill_switch=ks)
    try:
        session = await pool.get(account)
        scout = XTrendScout(session, cache_dir=cache_dir, ttl_seconds=ttl_seconds)
        trends = await scout.fetch(limit=limit, use_cache=not force)
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
            cache_dir=Path(args.cache_dir),
            limit=args.limit,
            ttl_seconds=args.ttl,
            force=args.force,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="x-auto")
    p.add_argument(
        "--state-file",
        default=str(DEFAULT_STATE),
        help="path to the kill-switch state file",
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
        help="fetch X trends via a scout account (TTL-cached)",
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

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
