"""
app/actions/scroll.py — Scroll the page up or down.
"""

import logging
from typing import Literal
from playwright.async_api import Page

logger = logging.getLogger("browser_agent.actions.scroll")

SCROLL_DELTA = 800  # pixels per scroll


async def scroll(page: Page, direction: Literal["up", "down"] = "down") -> str:
    """
    Scroll the page up or down by SCROLL_DELTA pixels.

    Args:
        page:      Active Playwright page
        direction: "up" or "down"

    Returns:
        A string summarizing the scroll action.
    """
    if direction not in ("up", "down"):
        raise ValueError(f"Invalid scroll direction: {direction!r}. Use 'up' or 'down'.")

    delta = SCROLL_DELTA if direction == "down" else -SCROLL_DELTA

    try:
        await page.mouse.wheel(0, delta)
        logger.debug(f"Scrolled {direction} by {abs(delta)}px")
        return f"Scrolled {direction}"
    except Exception as e:
        error_msg = f"Scroll {direction} failed: {e}"
        logger.warning(error_msg)
        raise ValueError(error_msg)
