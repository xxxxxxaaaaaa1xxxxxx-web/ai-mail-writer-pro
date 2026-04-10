from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from x_auto.schedule import CircadianQuietHours, assert_active, is_active, is_quiet


JST = ZoneInfo("Asia/Tokyo")


@pytest.mark.parametrize(
    "hour,minute,start,end,quiet",
    [
        (3, 0, "01:00", "08:00", True),
        (0, 59, "01:00", "08:00", False),
        (8, 0, "01:00", "08:00", False),
        (23, 30, "23:00", "07:00", True),  # cross-midnight window
        (6, 0, "23:00", "07:00", True),
        (7, 0, "23:00", "07:00", False),
        (12, 0, "23:00", "07:00", False),
    ],
)
def test_is_quiet(hour: int, minute: int, start: str, end: str, quiet: bool) -> None:
    now = datetime(2026, 4, 10, hour, minute, tzinfo=JST)
    assert is_quiet(now, start, end) is quiet


def test_is_active_is_inverse_of_quiet() -> None:
    now = datetime(2026, 4, 10, 3, 0, tzinfo=JST)
    assert is_active("01:00", "08:00", "Asia/Tokyo", now=now) is False
    now = datetime(2026, 4, 10, 10, 0, tzinfo=JST)
    assert is_active("01:00", "08:00", "Asia/Tokyo", now=now) is True


def test_assert_active_raises_during_quiet_hours() -> None:
    now = datetime(2026, 4, 10, 3, 0, tzinfo=JST)
    with pytest.raises(CircadianQuietHours):
        assert_active("01:00", "08:00", "Asia/Tokyo", now=now)


def test_assert_active_silent_when_active() -> None:
    now = datetime(2026, 4, 10, 12, 0, tzinfo=JST)
    assert_active("01:00", "08:00", "Asia/Tokyo", now=now)  # no raise


def test_naive_datetime_rejected() -> None:
    with pytest.raises(ValueError):
        is_quiet(datetime(2026, 4, 10, 3, 0), "01:00", "08:00")
