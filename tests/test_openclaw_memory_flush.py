"""Tests for memory flush helper wiring (US-OC-020)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from cua_bench.agents.openclaw.memory_flush import run_memory_flush


def _mock_flush_response(content: str = "<silent>") -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    choice.message.tool_calls = []
    response = MagicMock()
    response.choices = [choice]
    return response


class _SessionManagerStub:
    def __init__(self):
        self.appended = []
        self.flush_recorded = False

    def load_history(self):
        return []

    def append_message(self, role, content, **kwargs):
        self.appended.append((role, content, kwargs))

    def record_memory_flush(self):
        self.flush_recorded = True


class _MemoryStoreStub:
    def write_task_memory(self, content):
        self.last_task_memory = content

    def append_to_session_log(self, content):
        self.last_session_content = content


class TestRunMemoryFlush:
    def test_passes_thinking_params_to_litellm(self):
        session_mgr = _SessionManagerStub()
        memory_store = _MemoryStoreStub()
        mock_resp = _mock_flush_response()

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp) as mock_acomp:
            asyncio.get_event_loop().run_until_complete(
                run_memory_flush(
                    summary_model="anthropic/claude-sonnet-4-6-20260101",
                    session_mgr=session_mgr,
                    memory_store=memory_store,
                    flush_prompt="Flush now",
                    flush_system_prompt="system",
                    silent_token="<silent>",
                    thinking_params={"thinking": {"type": "enabled", "budget_tokens": 5000}},
                )
            )

        assert session_mgr.flush_recorded is True
        assert mock_acomp.call_args.kwargs["thinking"] == {
            "type": "enabled",
            "budget_tokens": 5000,
        }
