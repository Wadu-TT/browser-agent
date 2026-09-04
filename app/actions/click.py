"""
app/actions/click.py — Click action using semantic locators first.

Uses Playwright's semantic locators (role, text) before falling back to CSS/XPath
selectors. Semantic locators are far more resilient to site layout changes.
"""

import logging
from playwright.async_api import Page

logger = logging.getLogger("browser_agent.actions.click")


async def click(page: Page, selector: str) -> str:
    """
    Click an element on the page.

    The selector can be:
    - A CSS selector: "#submit-btn", ".nav-link"
    - A text phrase: "text=Sign in"
    - A role locator: "role=button[name='Submit']"
    - An ARIA label: "aria-label=Close"

    Tries multiple strategies before failing.
    """
    # Strategy 1: try the selector as-is (handles CSS, XPath, text=, role=)
    try:
        locator = page.locator(selector).first
        await locator.click(timeout=5000)
        logger.debug(f"Clicked: {selector!r} (direct selector)")
        return f"Clicked element: {selector}"
    except Exception as e1:
        logger.debug(f"Direct selector failed for {selector!r}: {e1}")

    # Strategy 2: try by visible text (useful when selector is a label)
    try:
        locator = page.get_by_text(selector, exact=False).first
        await locator.click(timeout=5000)
        logger.debug(f"Clicked by text: {selector!r}")
        return f"Clicked element with text: {selector}"
    except Exception as e2:
        logger.debug(f"Text locator failed for {selector!r}: {e2}")

    # Strategy 3: try by role + name
    try:
        for role in ("button", "link", "menuitem", "tab"):
            try:
                locator = page.get_by_role(role, name=selector)  # type: ignore[arg-type]
                await locator.first.click(timeout=3000)
                logger.debug(f"Clicked by role={role} name={selector!r}")
                return f"Clicked {role} with name: {selector}"
            except Exception:
                continue
    except Exception as e3:
        logger.debug(f"Role locator failed for {selector!r}: {e3}")

    error_msg = f"Could not click element: {selector!r}"
    logger.warning(error_msg)
    raise ValueError(error_msg)
