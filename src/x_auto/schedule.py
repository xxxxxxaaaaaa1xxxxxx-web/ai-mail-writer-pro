"""Circadian schedule enforcement.

Every action must pass through ``assert_active()``. If the current local time
falls within the quiet window ``[circadian_start, circadian_end)`` the action
is refused. This is the cheapest anti-bot-detection mechanism we have:
activity that stops at night looks human, activity that runs 24/7 doesn't.
"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo


class CircadianQuietHours(RuntimeError):
    """Raised when an action is attempted during the quiet window."""


def _parse_hhmm(v: str) -> time:
    h, m = (int(x) for x in v.split(":"))
    return time(hour=h, minute=m)


def is_quiet(now: datetime, start: str, end: str) -> bool:
    """Return True if ``now`` falls within ``[start, end)``.

    Supports windows that cross midnight (e.g. start=23:00, end=07:00).
    ``now`` must be timezone-aware.
    """
    if now.tzinfo is None:
        raise ValueError("`now` must be timezone-aware")
    start_t = _parse_hhmm(start)
    end_t = _parse_hhmm(end)
    cur = now.time()
    if start_t <= end_t:
        return start_t <= cur < end_t
    return cur >= start_t or cur < end_t


def is_active(
    start: str,
    end: str,
    tz: str = "Asia/Tokyo",
    *,
    now: datetime | None = None,
) -> bool:
    """Return True if the bot is allowed to act right now."""
    now = now or datetime.now(ZoneInfo(tz))
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo(tz))
    return not is_quiet(now, start, end)


def assert_active(
    start: str,
    end: str,
    tz: str = "Asia/Tokyo",
    *,
    now: datetime | None = None,
) -> None:
    if not is_active(start, end, tz, now=now):
        raise CircadianQuietHours(
            f"within quiet hours [{start}, {end}) for timezone {tz}"
        )
