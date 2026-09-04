"""tests/test_perception.py — Unit tests for the DOM simplifier."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.perception.dom_simplifier import simplify_page, _clean_text, _format_page_state


def test_clean_text_removes_blank_lines():
    raw = "Hello\n\n\nWorld\n  \n  "
    result = _clean_text(raw)
    assert result == "Hello\nWorld"


def test_clean_text_strips_whitespace():
    raw = "  Hello  \n  World  "
    result = _clean_text(raw)
    assert result == "Hello\nWorld"


def test_format_page_state_structure():
    result = _format_page_state(
        url="https://example.com",
        title="Test Page",
        body_text="Welcome to example",
        interactive=[
            {"tag": "button", "text": "Submit", "id": "submit-btn", "role": None, "placeholder": None, "href": None},
        ],
    )
    assert "=== PAGE STATE ===" in result
    assert "URL: https://example.com" in result
    assert "TITLE: Test Page" in result
    assert "Welcome to example" in result
    assert "[1]" in result
    assert "button" in result
    assert "Submit" in result


@pytest.mark.asyncio
async def test_simplify_page_calls_evaluate():
    """Test that simplify_page calls the right Playwright methods."""
    mock_page = AsyncMock()
    mock_page.url = "https://example.com"
    mock_page.title = AsyncMock(return_value="Example")
    mock_page.inner_text = AsyncMock(return_value="Some visible text on the page")
    mock_page.evaluate = AsyncMock(side_effect=[
        "Some visible text on the page",
        [{"tag": "button", "text": "Click me", "id": "btn1", "role": None, "placeholder": None, "href": None}]
    ])

    result = await simplify_page(mock_page)

    assert "https://example.com" in result
    assert "Example" in result
    assert "Some visible text" in result
    assert "Click me" in result
