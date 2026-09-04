"""
run.py — Windows-compatible server launcher.

WHY THIS APPROACH:
  Playwright needs ProactorEventLoop on Windows to spawn browser subprocesses.
  The only reliable way to ensure this is to:
  1. Set WindowsProactorEventLoopPolicy so asyncio.run() creates a ProactorLoop.
  2. Use uvicorn.Server().serve() — an async method — so uvicorn runs INSIDE
     our already-created ProactorEventLoop instead of creating its own.

  uvicorn.run() (the sync version) creates its own event loop, ignoring ours.
  uvicorn.Server.serve() (the async version) uses the CALLER's event loop.

Usage:
    python run.py
"""

import sys
import asyncio

# ── MUST be first — sets the policy used by asyncio.run() below ───────────────
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn


async def serve():
    """Run uvicorn inside the current (Proactor) event loop."""
    config = uvicorn.Config(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False,   # reload spawns child process -> resets loop policy
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    # asyncio.run() creates a ProactorEventLoop (because of the policy above)
    # and runs serve() inside it. uvicorn.Server.serve() uses that same loop.
    asyncio.run(serve())
