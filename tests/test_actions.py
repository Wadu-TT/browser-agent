"""tests/test_actions.py — Unit tests for individual action functions."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.actions import execute_action
from app.actions.navigate import navigate
from app.actions.scroll import scroll


@pytest.mark.asyncio
async def test_navigate_adds_https():
    """navigate() should prepend https:// if missing."""
    mock_page = AsyncMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_page.goto = AsyncMock(return_value=mock_response)
    mock_page.url = "https://example.com"

    result = await navigate(mock_page, "example.com")  # no scheme

    # Should have called goto with https://
    call_args = mock_page.goto.call_args[0][0]
    assert call_args.startswith("https://")
    assert "Navigated to" in result


@pytest.mark.asyncio
async def test_navigate_keeps_https():
    """navigate() should not double-add https://."""
    mock_page = AsyncMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_page.goto = AsyncMock(return_value=mock_response)
    mock_page.url = "https://example.com"

    await navigate(mock_page, "https://example.com")
    call_args = mock_page.goto.call_args[0][0]
    assert call_args == "https://example.com"


@pytest.mark.asyncio
async def test_scroll_down():
    mock_page = AsyncMock()
    mock_page.mouse = AsyncMock()
    mock_page.mouse.wheel = AsyncMock()

    result = await scroll(mock_page, "down")
    mock_page.mouse.wheel.assert_called_once_with(0, 800)
    assert "down" in result


@pytest.mark.asyncio
async def test_scroll_up():
    mock_page = AsyncMock()
    mock_page.mouse = AsyncMock()
    mock_page.mouse.wheel = AsyncMock()

    result = await scroll(mock_page, "up")
    mock_page.mouse.wheel.assert_called_once_with(0, -800)
    assert "up" in result


@pytest.mark.asyncio
async def test_scroll_invalid_direction():
    mock_page = AsyncMock()
    mock_page.mouse = AsyncMock()

    with pytest.raises(ValueError, match="Invalid scroll direction"):
        await scroll(mock_page, "sideways")  # type: ignore


@pytest.mark.asyncio
async def test_execute_action_done():
    """DONE action should return the result string directly."""
    mock_page = AsyncMock()
    action = {"type": "DONE", "result": "Task is complete!"}
    result = await execute_action(mock_page, action)
    assert result == "Task is complete!"


@pytest.mark.asyncio
async def test_execute_action_unknown_type():
    """Unknown action type should raise ValueError."""
    mock_page = AsyncMock()
    action = {"type": "fly", "selector": "#wings"}
    with pytest.raises(ValueError, match="Unknown action type"):
        await execute_action(mock_page, action)
