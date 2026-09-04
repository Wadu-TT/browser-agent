"""
app/actions/extract_text.py — Extract text content from a page element.
"""

import logging
from playwright.async_api import Page

logger = logging.getLogger("browser_agent.actions.extract_text")

MAX_EXTRACT_LENGTH = 5000  # cap extracted text to avoid overwhelming the state


async def extract_text(page: Page, selector: str) -> str:
    """
    Extract visible text from the element matched by the selector.

    Args:
        page:     Active Playwright page
        selector: CSS selector, XPath, or "body" for the full page

    Returns:
        Extracted text (capped at MAX_EXTRACT_LENGTH chars)
    """
    # Special case: extract entire page body
    if selector.strip().lower() in ("body", "page", "all", "*"):
        try:
            text = await page.inner_text("body")
            text = text[:MAX_EXTRACT_LENGTH]
            logger.debug(f"Extracted {len(text)} chars from body")
            return text
        except Exception as e:
            logger.warning(f"Body extraction failed: {e}")
            raise ValueError(f"Could not extract body text: {e}")

    # Strategy 1: Fast JavaScript query for first matching non-empty element
    try:
        js_text = await page.evaluate("""
            (sel) => {
                try {
                    const els = document.querySelectorAll(sel);
                    for (const el of els) {
                        const t = (el.innerText || el.textContent || '').trim();
                        if (t.length > 0) return t;
                    }
                } catch(e) {}
                return null;
            }
        """, selector)
        if js_text:
            logger.debug(f"Extracted JS text from {selector!r}: {js_text[:100]!r}...")
            return js_text[:MAX_EXTRACT_LENGTH]
    except Exception as e_js:
        logger.debug(f"JS extraction failed for {selector!r}: {e_js}")

    # Strategy 2: direct locator inner_text
    try:
        locator = page.locator(selector).first
        text = await locator.inner_text(timeout=3000)
        if text.strip():
            return text[:MAX_EXTRACT_LENGTH]
    except Exception as e1:
        logger.debug(f"Direct extraction failed for {selector!r}: {e1}")

    # Strategy 3: try by text search
    try:
        text = await page.get_by_text(selector, exact=False).first.inner_text(timeout=2000)
        if text.strip():
            return text[:MAX_EXTRACT_LENGTH]
    except Exception as e2:
        logger.debug(f"Text-based extraction failed for {selector!r}: {e2}")

    error_msg = f"Could not extract text from: {selector!r}"
    logger.warning(error_msg)
    raise ValueError(error_msg)
