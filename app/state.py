"""
app/state.py — Shared BrowserState TypedDict used across all LangGraph nodes.

Every node in the graph reads from and returns a BrowserState object.
The page Playwright object is NOT stored here (not serializable) — it's
managed as a module-level singleton in browser_controller.py.
"""

from typing import TypedDict, List, Optional, Literal


class ActionRecord(TypedDict):
    """A record of a single action taken by the agent."""
    step: int
    action_type: str            # "click" | "type_text" | "navigate" | "extract_text" | "scroll" | "DONE"
    target: Optional[str]       # selector or URL
    value: Optional[str]        # text to type, scroll direction, etc.
    result_summary: str         # human-readable outcome of the action


class BrowserState(TypedDict):
    """The full agent state passed between LangGraph nodes."""
    task: str                           # original user task
    current_url: str                    # current browser URL
    page_state: str                     # simplified DOM text for LLM
    action_history: List[ActionRecord]  # full log of all actions taken
    step_count: int                     # number of steps completed
    done: bool                          # True when agent signals task complete
    final_result: str                   # extracted result / answer
    error: Optional[str]                # last error message if any
