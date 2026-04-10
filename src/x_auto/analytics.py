"""Self-account KPI scraper.

WARNING — このモジュールは X 本体にアクセスします。 ``trend_scout`` と同じ
ガードを共有します:

- 対象アカウント自身の公開プロフィールのみを読む (他人のアカウントは scrape しない)
- TTL 付き JSON キャッシュで再取得頻度を制限 (デフォルト 30 分)
- single-shot: ``goto`` + extract のみ。同セッションで他アクションを行わない
- ``AccountSession.goto`` 経由で kill switch と challenge 検知が継続有効

収集する KPI は収益化条件の進捗を可視化するために選んでいます:
- ``followers``           — フォロワー総数
- ``following``           — フォロー数 (比率ガード用)
- ``verified_followers``  — 認証済み (Premium) フォロワー数 = **収益化の 500 人条件**
- ``posts``               — 総ポスト数

インプレッション / エンゲージメント率は Creator Analytics ダッシュボードが
必要で DOM が重く・頻繁に変わるため、本 PoC では対象外。
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .browser import AccountSession


DEFAULT_TTL_SECONDS = 30 * 60  # 30 minutes
PREMIUM_FOLLOWERS_TARGET = 500

# Compact numbers: "1,234" "1.2万" "2.3M" "500" "1.5億" "12.3K"
_COMPACT_NUMBER_RX = re.compile(r"([\d][\d,\.]*)\s*(千|万|億|K|M|B)?", re.IGNORECASE)

_UNIT_MULT: dict[str, int] = {
    "千": 1_000,
    "万": 10_000,
    "億": 100_000_000,
    "k": 1_000,
    "m": 1_000_000,
    "b": 1_000_000_000,
}

_POST_LABEL_RX = re.compile(r"(posts?|ポスト|投稿)", re.IGNORECASE)


def parse_compact_number(text: str) -> int | None:
    """Extract the first compact integer from a string.

    Handles::

        '1,234'   -> 1234
        '1.2万'   -> 12000
        '2.3M'    -> 2300000
        '500'     -> 500
        '1.5億'   -> 150000000
        '12.3K'   -> 12300
    """
    if not text:
        return None
    m = _COMPACT_NUMBER_RX.search(text)
    if not m:
        return None
    num_str = m.group(1).replace(",", "")
    # Reject bare "." or trailing-dot strings like "1." (X never renders these).
    if not num_str or num_str in {".", ","} or num_str.endswith("."):
        return None
    try:
        num = float(num_str)
    except ValueError:
        return None
    unit = m.group(2)
    mult = _UNIT_MULT.get(unit.lower(), 1) if unit else 1
    return int(num * mult)


@dataclass
class AccountMetrics:
    handle: str
    followers: int | None = None
    following: int | None = None
    verified_followers: int | None = None
    posts: int | None = None
    premium_followers_target: int = PREMIUM_FOLLOWERS_TARGET
    collected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    raw_snippets: dict[str, str] = field(default_factory=dict)

    def premium_progress(self) -> float | None:
        """Return verified_followers / target clamped to [0, 1], or None if unknown."""
        if self.verified_followers is None:
            return None
        if self.premium_followers_target <= 0:
            return None
        return max(0.0, min(1.0, self.verified_followers / self.premium_followers_target))

    def follow_ratio(self) -> float | None:
        """following / followers — should stay < 1.1 per design §3.5."""
        if self.followers is None or self.following is None or self.followers == 0:
            return None
        return self.following / self.followers


async def _first_count_by_href(
    page,
    href_suffix: str,
) -> tuple[int | None, str]:
    """Find the first ``<a href$=...>`` and parse a count from its text."""
    try:
        locator = page.locator(f'a[href$="{href_suffix}"]').first
        if await locator.count() == 0:
            return (None, "")
        text = await locator.inner_text()
        return (parse_compact_number(text), text)
    except Exception:
        return (None, "")


async def _scan_post_count(page) -> tuple[int | None, str]:
    """Scan the primary column for a line containing 'posts'/'ポスト'/'投稿'."""
    try:
        primary = page.locator('[data-testid="primaryColumn"]').first
        text = await primary.inner_text()
    except Exception:
        return (None, "")
    for line in text.splitlines():
        if _POST_LABEL_RX.search(line):
            num = parse_compact_number(line)
            if num is not None:
                return (num, line.strip())
    return (None, "")


class ProfileMetricsScraper:
    """Scrape self-profile KPIs (followers, following, verified followers, posts)."""

    def __init__(
        self,
        session: "AccountSession",
        cache_dir: Path,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self.session = session
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self) -> Path:
        return self.cache_dir / f"{self.session.account.handle}.metrics.json"

    def _debug_path(self) -> Path:
        return self.cache_dir / f"{self.session.account.handle}.metrics_raw.txt"

    def _load_cache(self) -> AccountMetrics | None:
        path = self._cache_path()
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        try:
            collected_at = datetime.fromisoformat(payload["collected_at"])
        except (KeyError, ValueError):
            return None
        age = (datetime.now(timezone.utc) - collected_at).total_seconds()
        if age > self.ttl_seconds:
            return None
        try:
            return AccountMetrics(**payload)
        except TypeError:
            return None

    def _save_cache(self, metrics: AccountMetrics) -> None:
        self._cache_path().write_text(
            json.dumps(asdict(metrics), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    async def fetch(self, *, use_cache: bool = True) -> AccountMetrics:
        if use_cache:
            cached = self._load_cache()
            if cached is not None:
                return cached

        handle = self.session.account.handle
        profile_url = f"https://x.com/{handle}"

        await self.session.goto(profile_url, wait_until="domcontentloaded")
        page = self.session.page

        try:
            await page.wait_for_selector(
                '[data-testid="primaryColumn"]',
                timeout=20_000,
            )
        except Exception as e:
            try:
                body = await page.inner_text("body")
                self._debug_path().write_text(body, encoding="utf-8")
            except Exception:
                pass
            raise RuntimeError(
                f"profile page did not load for @{handle} "
                "(login required, handle wrong, or DOM changed)"
            ) from e

        # Let virtualized layout settle.
        await asyncio.sleep(1.5)

        metrics = AccountMetrics(handle=handle)

        metrics.followers, metrics.raw_snippets["followers"] = await _first_count_by_href(
            page, f"/{handle}/followers"
        )
        metrics.following, metrics.raw_snippets["following"] = await _first_count_by_href(
            page, f"/{handle}/following"
        )
        (
            metrics.verified_followers,
            metrics.raw_snippets["verified_followers"],
        ) = await _first_count_by_href(page, f"/{handle}/verified_followers")

        metrics.posts, metrics.raw_snippets["posts"] = await _scan_post_count(page)

        if all(
            v is None
            for v in (
                metrics.followers,
                metrics.following,
                metrics.verified_followers,
                metrics.posts,
            )
        ):
            # Dump for debugging — DOM schema likely changed.
            try:
                body = await page.inner_text("body")
                self._debug_path().write_text(body, encoding="utf-8")
            except Exception:
                pass
            raise RuntimeError(
                "all KPI extractors returned None — DOM schema likely changed"
            )

        self._save_cache(metrics)
        return metrics
