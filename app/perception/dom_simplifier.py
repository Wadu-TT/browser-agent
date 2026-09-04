"""
app/perception/dom_simplifier.py — Extract a compact, LLM-friendly page representation.

The most critical design decision in this project:
- NEVER dump raw HTML to the LLM (scripts, styles, deeply nested divs = noise)
- Extract visible text + interactive elements only
- Cap lengths so a dense page doesn't blow the context window

Output format example:
    === PAGE STATE ===
    URL: https://example.com/search
    TITLE: Example Search

    --- VISIBLE TEXT (first 2000 chars) ---
    Welcome to Example ...

    --- INTERACTIVE ELEMENTS (up to 40) ---
    [1] button | "Search" | id=search-btn
    [2] input | placeholder="Search..." | id=query-input
    [3] a | "Home" | href=/
    ...
"""

import logging
from playwright.async_api import Page

logger = logging.getLogger("browser_agent.perception")

MAX_VISIBLE_TEXT = 2000    # chars of visible content text to include (lean context)
MAX_INTERACTIVE = 25       # max interactive elements to list
MAX_ELEMENT_TEXT = 60      # max chars per element label


async def simplify_page(page: Page) -> str:
    """
    Return a compact text representation of the current page:
    visible body text + a numbered list of interactive elements.
    """
    url = page.url
    title = await page.title()

    # ── Visible text (prioritize main article/content container) ───────────────
    try:
        main_text = await page.evaluate("""
            () => {
                const mainEl = document.querySelector('main, article, #content, #mw-content-text, [role="main"], #main-content');
                if (mainEl && (mainEl.innerText || '').trim().length > 100) {
                    return mainEl.innerText;
                }
                return document.body ? document.body.innerText : '';
            }
        """)
        body_text = _clean_text(main_text)[:MAX_VISIBLE_TEXT]
    except Exception as e:
        body_text = f"[Could not extract body text: {e}]"
        logger.warning(f"Body text extraction failed: {e}")

    # ── Interactive elements ───────────────────────────────────────────────────
    try:
        interactive = await page.evaluate(_INTERACTIVE_JS)
        interactive = interactive[:MAX_INTERACTIVE]
    except Exception as e:
        interactive = []
        logger.warning(f"Interactive element extraction failed: {e}")

    # ── Format output ──────────────────────────────────────────────────────────
    return _format_page_state(url, title, body_text, interactive)


def _clean_text(text: str) -> str:
    """Remove excessive whitespace and blank lines from body text."""
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    lines = (line.strip() for line in text.splitlines())
    non_empty = (line for line in lines if line)
    return "\n".join(non_empty)


def _format_page_state(
    url: str,
    title: str,
    body_text: str,
    interactive: list[dict],
) -> str:
    """Format the extracted page data into a clean string for the LLM."""
    lines = [
        "=== PAGE STATE ===",
        f"URL: {url}",
        f"TITLE: {title}",
        "",
        f"--- VISIBLE TEXT (first {MAX_VISIBLE_TEXT} chars) ---",
        body_text,
        "",
        f"--- INTERACTIVE ELEMENTS (up to {MAX_INTERACTIVE}) ---",
    ]

    for i, el in enumerate(interactive, start=1):
        tag = el.get("tag", "?")
        text = (el.get("text") or "")[:MAX_ELEMENT_TEXT]
        el_id = el.get("id") or ""
        role = el.get("role") or ""
        href = el.get("href") or ""
        placeholder = el.get("placeholder") or ""

        parts = [f"[{i}]", tag]
        if text:
            parts.append(f'"{text}"')
        if el_id:
            parts.append(f"id={el_id}")
        if role:
            parts.append(f"role={role}")
        if placeholder:
            parts.append(f'placeholder="{placeholder}"')
        if href:
            parts.append(f"href={href[:60]}")

        lines.append(" | ".join(parts))

    return "\n".join(lines)


# JavaScript snippet to extract interactive elements from the live DOM
_INTERACTIVE_JS = """
() => Array.from(
    document.querySelectorAll('button, a[href], input, select, textarea, [role="button"], [role="link"], [role="menuitem"], [role="tab"]')
)
.filter(el => {
    const rect = el.getBoundingClientRect();
    return el.offsetParent !== null && rect.width > 0 && rect.height > 0;
})
.map(el => ({
    tag: el.tagName.toLowerCase(),
    text: (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().slice(0, 80),
    id: el.id || null,
    role: el.getAttribute('role') || null,
    placeholder: el.placeholder || null,
    href: el.href || null,
}))
"""
