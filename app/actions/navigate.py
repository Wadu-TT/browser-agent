"""
app/actions/navigate.py — Navigate the browser to a URL.
"""

import logging
from playwright.async_api import Page

logger = logging.getLogger("browser_agent.actions.navigate")


async def navigate(page: Page, url: str) -> str:
    """
    Navigate the browser to the given URL.

    Waits for 'domcontentloaded' (faster than 'networkidle' and sufficient
    for most pages — the agent will perceive the page after navigation anyway).

    Args:
        page: Active Playwright page
        url:  Full URL to navigate to (must include https://)

    Returns:
        A string summarizing the navigation result.
    """
    # Ensure URL has a scheme
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        status = response.status if response else "unknown"
        current_url = page.url
        logger.debug(f"Navigated to {url!r} | status={status} | final_url={current_url!r}")
        return f"Navigated to {current_url} (HTTP {status})"
    except Exception as e:
        error_msg = f"Navigation failed for {url!r}: {e}"
        logger.warning(error_msg)
        raise ValueError(error_msg)
