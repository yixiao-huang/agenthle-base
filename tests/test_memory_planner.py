"""Tests for memory/planner.py — central planner LLM client."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory.planner import call_planner


@pytest.fixture
def mock_openai():
    """Mock AsyncOpenAI client and its chat.completions.create method."""
    with patch("memory.planner.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        # Build mock response: response.choices[0].message.content
        mock_message = MagicMock()
        mock_message.content = "Compacted memory output"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        yield mock_cls, mock_client


def test_default_model(mock_openai):
    """No model arg → uses gpt-4.1-mini."""
    mock_cls, mock_client = mock_openai

    result = asyncio.get_event_loop().run_until_complete(
        call_planner(system_prompt="sys", user_prompt="usr")
    )

    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs.kwargs["model"] == "gpt-4.1-mini"
    assert result == "Compacted memory output"


def test_explicit_model(mock_openai):
    """model='gpt-4.1' → passes that to API."""
    mock_cls, mock_client = mock_openai

    asyncio.get_event_loop().run_until_complete(
        call_planner(system_prompt="sys", user_prompt="usr", model="gpt-4.1")
    )

    call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs.kwargs["model"] == "gpt-4.1"


def test_system_and_user_prompts(mock_openai):
    """Verify prompts are passed correctly to the API."""
    mock_cls, mock_client = mock_openai

    asyncio.get_event_loop().run_until_complete(
        call_planner(
            system_prompt="Merge session learnings into concise memory.",
            user_prompt="Session log: explored floor 3, found key.",
        )
    )

    call_kwargs = mock_client.chat.completions.create.call_args
    messages = call_kwargs.kwargs["messages"]
    assert len(messages) == 2
    assert messages[0] == {
        "role": "system",
        "content": "Merge session learnings into concise memory.",
    }
    assert messages[1] == {
        "role": "user",
        "content": "Session log: explored floor 3, found key.",
    }


def test_returns_content(mock_openai):
    """Returns response.choices[0].message.content."""
    _, mock_client = mock_openai
    mock_client.chat.completions.create.return_value.choices[0].message.content = (
        "Floor 3: key found near stairs"
    )

    result = asyncio.get_event_loop().run_until_complete(
        call_planner(system_prompt="sys", user_prompt="usr")
    )

    assert result == "Floor 3: key found near stairs"


def test_api_error_propagates(mock_openai):
    """OpenAI error not caught — raises to caller."""
    _, mock_client = mock_openai
    mock_client.chat.completions.create = AsyncMock(
        side_effect=Exception("API rate limit exceeded")
    )

    with pytest.raises(Exception, match="API rate limit exceeded"):
        asyncio.get_event_loop().run_until_complete(
            call_planner(system_prompt="sys", user_prompt="usr")
        )
