"""tests/test_graph.py — Integration tests for the LangGraph agent."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.state import BrowserState


def make_state(**overrides) -> BrowserState:
    """Create a minimal BrowserState for testing."""
    base: BrowserState = {
        "task": "Test task",
        "current_url": "https://example.com",
        "page_state": "=== PAGE STATE ===\nURL: https://example.com\nTITLE: Test",
        "action_history": [],
        "step_count": 0,
        "done": False,
        "final_result": "",
        "error": None,
    }
    base.update(overrides)  # type: ignore
    return base


def test_should_continue_done():
    """should_continue returns 'end' when done=True."""
    from app.graph import should_continue
    state = make_state(done=True, step_count=3)
    assert should_continue(state) == "end"


def test_should_continue_step_cap(monkeypatch):
    """should_continue returns 'end' when step cap is reached."""
    from app import graph as graph_module
    from app.graph import should_continue

    # Patch MAX_STEPS
    monkeypatch.setattr(graph_module.settings, "MAX_STEPS", 5)
    state = make_state(done=False, step_count=5)
    assert should_continue(state) == "end"


def test_should_continue_loops():
    """should_continue returns 'perceive' when not done and under step cap."""
    from app.graph import should_continue
    state = make_state(done=False, step_count=2)
    # Default MAX_STEPS is 20, so step 2 should loop
    result = should_continue(state)
    assert result == "perceive"


@pytest.mark.asyncio
async def test_perceive_updates_state():
    """perceive node should update page_state and current_url."""
    from app.graph import perceive

    mock_page = AsyncMock()
    mock_page.url = "https://new-url.com"
    mock_page.title = AsyncMock(return_value="New Page")
    mock_page.inner_text = AsyncMock(return_value="Page content here")
    mock_page.evaluate = AsyncMock(return_value=[])
    mock_page.is_closed = MagicMock(return_value=False)

    with patch("app.graph.get_page", return_value=mock_page):
        state = make_state()
        result = await perceive(state)

    assert result["current_url"] == "https://new-url.com"
    assert "PAGE STATE" in result["page_state"]
