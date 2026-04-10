"""X (Twitter) トレンドスクレイパー.

WARNING — このモジュールは X 本体にアクセスします。ToS 上グレー領域です。
運用上の約束:

- 投稿用とは **別の「スカウト専用」アカウント** を使用してください
  (万一 burn してもメインアカウントに波及しません)
- 呼び出しは TTL 付きキャッシュにより最低 ``ttl_seconds`` 間隔に制限されます
- このモジュールは ``goto`` + ``extract`` のみ行います。同じセッションで
  Like / Follow / Post 等の他アクションを **絶対に** 行わないでください
- kill switch と challenge 検知は ``AccountSession.goto`` 経由で継続有効です

DOM 形状が変わった場合のデバッグのため、ページテキストのスナップショットを
``cache_dir/<handle>.last_raw.html`` に保存します。
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


TRENDS_URL = "https://x.com/explore/tabs/trending"
TREND_SELECTOR = '[data-testid="trend"]'
DEFAULT_TTL_SECONDS = 15 * 60  # 15 minutes

# X は "1.2万件のポスト" / "12.3K posts" 等の形式で件数を表示する。
# 単位は日本語 (千/万/億) と英語 (K/M/B) を両方扱う。
_POST_COUNT_JP = re.compile(r"([\d.]+)\s*(千|万|億)?\s*件?\s*のポスト")
_POST_COUNT_EN = re.compile(r"([\d.]+)\s*(K|M|B)?\s*posts?", re.IGNORECASE)

_CATEGORY_RX = re.compile(r"(トレンド|Trending|トピック)", re.IGNORECASE)
_COUNT_RX = re.compile(r"(件のポスト|posts?\b)", re.IGNORECASE)

_UNIT_MULTIPLIER: dict[str, int] = {
    "千": 1_000,
    "万": 10_000,
    "億": 100_000_000,
    "k": 1_000,
    "m": 1_000_000,
    "b": 1_000_000_000,
}


@dataclass
class Trend:
    rank: int
    word: str
    category: str | None = None
    post_count: int | None = None
    raw_text: str = ""
    collected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def _parse_post_count(text: str) -> int | None:
    """'1.2万件のポスト' / '12.3K posts' などから整数件数を取り出す."""
    for rx in (_POST_COUNT_JP, _POST_COUNT_EN):
        m = rx.search(text)
        if not m:
            continue
        try:
            num = float(m.group(1))
        except ValueError:
            continue
        unit = m.group(2)
        mult = _UNIT_MULTIPLIER.get(unit.lower(), 1) if unit else 1
        return int(num * mult)
    return None


def parse_trend_block(text: str) -> Trend | None:
    """X のトレンドカード 1 枚分のテキストを ``Trend`` に変換する.

    典型レイアウト::

        トレンドトピック・日本
        #入社式
        1.2万件のポスト

    レイアウトは頻繁に変わり得るため、行単位で「カテゴリ」「件数」「その他」に
    分類し、最初の「その他」をトレンドワードとして採用する。
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None

    category: str | None = None
    count_text: str | None = None
    remaining: list[str] = []

    for line in lines:
        if _CATEGORY_RX.search(line):
            category = line
        elif _COUNT_RX.search(line):
            count_text = line
        else:
            remaining.append(line)

    if not remaining:
        return None

    word = remaining[0]
    return Trend(
        rank=0,
        word=word,
        category=category,
        post_count=_parse_post_count(count_text) if count_text else None,
        raw_text=text,
    )


class XTrendScout:
    """X の explore/tabs/trending からトレンドを取得して JSON キャッシュする."""

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
        return self.cache_dir / f"{self.session.account.handle}.trends.json"

    def _debug_path(self) -> Path:
        return self.cache_dir / f"{self.session.account.handle}.last_raw.txt"

    def _load_cache(self) -> list[Trend] | None:
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
        return [Trend(**t) for t in payload.get("trends", [])]

    def _save_cache(self, trends: list[Trend]) -> None:
        payload = {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "source": "x.com/explore/tabs/trending",
            "trends": [asdict(t) for t in trends],
        }
        self._cache_path().write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    async def fetch(
        self,
        limit: int = 30,
        *,
        use_cache: bool = True,
    ) -> list[Trend]:
        """Fetch up to ``limit`` trends. Uses cache if fresh enough."""
        if use_cache:
            cached = self._load_cache()
            if cached is not None:
                return cached[:limit]

        await self.session.goto(TRENDS_URL, wait_until="domcontentloaded")

        page = self.session.page
        try:
            await page.wait_for_selector(TREND_SELECTOR, timeout=20_000)
        except Exception as e:
            # Dump whatever text we got so the human can inspect.
            try:
                body_text = await page.inner_text("body")
                self._debug_path().write_text(body_text, encoding="utf-8")
            except Exception:
                pass
            raise RuntimeError(
                f"trend selector {TREND_SELECTOR!r} did not appear within 20s "
                "(selector may have changed, or login required)"
            ) from e

        # Let virtualized list settle.
        await asyncio.sleep(1.5)

        locators = page.locator(TREND_SELECTOR)
        count = await locators.count()
        trends: list[Trend] = []
        for i in range(min(count, limit)):
            try:
                text = await locators.nth(i).inner_text()
            except Exception:
                continue
            trend = parse_trend_block(text)
            if trend is None:
                continue
            trend.rank = i + 1
            trends.append(trend)

        if not trends:
            raise RuntimeError(
                "trend elements matched but none parsed — DOM schema likely changed"
            )

        self._save_cache(trends)
        return trends
