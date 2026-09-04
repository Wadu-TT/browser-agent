"""
app/actions/browser_controller.py — Playwright session lifecycle management.

Manages a module-level singleton browser/page so it can be shared across
LangGraph nodes without being serialized into BrowserState.
"""

import logging
from playwright.async_api import async_playwright, Browser, Page, Playwright

logger = logging.getLogger("browser_agent.controller")

# Module-level singletons — shared across all nodes in one agent run
_playwright: Playwright | None = None
_browser: Browser | None = None
_page: Page | None = None


async def launch_browser(headless: bool = True) -> Page:
    """
    Launch a Chromium browser instance and return the active page.
    Must be called once before starting the agent graph.
    """
    global _playwright, _browser, _page

    logger.info(f"Launching Chromium (headless={headless})")
    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",  # important for Docker
            "--disable-gpu",
        ],
    )
    context = await _browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    _page = await context.new_page()
    logger.info("Browser launched successfully")
    return _page


async def close_browser():
    """Close the browser and clean up the Playwright instance."""
    global _playwright, _browser, _page

    if _page and not _page.is_closed():
        await _page.close()
    if _browser:
        await _browser.close()
    if _playwright:
        await _playwright.stop()

    _playwright = None
    _browser = None
    _page = None
    logger.info("Browser closed")


def get_page() -> Page:
    """
    Return the currently active page.
    Raises RuntimeError if the browser hasn't been launched yet.
    """
    if _page is None or _page.is_closed():
        raise RuntimeError(
            "Browser page is not available. Call launch_browser() first."
        )
    return _page
