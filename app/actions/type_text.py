"""
app/actions/type_text.py — Type text into an input element.

Uses page.fill() for instant fill rather than character-by-character typing.
Clears existing content before filling.
"""

import logging
from playwright.async_api import Page

logger = logging.getLogger("browser_agent.actions.type_text")


async def type_text(page: Page, selector: str, text: str) -> str:
    """
    Fill text into an input, textarea, or contenteditable element.

    Args:
        page:     Active Playwright page
        selector: CSS selector, XPath, or text locator for the input element
        text:     The text to type

    Returns:
        A string summarizing what was done.
    """
    # Strategy 1: direct fill by selector
    try:
        locator = page.locator(selector).first
        await locator.fill(text, timeout=5000)
        logger.debug(f"Filled {selector!r} with: {text[:50]!r}")
        return f"Typed into {selector}: {text[:80]!r}"
    except Exception as e1:
        logger.debug(f"Direct fill failed for {selector!r}: {e1}")

    # Strategy 2: try by placeholder
    try:
        locator = page.get_by_placeholder(selector, exact=False).first
        await locator.fill(text, timeout=5000)
        logger.debug(f"Filled by placeholder {selector!r}")
        return f"Typed into placeholder '{selector}': {text[:80]!r}"
    except Exception as e2:
        logger.debug(f"Placeholder fill failed for {selector!r}: {e2}")

    # Strategy 3: try by label
    try:
        locator = page.get_by_label(selector, exact=False).first
        await locator.fill(text, timeout=5000)
        logger.debug(f"Filled by label {selector!r}")
        return f"Typed into label '{selector}': {text[:80]!r}"
    except Exception as e3:
        logger.debug(f"Label fill failed for {selector!r}: {e3}")

    error_msg = f"Could not type into element: {selector!r}"
    logger.warning(error_msg)
    raise ValueError(error_msg)
