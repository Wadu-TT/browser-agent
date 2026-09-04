"""
app/planner/planner_agent.py — LLM planner using Groq API (free tier).

Uses langchain-groq with llama-3.3-70b-versatile to decide the next action
given the current page state and action history.

Groq free tier limits:
  - 30 requests/minute
  - 14,400 requests/day
  - 131,072 tokens/minute
Each step costs 1 request + ~500-1500 tokens.
"""

import json
import logging
import asyncio
from typing import Any

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from app.config import settings
from app.state import BrowserState

logger = logging.getLogger("browser_agent.planner")

# ── Pydantic schema for structured action output ───────────────────────────────

class AgentAction(BaseModel):
    """The action the agent decides to take next."""
    type: str = Field(
        description=(
            "One of: click, type_text, navigate, extract_text, scroll, DONE"
        )
    )
    selector: str | None = Field(
        default=None,
        description="CSS selector, text, or element identifier for click/type_text/extract_text",
    )
    text: str | None = Field(
        default=None,
        description="Text to type, only used when type=type_text",
    )
    url: str | None = Field(
        default=None,
        description="Full URL to navigate to, only used when type=navigate",
    )
    direction: str | None = Field(
        default=None,
        description="'up' or 'down', only used when type=scroll",
    )
    result: str | None = Field(
        default=None,
        description="Final result/answer to return to the user, only used when type=DONE",
    )
    reasoning: str | None = Field(
        default=None,
        description="Brief one-sentence explanation of why this action was chosen",
    )


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an AI agent that controls a web browser to complete tasks.

You will receive:
1. The TASK you must complete
2. The current PAGE STATE (URL, visible text, interactive elements)
3. The ACTION HISTORY (what you've done so far, including text you already extracted)

Your job is to decide exactly ONE next action.

Available actions:
- navigate(url): Go to a URL.
- click(selector): Click a button, link, or element.
- type_text(selector, text): Type into an input field.
- extract_text(selector): Extract text from an element. Use "body" for the full page.
- scroll(direction): Scroll "up" or "down".
- DONE(result): STOP and return the final answer.

=== CRITICAL RULES ===
1. **CALL DONE IMMEDIATELY** when you have the information the task asked for.
   - Check the ACTION HISTORY. If a previous extract_text already returned the answer, call DONE NOW with that text.
   - Do NOT keep extracting or scrolling if you already have the answer.
2. If you have tried the same selector 2+ times and it failed, move on — try "body" or a different approach.
3. For extraction tasks: try extract_text("body") if specific selectors fail — body always works.
4. Output ONLY valid JSON — no markdown, no explanation outside the JSON.
5. The "result" field in DONE must contain the actual extracted text, not a description.
"""

# ── LLM setup ─────────────────────────────────────────────────────────────────

def _get_llm() -> ChatGroq:
    """Return a configured Groq LLM with structured output."""
    return ChatGroq(
        model=settings.GROQ_MODEL,
        temperature=0.2,
        groq_api_key=settings.GROQ_API_KEY,
        max_retries=2,
    ).with_structured_output(AgentAction)


# ── Core planner function ──────────────────────────────────────────────────────

async def plan_next_action(state: BrowserState) -> dict[str, Any]:
    """
    Call the Groq LLM to decide the next action.

    Returns:
        Action dict compatible with execute_action() dispatcher.
    """
    task = state["task"]
    page_state = state["page_state"]
    action_history = state["action_history"]
    step_count = state["step_count"]

    # Format action history for the prompt
    history_text = _format_history(action_history)

    human_prompt = f"""TASK: {task}

CURRENT PAGE STATE:
{page_state}

ACTIONS TAKEN SO FAR ({step_count} steps):
{history_text}

Decide the next single action to take."""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=human_prompt),
    ]

    logger.info(f"Step {step_count}: Calling Groq LLM ({settings.GROQ_MODEL})")

    # Retry on rate limit (429) with backoff
    for attempt in range(3):
        try:
            llm = _get_llm()
            # Use ainvoke for native async (avoids run_in_executor issues on Windows)
            action: AgentAction = await llm.ainvoke(messages)
            logger.info(
                f"Step {step_count}: Planned action={action.type!r} "
                f"reasoning={action.reasoning!r}"
            )
            return action.model_dump()

        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                wait = 2 ** attempt * 10  # 10s, 20s, 40s
                logger.warning(f"Groq rate limit hit. Waiting {wait}s (attempt {attempt+1}/3)")
                await asyncio.sleep(wait)
            else:
                logger.error(f"LLM call failed: {e}")
                raise

    raise RuntimeError("Groq API rate limit exceeded after 3 retries. Try again later.")


def _format_history(action_history: list[dict]) -> str:
    """Format the action history into a readable string for the LLM.
    Highlights successful extract_text results so the model sees when it already has the answer.
    """
    if not action_history:
        return "None -- this is the first step."

    lines = []
    extracted_data = []  # collect all successful extractions

    for record in action_history[-15:]:
        step = record.get("step", "?")
        action_type = record.get("action_type", "?")
        target = record.get("target") or ""
        result = record.get("result_summary", "")

        if action_type == "extract_text" and result and not result.startswith("Could not"):
            # Show extracted text very prominently
            preview = result[:400]
            line = (
                f"Step {step}: EXTRACT_TEXT -> {target!r}\n"
                f"  *** EXTRACTED DATA: {preview!r} ***"
            )
            extracted_data.append(preview)
        else:
            line = f"Step {step}: {action_type}"
            if target:
                line += f" -> {target!r}"
            result_preview = result[:120]
            if result_preview:
                line += f"\n  Result: {result_preview}"

        lines.append(line)

    history_str = "\n".join(lines)

    # If there is already extracted data, add a prominent banner
    if extracted_data:
        latest = extracted_data[-1]
        history_str = (
            "=== DATA ALREADY EXTRACTED (call DONE if this answers the task) ===\n"
            f"{latest[:300]}\n"
            "=== END EXTRACTED DATA ===\n\n"
            f"FULL HISTORY:\n{history_str}"
        )

    return history_str
