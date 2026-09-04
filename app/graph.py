"""
app/graph.py — LangGraph StateGraph: the ReAct loop.

Node sequence:
    perceive → plan_and_act → (should_continue?) → perceive | END

IMPORTANT: LangGraph 0.1.x validates node return keys against the TypedDict at
compile time. To avoid 'Must write to at least one of [...]' errors, nodes can
ONLY return keys defined in BrowserState. The original plan+act split required
a 'pending_action' intermediate key — instead we merge plan+act into one node
so the action never needs to live in the state.
"""

import logging
from langgraph.graph import StateGraph, END

from app.state import BrowserState
from app.config import settings
from app.perception.dom_simplifier import simplify_page
from app.planner.planner_agent import plan_next_action
from app.actions import execute_action
from app.actions.browser_controller import get_page
from app.logging.step_logger import log_step

logger = logging.getLogger("browser_agent.graph")


# ── Graph nodes ───────────────────────────────────────────────────────────────

async def perceive(state: BrowserState) -> dict:
    """
    Observation node: capture the current page state as a compact text string.
    Returns only BrowserState keys: page_state, current_url.
    """
    page = get_page()
    page_state = await simplify_page(page)
    current_url = page.url

    logger.info(f"Step {state['step_count']}: Perceived page — {current_url}")
    return {
        "page_state": page_state,
        "current_url": current_url,
    }


async def plan_and_act(state: BrowserState) -> dict:
    """
    Combined plan+act node: calls the LLM to decide the next action, then
    executes it immediately. Returns only valid BrowserState keys.

    Merging plan+act avoids needing a 'pending_action' intermediate key in
    BrowserState, which LangGraph 0.1.x would reject at the write step.
    """
    page = get_page()
    step = state["step_count"]

    # ── Plan: ask LLM for the next action ────────────────────────────────────
    action = await plan_next_action(state)
    logger.info(f"Step {step}: Planned action={action.get('type')!r} reasoning={action.get('reasoning', '')!r}")

    # ── Act: execute it ───────────────────────────────────────────────────────
    result_summary = await execute_action(page, action)

    # ── Log ───────────────────────────────────────────────────────────────────
    log_step(
        step=step,
        page_state=state["page_state"],
        action=action,
        result=result_summary,
        current_url=page.url,
    )

    # ── Build updated state (only valid BrowserState keys) ────────────────────
    new_record = {
        "step": step,
        "action_type": action.get("type", "unknown"),
        "target": action.get("selector") or action.get("url") or action.get("direction"),
        "value": action.get("text") or action.get("result"),
        "result_summary": result_summary,
    }

    new_history = state["action_history"] + [new_record]
    done = action.get("type", "").upper() == "DONE"
    final_result = action.get("result", "") if done else state["final_result"]

    return {
        "action_history": new_history,
        "step_count": step + 1,
        "done": done,
        "final_result": final_result,
        "error": None,
    }


def should_continue(state: BrowserState) -> str:
    """
    Conditional edge: loop back to perceive, or end the run.
    Ends when: agent signals done=True, OR step cap is reached.
    """
    if state["done"]:
        logger.info(f"Task completed after {state['step_count']} steps.")
        return "end"

    if state["step_count"] >= settings.MAX_STEPS:
        logger.warning(
            f"Step cap reached ({settings.MAX_STEPS}). Ending. "
            f"Last action: {state['action_history'][-1] if state['action_history'] else 'none'}"
        )
        return "end"

    return "perceive"


# ── Build the graph ───────────────────────────────────────────────────────────

def build_graph():
    """Compile and return the LangGraph ReAct loop."""
    graph = StateGraph(BrowserState)

    graph.add_node("perceive", perceive)
    graph.add_node("plan_and_act", plan_and_act)

    graph.set_entry_point("perceive")
    graph.add_edge("perceive", "plan_and_act")
    graph.add_conditional_edges(
        "plan_and_act",
        should_continue,
        {
            "perceive": "perceive",
            "end": END,
        },
    )

    return graph.compile()


# Module-level compiled agent — import this in main.py
browser_agent = build_graph()
