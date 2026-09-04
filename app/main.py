"""
app/main.py — FastAPI entrypoint.

Endpoints:
    GET  /health         — liveness check (used by Render.com to detect startup)
    POST /run-task       — run the browser agent on a given task
    GET  /docs           — auto-generated Swagger UI (built into FastAPI)
"""

import sys
import asyncio
import logging
from contextlib import asynccontextmanager

# ── Windows asyncio fix ───────────────────────────────────────────────────────
# Playwright uses asyncio.create_subprocess_exec internally to spawn the browser
# process. On Windows, the default SelectorEventLoop does NOT support subprocess
# creation — only the ProactorEventLoop does. Without this fix you get:
#   NotImplementedError from asyncio.base_events._make_subprocess_transport
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl

from app.config import settings, setup_logging
from app.graph import browser_agent
from app.actions.browser_controller import launch_browser, close_browser
from app.logging.step_logger import log_run_start, log_run_end

# Configure logging on startup
setup_logging()
logger = logging.getLogger("browser_agent.api")


# ── Request / Response models ─────────────────────────────────────────────────

class TaskRequest(BaseModel):
    task: str
    start_url: str = "https://www.google.com"
    headless: bool = True
    max_steps: int | None = None

    model_config = {"json_schema_extra": {
        "example": {
            "task": "Search for 'Python jobs remote' on Google and list the first 3 results",
            "start_url": "https://www.google.com",
            "headless": True,
        }
    }}


class TaskResponse(BaseModel):
    success: bool
    result: str
    steps_taken: int
    action_log: list[dict]
    error: str | None = None


# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate config on startup."""
    try:
        settings.validate()
        logger.info(
            f"Browser Agent starting | model={settings.GROQ_MODEL} "
            f"| max_steps={settings.MAX_STEPS}"
        )
    except ValueError as e:
        logger.error(f"Startup validation failed: {e}")
        raise
    yield
    logger.info("Browser Agent shutting down")


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Browser Automation Agent",
    description=(
        "An AI agent that controls a real web browser using natural language instructions. "
        "Powered by Groq (llama-3.3-70b-versatile) + Playwright + LangGraph."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Allow cross-origin requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    """Liveness probe — returns 200 if the server is running."""
    return {
        "status": "healthy",
        "model": settings.GROQ_MODEL,
        "max_steps": settings.MAX_STEPS,
    }


@app.post("/run-task", response_model=TaskResponse, tags=["Agent"])
async def run_task(request: TaskRequest):
    """
    Run the browser agent on a task.

    The agent will:
    1. Launch a Chromium browser
    2. Navigate to start_url
    3. Run the ReAct loop (perceive → plan → act) until done or step cap
    4. Return the result + full action log
    """
    # Override step cap per-request if provided
    if request.max_steps:
        settings.MAX_STEPS = request.max_steps

    page = None
    log_run_start(request.task, request.start_url)

    try:
        # Launch browser
        page = await launch_browser(headless=request.headless)
        await page.goto(request.start_url, wait_until="domcontentloaded", timeout=30_000)

        # Build initial state
        initial_state = {
            "task": request.task,
            "current_url": request.start_url,
            "page_state": "",
            "action_history": [],
            "step_count": 0,
            "done": False,
            "final_result": "",
            "error": None,
        }

        # Run the agent graph
        # recursion_limit: each agent step = 2 LangGraph recursions (perceive + plan_and_act)
        # We set it to MAX_STEPS * 3 to give plenty of headroom
        recursion_limit = (request.max_steps or settings.MAX_STEPS) * 3
        logger.info(f"Starting agent run: task={request.task!r}")
        final_state = await browser_agent.ainvoke(
            initial_state,
            config={"recursion_limit": recursion_limit},
        )

        success = final_state["done"] and not final_state.get("error")
        result = final_state["final_result"] or (
            "Task ended (step cap reached)" if not final_state["done"] else "Done"
        )

        log_run_end(
            task=request.task,
            steps_taken=final_state["step_count"],
            success=success,
            final_result=result,
        )

        return TaskResponse(
            success=success,
            result=result,
            steps_taken=final_state["step_count"],
            action_log=final_state["action_history"],
            error=final_state.get("error"),
        )

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Agent run failed: {error_msg}", exc_info=True)
        log_run_end(
            task=request.task,
            steps_taken=0,
            success=False,
            final_result="",
            error=error_msg,
        )
        raise HTTPException(status_code=500, detail=error_msg)

    finally:
        if page:
            await close_browser()


# ── Serve frontend ────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the frontend UI."""
    return FileResponse("frontend/index.html")
