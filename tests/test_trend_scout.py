"""Unit tests for the trend parser and on-disk cache.

Intentionally does not exercise Playwright — the browser path is exercised
by the ``smoke`` CLI command in manual testing, not here. Here we pin the
pure-Python parsing logic against realistic DOM-derived text.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from x_auto.trend_scout import (
    Trend,
    XTrendScout,
    _parse_post_count,
    parse_trend_block,
)


# ---- parser ----------------------------------------------------------------


def test_parse_japanese_hashtag_trend() -> None:
    text = "トレンドトピック・日本\n#入社式\n1.2万件のポスト"
    t = parse_trend_block(text)
    assert t is not None
    assert t.word == "#入社式"
    assert t.post_count == 12_000
    assert t.category is not None and "日本" in t.category


def test_parse_english_trend() -> None:
    text = "Trending in Japan\nSakura\n12.3K posts"
    t = parse_trend_block(text)
    assert t is not None
    assert t.word == "Sakura"
    assert t.post_count == 12_300


def test_parse_trend_without_count() -> None:
    text = "トレンドトピック\nお花見"
    t = parse_trend_block(text)
    assert t is not None
    assert t.word == "お花見"
    assert t.post_count is None


def test_parse_empty_returns_none() -> None:
    assert parse_trend_block("") is None
    assert parse_trend_block("   \n\n") is None


def test_parse_only_category_returns_none() -> None:
    assert parse_trend_block("トレンドトピック・日本") is None


def test_parse_plain_word_without_category() -> None:
    t = parse_trend_block("お花見\n500件のポスト")
    assert t is not None
    assert t.word == "お花見"
    assert t.post_count == 500


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1.5万件のポスト", 15_000),
        ("500件のポスト", 500),
        ("1億件のポスト", 100_000_000),
        ("3千件のポスト", 3_000),
        ("2.3M posts", 2_300_000),
        ("1K posts", 1_000),
        ("950 posts", 950),
        ("no number here", None),
    ],
)
def test_parse_post_count_variations(text: str, expected: int | None) -> None:
    assert _parse_post_count(text) == expected


# ---- cache -----------------------------------------------------------------


class _FakeAccount:
    def __init__(self, handle: str) -> None:
        self.handle = handle


class _FakeSession:
    def __init__(self, handle: str) -> None:
        self.account = _FakeAccount(handle)


def _make_scout(tmp_path: Path, ttl: int = 900) -> XTrendScout:
    session = _FakeSession("scout_a")
    return XTrendScout(session, cache_dir=tmp_path, ttl_seconds=ttl)  # type: ignore[arg-type]


def test_cache_roundtrip(tmp_path: Path) -> None:
    scout = _make_scout(tmp_path)
    scout._save_cache(
        [
            Trend(rank=1, word="#入社式", post_count=12_000, category="日本"),
            Trend(rank=2, word="お花見", post_count=8_000),
        ]
    )
    loaded = scout._load_cache()
    assert loaded is not None
    assert [t.word for t in loaded] == ["#入社式", "お花見"]
    assert loaded[0].post_count == 12_000


def test_cache_expired_returns_none(tmp_path: Path) -> None:
    scout = _make_scout(tmp_path, ttl=60)
    cache_path = scout._cache_path()
    # Write a stale payload directly.
    stale = datetime.now(timezone.utc) - timedelta(seconds=3600)
    cache_path.write_text(
        json.dumps(
            {
                "collected_at": stale.isoformat(),
                "trends": [asdict(Trend(rank=1, word="old"))],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert scout._load_cache() is None


def test_cache_corrupt_returns_none(tmp_path: Path) -> None:
    scout = _make_scout(tmp_path)
    scout._cache_path().write_text("not json", encoding="utf-8")
    assert scout._load_cache() is None


def test_cache_missing_returns_none(tmp_path: Path) -> None:
    scout = _make_scout(tmp_path)
    assert scout._load_cache() is None
