"""Playwright browser session pool.

One persistent-context browser per account. The context is rooted at the
account's ``user_data_dir`` so cookies, localStorage, and IndexedDB survive
restarts — we never want to log in again unless we have to.

Every navigation goes through ``AccountSession.goto()`` which:
  1. consults the kill switch,
  2. enforces the circadian schedule,
  3. sniffs for CAPTCHA / login-challenge UI after load, and trips the
     kill switch if any is found.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from .config import AccountConfig
from .kill_switch import KillSwitch
from .schedule import assert_active

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page, Playwright


# Injected into every page before scripts run. Patches the most common
# automation tells. NOT a substitute for a real stealth library in production,
# but enough to not fail the trivial ``navigator.webdriver`` check.
_STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['ja-JP', 'ja', 'en'] });
Object.defineProperty(navigator, 'plugins', {
  get: () => [1, 2, 3, 4, 5].map(() => ({ name: 'plugin' })),
});
window.chrome = window.chrome || { runtime: {} };
"""

# Selectors that indicate X is challenging us. If any match after a navigation,
# we consider the session burned and trip the kill switch.
_CHALLENGE_SELECTORS = (
    'iframe[title*="captcha" i]',
    'iframe[src*="arkoselabs" i]',
    'iframe[src*="funcaptcha" i]',
    'div[data-testid="LoginForm_Login_Button"]',
    'input[name="challenge_response"]',
    'text=/認証.{0,4}必要/',
    'text=/unusual login activity/i',
    'text=/help us verify/i',
)


class ChallengeDetected(RuntimeError):
    """Raised when X presents a CAPTCHA or login challenge."""


class AccountSession:
    """Wrapper around a single account's Playwright context + page."""

    def __init__(
        self,
        account: AccountConfig,
        kill_switch: KillSwitch,
        playwright: "Playwright",
        context: "BrowserContext",
        page: "Page",
    ) -> None:
        self.account = account
        self.kill_switch = kill_switch
        self._playwright = playwright
        self.context = context
        self.page = page

    @classmethod
    async def create(
        cls,
        account: AccountConfig,
        kill_switch: KillSwitch,
    ) -> "AccountSession":
        # Deferred import so unit tests that don't exercise the browser
        # don't need playwright browsers installed.
        from playwright.async_api import async_playwright

        kill_switch.check()
        assert_active(account.circadian_start, account.circadian_end, account.timezone)

        account.user_data_dir.mkdir(parents=True, exist_ok=True)
        pw = await async_playwright().start()

        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(account.user_data_dir),
            headless=account.headless,
            proxy={"server": account.proxy_url} if account.proxy_url else None,
            user_agent=account.user_agent,
            viewport={"width": account.viewport.width, "height": account.viewport.height},
            locale=account.locale,
            timezone_id=account.timezone,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )
        await context.add_init_script(_STEALTH_INIT_SCRIPT)

        page = context.pages[0] if context.pages else await context.new_page()
        return cls(account, kill_switch, pw, context, page)

    async def goto(self, url: str, *, wait_until: str = "domcontentloaded") -> None:
        self.kill_switch.check()
        assert_active(
            self.account.circadian_start,
            self.account.circadian_end,
            self.account.timezone,
        )
        await self.page.goto(url, wait_until=wait_until)
        await self._detect_challenge()

    async def _detect_challenge(self) -> None:
        for sel in _CHALLENGE_SELECTORS:
            try:
                locator = self.page.locator(sel).first
                if await locator.count() > 0:
                    self.kill_switch.trigger(
                        reason=f"challenge detected: {sel}",
                        account=self.account.handle,
                    )
                    raise ChallengeDetected(sel)
            except ChallengeDetected:
                raise
            except Exception:
                # A broken selector shouldn't mask real challenges;
                # skip and keep checking the rest.
                continue

    async def close(self) -> None:
        try:
            await self.context.close()
        finally:
            await self._playwright.stop()


class BrowserSessionPool:
    """Holds one live ``AccountSession`` per handle."""

    def __init__(self, kill_switch: KillSwitch) -> None:
        self.kill_switch = kill_switch
        self._sessions: dict[str, AccountSession] = {}
        self._lock = asyncio.Lock()

    async def get(self, account: AccountConfig) -> AccountSession:
        async with self._lock:
            existing = self._sessions.get(account.handle)
            if existing is not None:
                return existing
            session = await AccountSession.create(account, self.kill_switch)
            self._sessions[account.handle] = session
            return session

    async def close_all(self) -> None:
        async with self._lock:
            for session in list(self._sessions.values()):
                try:
                    await session.close()
                except Exception:
                    pass
            self._sessions.clear()
