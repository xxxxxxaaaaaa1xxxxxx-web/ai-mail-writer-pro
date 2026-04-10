"""Unit tests for the analytics parser, progress math, and cache.

Like ``test_trend_scout.py``, this file never touches Playwright. The
browser path is exercised by the ``analytics`` CLI command in manual testing.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from x_auto.analytics import (
    AccountMetrics,
    PREMIUM_FOLLOWERS_TARGET,
    ProfileMetricsScraper,
    parse_compact_number,
)


# ---- parse_compact_number --------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1,234", 1_234),
        ("500", 500),
        ("1.2万", 12_000),
        ("3千", 3_000),
        ("1.5億", 150_000_000),
        ("12.3K", 12_300),
        ("2.3M", 2_300_000),
        ("1B", 1_000_000_000),
        ("0", 0),
        ("", None),
        ("no number", None),
        (".", None),
        ("1.", None),
        # Leading label is ignored, first numeric token wins.
        ("Followers 1,234", 1_234),
        ("フォロワー 1.2万", 12_000),
    ],
)
def test_parse_compact_number(text: str, expected: int | None) -> None:
    assert parse_compact_number(text) == expected


# ---- AccountMetrics math ---------------------------------------------------


def test_premium_progress_none_when_unknown() -> None:
    m = AccountMetrics(handle="a")
    assert m.premium_progress() is None


def test_premium_progress_fraction() -> None:
    m = AccountMetrics(handle="a", verified_followers=250)
    assert m.premium_progress() == pytest.approx(0.5)


def test_premium_progress_clamped_to_one() -> None:
    m = AccountMetrics(handle="a", verified_followers=999_999)
    assert m.premium_progress() == 1.0


def test_premium_progress_zero() -> None:
    m = AccountMetrics(handle="a", verified_followers=0)
    assert m.premium_progress() == 0.0


def test_follow_ratio_none_when_missing() -> None:
    assert AccountMetrics(handle="a").follow_ratio() is None
    assert AccountMetrics(handle="a", followers=100).follow_ratio() is None
    assert AccountMetrics(handle="a", followers=0, following=50).follow_ratio() is None


def test_follow_ratio_value() -> None:
    m = AccountMetrics(handle="a", followers=200, following=100)
    assert m.follow_ratio() == pytest.approx(0.5)


def test_default_premium_target_matches_monetization_condition() -> None:
    assert PREMIUM_FOLLOWERS_TARGET == 500
    assert AccountMetrics(handle="a").premium_followers_target == 500


# ---- cache -----------------------------------------------------------------


class _FakeAccount:
    def __init__(self, handle: str) -> None:
        self.handle = handle


class _FakeSession:
    def __init__(self, handle: str) -> None:
        self.account = _FakeAccount(handle)


def _make_scraper(tmp_path: Path, ttl: int = 1800) -> ProfileMetricsScraper:
    session = _FakeSession("me")
    return ProfileMetricsScraper(session, cache_dir=tmp_path, ttl_seconds=ttl)  # type: ignore[arg-type]


def test_cache_roundtrip(tmp_path: Path) -> None:
    scraper = _make_scraper(tmp_path)
    original = AccountMetrics(
        handle="me",
        followers=1200,
        following=250,
        verified_followers=42,
        posts=876,
    )
    scraper._save_cache(original)

    loaded = scraper._load_cache()
    assert loaded is not None
    assert loaded.handle == "me"
    assert loaded.followers == 1200
    assert loaded.verified_followers == 42
    assert loaded.posts == 876
    assert loaded.premium_progress() == pytest.approx(42 / 500)


def test_cache_expired_returns_none(tmp_path: Path) -> None:
    scraper = _make_scraper(tmp_path, ttl=60)
    stale = datetime.now(timezone.utc) - timedelta(seconds=3600)
    payload = asdict(AccountMetrics(handle="me", followers=1))
    payload["collected_at"] = stale.isoformat()
    scraper._cache_path().write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    assert scraper._load_cache() is None


def test_cache_corrupt_returns_none(tmp_path: Path) -> None:
    scraper = _make_scraper(tmp_path)
    scraper._cache_path().write_text("definitely not json", encoding="utf-8")
    assert scraper._load_cache() is None


def test_cache_missing_returns_none(tmp_path: Path) -> None:
    scraper = _make_scraper(tmp_path)
    assert scraper._load_cache() is None
