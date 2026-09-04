"""
app/logging/step_logger.py — Structured JSON step logger.

Logs every (step, page_state_excerpt, action, result) triple as structured JSON.
This is the substitute for LangSmith — use this to debug why the agent
clicked the wrong thing or got stuck in a loop.

Log format:
    {
        "timestamp": "...",
        "step": 3,
        "page_state_excerpt": "=== PAGE STATE ===\nURL: ...",
        "action": {"type": "click", "selector": "Sign in", ...},
        "result": "Clicked element with text: Sign in",
        "current_url": "https://example.com/login"
    }
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger("browser_agent.steps")


def log_step(
    step: int,
    page_state: str,
    action: dict,
    result: str,
    current_url: str = "",
) -> None:
    """
    Log a single agent step as structured JSON.

    Args:
        step:        Current step number
        page_state:  Full page state string (will be truncated in log)
        action:      Action dict returned by the planner
        result:      Result string from action execution
        current_url: Current browser URL at time of logging
    """
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "step": step,
        "current_url": current_url,
        "page_state_excerpt": (page_state or "")[:400],
        "action": {
            "type": action.get("type"),
            "selector": action.get("selector"),
            "text": (action.get("text") or "")[:100] if action.get("text") else None,
            "url": action.get("url"),
            "direction": action.get("direction"),
            "reasoning": (action.get("reasoning") or "")[:200] if action.get("reasoning") else None,
        },
        "result": (result or "")[:300],
    }
    logger.info(json.dumps(entry))


def log_run_start(task: str, start_url: str) -> None:
    """Log the start of a new agent run."""
    entry = {
        "event": "run_start",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "task": task,
        "start_url": start_url,
    }
    logger.info(json.dumps(entry))


def log_run_end(
    task: str,
    steps_taken: int,
    success: bool,
    final_result: str,
    error: str | None = None,
) -> None:
    """Log the end of an agent run (success or failure)."""
    entry = {
        "event": "run_end",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "task": task,
        "steps_taken": steps_taken,
        "success": success,
        "final_result": (final_result or "")[:500],
        "error": error,
    }
    logger.info(json.dumps(entry))
