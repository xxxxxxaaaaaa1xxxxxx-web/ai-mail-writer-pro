"""Human-like interaction primitives.

Every function here should introduce jitter — never act deterministically.
The goal is not perfect mimicry, but avoiding the obvious tells
(instant typing, zero delay between actions, perfectly linear mouse moves).
"""

from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page


async def human_delay(min_sec: float = 0.5, max_sec: float = 2.0) -> None:
    """Sleep for a random duration in [min_sec, max_sec]."""
    await asyncio.sleep(random.uniform(min_sec, max_sec))


async def human_type(page: "Page", selector: str, text: str) -> None:
    """Focus ``selector`` and type ``text`` with per-key jitter."""
    await page.click(selector)
    await human_delay(0.2, 0.6)
    for char in text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.08, 0.22))
        # Occasional longer pause — like a human thinking.
        if random.random() < 0.04:
            await asyncio.sleep(random.uniform(0.4, 1.2))


async def human_scroll(page: "Page", total_pixels: int = 1200) -> None:
    """Scroll ``total_pixels`` downward in jittered chunks."""
    scrolled = 0
    while scrolled < total_pixels:
        step = random.randint(120, 320)
        await page.mouse.wheel(0, step)
        scrolled += step
        await human_delay(0.35, 1.1)
        # Occasional small scroll-back — humans do this.
        if random.random() < 0.15:
            await page.mouse.wheel(0, -random.randint(40, 120))
            await human_delay(0.2, 0.6)


async def idle_browse(page: "Page", seconds: float = 30.0) -> None:
    """Pretend to read the current page for roughly ``seconds`` seconds.

    Used for "idle sessions" — scheduled sessions where the bot deliberately
    does nothing but scroll, to keep the behavioural distribution natural.
    """
    end = asyncio.get_event_loop().time() + seconds
    while asyncio.get_event_loop().time() < end:
        await human_scroll(page, total_pixels=random.randint(200, 800))
        await human_delay(1.0, 4.0)
