# CLAUDE.md — AI Browser Automation Agent

This file is the build spec for an AI coding agent (Claude Code, Antigravity, etc.) to implement this project end-to-end. Follow the phases in order — do not build the LangGraph loop before the perception and action layers work standalone, and do not point the agent at a real-world site before it's proven on a stable test target.

---

## 1. Project overview

An AI agent that controls a real web browser to complete tasks given in natural language — navigating, clicking, filling forms, and extracting data — by running a **ReAct loop** (Reason + Act): observe the page, decide the next action, execute it, observe again, repeat until the task is done or a step limit is hit.

```
User task ("find and list 5 remote Python jobs on X site")
  → Browser controller launches/manages a Playwright session
  → Perception: capture simplified page state (DOM text, not raw HTML)
  → Planner: LLM decides ONE next action given task + page state + history
  → Action executor: click / type / navigate / extract / scroll via Playwright
  → loop back to Perception until done=True or step_count exceeds cap
  → Result: structured output (extracted data + full action log)
```

This is fundamentally different from a hardcoded scraper — the agent decides its next move dynamically based on what the page actually renders, so it adapts to layout it hasn't seen before (within reason).

---

## 2. Tech stack (exact)

| Layer | Choice | Notes |
|---|---|---|
| Browser control | Playwright (async API) | Chromium headless by default, headed mode for debugging |
| Orchestration | LangGraph | `StateGraph` with a self-looping conditional edge for the ReAct cycle |
| LLM | OpenAI API | `gpt-4o-mini` for the planner — this task needs fast, cheap, frequent calls, not deep reasoning |
| Page state extraction | Custom DOM simplifier (BeautifulSoup or Playwright's own locators) | Strips scripts/styles/noise, keeps visible text + interactive elements |
| API layer | FastAPI | wraps the agent behind a `/run-task` endpoint |
| Logging | Structured JSON logs per step | your substitute for LangSmith here — logs every (page_state, action, result) triple |
| Containerization | Docker | Playwright's official image handles browser binaries cleanly |

```bash
pip install playwright langgraph langchain-openai fastapi uvicorn beautifulsoup4 python-dotenv
playwright install chromium --with-deps
```

---

## 3. Directory structure

```
browser-agent/
├── app/
│   ├── main.py                  # FastAPI app + /run-task endpoint
│   ├── graph.py                  # LangGraph StateGraph (perceive → plan → act loop)
│   ├── state.py                  # BrowserState TypedDict
│   ├── perception/
│   │   └── dom_simplifier.py     # strips raw HTML down to visible text + interactive elements
│   ├── planner/
│   │   └── planner_agent.py      # LLM node: decides next action
│   ├── actions/
│   │   ├── browser_controller.py # Playwright session lifecycle (launch/close)
│   │   ├── click.py
│   │   ├── type_text.py
│   │   ├── navigate.py
│   │   ├── extract_text.py
│   │   └── scroll.py
│   ├── logging/
│   │   └── step_logger.py        # logs every step for debugging
│   └── config.py                 # env var loading, step caps, timeouts
├── tests/
│   ├── test_perception.py
│   ├── test_actions.py
│   └── test_graph.py
├── Dockerfile
├── requirements.txt
├── .env.example
└── CLAUDE.md
```

---

## 4. Environment variables (`.env.example`)

```
OPENAI_API_KEY=
MAX_STEPS=20
STEP_TIMEOUT_SECONDS=30
HEADLESS=true
LOG_LEVEL=INFO
```

---

## 5. Shared state — `app/state.py`

Build this first. Every node in the graph reads from and returns this object.

```python
from typing import TypedDict, List, Optional, Literal

class ActionRecord(TypedDict):
    step: int
    action_type: str
    target: Optional[str]
    value: Optional[str]
    result_summary: str

class BrowserState(TypedDict):
    task: str
    current_url: str
    page_state: str              # simplified text representation of the page
    action_history: List[ActionRecord]
    step_count: int
    done: bool
    final_result: str
    error: Optional[str]
```

---

## 6. Perception layer — `app/perception/dom_simplifier.py`

**This is the most important design decision in the whole project — get it right before writing any agent logic.**

Two viable approaches:

- **DOM-as-text (start here):** extract visible text plus a list of interactive elements (buttons, links, inputs) with stable identifiers. Cheap, fast, easy to debug.
- **Screenshot-as-image (add later if needed):** feed a screenshot to a vision-capable model. More robust to messy/dynamic DOMs, but slower and costlier per step — treat as a fallback for pages that don't simplify well as text, not the default.

```python
async def simplify_page(page) -> str:
    """Return a compact text representation: visible text + interactive elements."""
    interactive = await page.evaluate("""
        () => Array.from(document.querySelectorAll('button, a, input, select, textarea'))
            .filter(el => el.offsetParent !== null)
            .map(el => ({
                tag: el.tagName.toLowerCase(),
                text: el.innerText?.slice(0, 60) || el.placeholder || '',
                id: el.id || null,
                role: el.getAttribute('role') || null
            }))
    """)
    visible_text = await page.inner_text("body")
    return format_for_llm(visible_text[:2000], interactive[:40])
```

**Never dump raw HTML into the LLM** — it's full of noise (scripts, styles, deeply nested wrapper divs) and will blow up both your context window and your cost per step.

---

## 7. Action space — `app/actions/`

Keep the initial action set small and well-defined. Each is a LangGraph tool bound to the LLM via function calling.

```python
async def click(page, selector: str) -> str:
    await page.click(selector, timeout=5000)
    return f"Clicked {selector}"

async def type_text(page, selector: str, text: str) -> str:
    await page.fill(selector, text)
    return f"Typed into {selector}"

async def navigate(page, url: str) -> str:
    await page.goto(url, wait_until="domcontentloaded")
    return f"Navigated to {url}"

async def extract_text(page, selector: str) -> str:
    return await page.inner_text(selector)

async def scroll(page, direction: Literal["up", "down"]) -> str:
    delta = 800 if direction == "down" else -800
    await page.mouse.wheel(0, delta)
    return f"Scrolled {direction}"
```

**Selector strategy:** prefer semantic locators (`page.get_by_role`, `page.get_by_text`) over brittle CSS class selectors — sites change class names far more often than they change visible text or ARIA roles, so this materially reduces breakage.

**Never use raw `time.sleep()`** for waiting — Playwright's actions already auto-wait for elements to be actionable. Use explicit `wait_for_selector` only when you need to wait on something the action itself doesn't cover (e.g. an async page transition).

---

## 8. Planner node — `app/planner/planner_agent.py`

- **Model:** `gpt-4o-mini`
- **Temperature:** 0.2 (want consistent, non-erratic action choices)
- **Output:** structured JSON — exactly ONE action per step, never free text
- **System prompt:**
```
You control a web browser to complete this task: {task}

Current page state:
{page_state}

Actions taken so far (most recent last):
{action_history}

Choose exactly ONE next action to move closer to completing the task.
Valid actions: click(selector), type_text(selector, text), navigate(url),
extract_text(selector), scroll(direction), or DONE(result) if the task
is fully complete.

Return structured JSON matching the action schema. Do not explain your
reasoning outside the JSON — return only the action.
```

Feeding the **full action history** (not just the latest state) matters — without it the agent can't tell if it already tried something that failed, and will loop on the same mistake.

---

## 9. LangGraph wiring — `app/graph.py`

```python
from langgraph.graph import StateGraph, END
from app.state import BrowserState
from app.perception.dom_simplifier import simplify_page
from app.planner.planner_agent import plan_next_action
from app.actions import execute_action

async def perceive(state: BrowserState) -> BrowserState:
    page_state = await simplify_page(current_page)
    return {**state, "page_state": page_state}

async def plan(state: BrowserState) -> BrowserState:
    action = await plan_next_action(state)
    return {**state, "pending_action": action}

async def act(state: BrowserState) -> BrowserState:
    result = await execute_action(state["pending_action"])
    new_history = state["action_history"] + [result]
    done = state["pending_action"]["type"] == "DONE"
    return {
        **state,
        "action_history": new_history,
        "step_count": state["step_count"] + 1,
        "done": done,
        "final_result": result["result_summary"] if done else state["final_result"],
    }

def should_continue(state: BrowserState) -> str:
    if state["done"] or state["step_count"] >= MAX_STEPS:
        return "end"
    return "perceive"

graph = StateGraph(BrowserState)
graph.add_node("perceive", perceive)
graph.add_node("plan", plan)
graph.add_node("act", act)

graph.set_entry_point("perceive")
graph.add_edge("perceive", "plan")
graph.add_edge("plan", "act")
graph.add_conditional_edges("act", should_continue, {
    "perceive": "perceive",
    "end": END,
})

browser_agent = graph.compile()
```

**The step cap is not optional.** Without it, a confused agent will loop indefinitely clicking the wrong element. Cap at 15–25 steps and fail gracefully with the full action log when hit, rather than hanging.

---

## 10. FastAPI endpoint — `app/main.py`

```python
from fastapi import FastAPI
from app.graph import browser_agent
from app.actions.browser_controller import launch_browser, close_browser

api = FastAPI()

@api.post("/run-task")
async def run_task(task: str, start_url: str):
    page = await launch_browser(headless=True)
    await page.goto(start_url)

    initial_state = {
        "task": task,
        "current_url": start_url,
        "page_state": "",
        "action_history": [],
        "step_count": 0,
        "done": False,
        "final_result": "",
        "error": None,
    }
    result = await browser_agent.ainvoke(initial_state)
    await close_browser(page)

    return {
        "result": result["final_result"],
        "steps_taken": result["step_count"],
        "action_log": result["action_history"],
    }
```

---

## 11. Logging — `app/logging/step_logger.py`

This is your substitute for LangSmith on this project. Log every step as structured JSON — you will need this to debug why the agent clicked the wrong thing.

```python
import json, logging

logger = logging.getLogger("browser_agent")

def log_step(step: int, page_state: str, action: dict, result: str):
    logger.info(json.dumps({
        "step": step,
        "page_state_excerpt": page_state[:300],
        "action": action,
        "result": result,
    }))
```

Log at minimum: the page state snapshot (truncated), the action chosen, and the result — this triple is what you replay when something goes wrong.

---

## 12. Docker

Use Playwright's official base image — it already bundles the correct browser binaries and system dependencies, which is by far the most common source of "works locally, fails in Docker" bugs for this kind of project.

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app/ ./app/
CMD ["uvicorn", "app.main:api", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 13. Operational hardening (build these before calling it done)

- **Step cap:** 15–25 steps max, fail gracefully with the full action log on hit
- **Per-action timeout:** 30s — a hung page interaction fails that step rather than blocking the whole run
- **Retry on transient failures:** 1–2 retries with a short backoff on navigation/click failures (e.g. element not yet rendered), not on logical planner mistakes
- **Selector fallback:** if a semantic locator fails, log it clearly rather than silently failing — this is usually the first sign a target site changed its layout
- **Rate limiting / politeness:** throttle requests to any single domain, respect `robots.txt` where relevant, and avoid targeting sites whose terms of service explicitly disallow automation — pick demo targets you control or that permit it
- **Context window control:** cap page_state text length (e.g. 2000 chars) and interactive element list length (e.g. 40 elements) so a dense page doesn't blow the planner's context

---

## 14. Build order (do it in this sequence)

1. `state.py` — shared state schema
2. Playwright standalone script — prove `goto`, `click`, `fill`, `inner_text` work manually against a real page, no agent logic yet
3. `dom_simplifier.py` — build and manually inspect its output against 2-3 different test pages before trusting it
4. Action functions (`click`, `type_text`, `navigate`, `extract_text`, `scroll`) — test each standalone
5. Planner prompt + structured output — test with a hardcoded `page_state` string, no live browser yet, to iterate on the prompt cheaply
6. `graph.py` — wire perceive → plan → act into a self-looping LangGraph graph, test end-to-end on a simple, stable demo site (a form you control, or Wikipedia)
7. Step logging — add structured logging before doing any real debugging
8. FastAPI endpoint — wrap the graph behind `/run-task`
9. Docker — containerize using Playwright's official base image
10. Hardening — step caps, timeouts, retries, rate limiting — last, once the happy path works end to end on your test site

Do not point this at a real-world target site (job boards, e-commerce) until it reliably completes tasks on a simple, stable test site first — real sites add anti-bot measures, dynamic content, and layout quirks that will make debugging your core loop much harder than it needs to be.

---

## 15. Cost and performance expectation

Each step costs one `gpt-4o-mini` call — cheap individually, but a 15-step run at even a few cents worth of tokens per call adds up if you're testing repeatedly. Cache nothing here (unlike the research assistant) since page state changes every step by nature — the cost lever in this project is keeping `page_state` compact, not caching, since a bloated DOM dump is the main thing that drives up both cost and planner confusion.
