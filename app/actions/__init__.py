"""
app/actions/__init__.py — Action dispatcher.

Routes the action dict returned by the planner to the correct action function.
All action functions share the same signature: async (page, **kwargs) -> str.
"""

import logging
from typing import Any
from playwright.async_api import Page

from app.actions.click import click
from app.actions.type_text import type_text
from app.actions.navigate import navigate
from app.actions.extract_text import extract_text
from app.actions.scroll import scroll

logger = logging.getLogger("browser_agent.actions")

# Registry of all valid action types
ACTION_REGISTRY = {
    "click": click,
    "type_text": type_text,
    "navigate": navigate,
    "extract_text": extract_text,
    "scroll": scroll,
}


async def execute_action(page: Page, action: dict[str, Any]) -> str:
    """
    Execute a single action returned by the planner.

    The action dict has the shape:
        {
            "type": "click" | "type_text" | "navigate" | "extract_text" | "scroll" | "DONE",
            "selector": "...",   # optional, depends on action type
            "text": "...",       # optional, for type_text
            "url": "...",        # optional, for navigate
            "direction": "...",  # optional, for scroll
            "result": "...",     # optional, for DONE
        }

    Returns a human-readable result string.
    """
    action_type = action.get("type", "").lower()

    if action_type == "done":
        return action.get("result", "Task completed.")

    if action_type not in ACTION_REGISTRY:
        raise ValueError(f"Unknown action type: {action_type!r}. Valid: {list(ACTION_REGISTRY)}")

    action_fn = ACTION_REGISTRY[action_type]

    try:
        if action_type == "click":
            selector = action.get("selector") or "body"
            result = await action_fn(page, selector)

        elif action_type == "type_text":
            selector = action.get("selector") or "input"
            text = action.get("text") or ""
            result = await action_fn(page, selector, text)

        elif action_type == "navigate":
            url = action.get("url") or page.url
            result = await action_fn(page, url)

        elif action_type == "extract_text":
            result = await action_fn(page, action.get("selector") or "body")

        elif action_type == "scroll":
            result = await action_fn(page, action.get("direction") or "down")

        else:
            result = "Unknown action"

        logger.info(f"Action [{action_type}] executed: {result[:200]}")
        return result

    except Exception as e:
        error_msg = f"Action [{action_type}] failed: {e}"
        logger.warning(error_msg)
        return error_msg  # Return error string rather than raising — let agent decide how to recover
