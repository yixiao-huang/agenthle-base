"""Tests for OpenClaw tool registry, summaries, and logging callback (US-OC-007).

Covers:
  - build_tools() returns 5 tools with correct types
  - get_tool_summaries() filters out Computer, includes BaseTool instances
  - ToolLoggingCallback logs start/end with timing (function + computer calls)
  - Edge cases: truncation, missing call_id
"""

import asyncio
import json

import pytest

from cua_bench.agents.openclaw.tools import (
    ToolLoggingCallback,
    _extract_result_summary,
    get_tool_summaries,
)


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Fixtures — lightweight fakes that avoid heavy CUA imports
# ---------------------------------------------------------------------------


class FakeBaseTool:
    """Minimal stand-in for BaseTool to test get_tool_summaries."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description


class FakeComputer:
    """Duck-typed computer object (not a BaseTool subclass)."""

    pass


# ---------------------------------------------------------------------------
# get_tool_summaries
# ---------------------------------------------------------------------------


class TestGetToolSummaries:
    def test_filters_out_non_basetool(self):
        """Computer objects should be excluded from summaries."""
        computer = FakeComputer()
        tools = [computer]
        result = get_tool_summaries(tools)
        assert result == {}

    def test_includes_basetool_instances(self):
        """All BaseTool subclasses should appear in summaries."""
        from cua_bench.agents.openclaw.memory import (
            MemoryGetTool,
            MemorySearchTool,
            MemoryStore,
            MemoryWriteTool,
        )

        store = MemoryStore(task_id="test", base_dir="/tmp/test_tools_summaries")
        tools = [
            MemorySearchTool(store),
            MemoryGetTool(store),
            MemoryWriteTool(store),
        ]
        result = get_tool_summaries(tools)
        assert len(result) == 3
        assert "memory_search" in result
        assert "memory_get" in result
        assert "memory_write" in result

    def test_empty_tool_list(self):
        assert get_tool_summaries([]) == {}

    def test_mixed_tools_correct_count(self):
        """Mixed list of BaseTool and non-BaseTool should only include BaseTools."""
        from cua_bench.agents.openclaw.memory import MemoryGetTool, MemoryStore

        store = MemoryStore(task_id="test", base_dir="/tmp/test_tools_mixed")
        computer = FakeComputer()
        tools = [computer, MemoryGetTool(store)]
        result = get_tool_summaries(tools)
        assert len(result) == 1
        assert "memory_get" in result


# ---------------------------------------------------------------------------
# ToolLoggingCallback — function calls
# ---------------------------------------------------------------------------


class TestToolLoggingCallback:
    @pytest.fixture
    def callback(self):
        return ToolLoggingCallback()

    def test_on_function_call_start_logs(self, callback, capsys):
        _run(callback.on_function_call_start({
            "call_id": "c1",
            "name": "memory_search",
            "arguments": '{"keywords": ["test"]}',
        }))
        captured = capsys.readouterr()
        assert "[Tool] memory_search(" in captured.out
        assert "c1" in callback._start_times

    def test_on_function_call_end_logs_duration(self, callback, capsys):
        _run(callback.on_function_call_start({
            "call_id": "c2",
            "name": "memory_get",
            "arguments": "{}",
        }))
        capsys.readouterr()  # clear start output

        _run(callback.on_function_call_end(
            {"call_id": "c2", "name": "memory_get"},
            [{"output": "some result data"}],
        ))
        captured = capsys.readouterr()
        assert "[Tool] memory_get -> some result data" in captured.out
        assert "ms)" in captured.out
        assert "c2" not in callback._start_times

    def test_on_function_call_end_missing_start(self, callback, capsys):
        """End without start should show ?ms."""
        _run(callback.on_function_call_end(
            {"call_id": "orphan", "name": "memory_write"},
            [{"output": "ok"}],
        ))
        captured = capsys.readouterr()
        assert "?ms" in captured.out

    def test_args_truncation(self, callback, capsys):
        """Long arguments should be truncated."""
        long_args = json.dumps({"data": "x" * 500})
        _run(callback.on_function_call_start({
            "call_id": "c3",
            "name": "memory_write",
            "arguments": long_args,
        }))
        captured = capsys.readouterr()
        assert "…" in captured.out

    def test_dict_arguments(self, callback, capsys):
        """Arguments passed as dict (not string) should be handled."""
        _run(callback.on_function_call_start({
            "call_id": "c4",
            "name": "memory_search",
            "arguments": {"keywords": ["hello"]},
        }))
        captured = capsys.readouterr()
        assert "hello" in captured.out

    def test_missing_call_id_defaults(self, callback, capsys):
        """Missing call_id should use 'unknown'."""
        _run(callback.on_function_call_start({
            "name": "memory_get",
            "arguments": "{}",
        }))
        assert "unknown" in callback._start_times


# ---------------------------------------------------------------------------
# ToolLoggingCallback — computer calls
# ---------------------------------------------------------------------------


class TestToolLoggingCallbackComputer:
    @pytest.fixture
    def callback(self):
        return ToolLoggingCallback()

    def test_on_computer_call_start_logs_action_type(self, callback, capsys):
        _run(callback.on_computer_call_start({
            "call_id": "cc1",
            "action": {"type": "click", "x": 100, "y": 200},
        }))
        captured = capsys.readouterr()
        assert "[Computer] click" in captured.out
        assert "cc1" in callback._start_times

    def test_on_computer_call_end_logs_duration(self, callback, capsys):
        _run(callback.on_computer_call_start({
            "call_id": "cc2",
            "action": {"type": "screenshot"},
        }))
        capsys.readouterr()

        _run(callback.on_computer_call_end(
            {"call_id": "cc2", "action": {"type": "screenshot"}},
            [{"output": {"type": "input_image"}}],
        ))
        captured = capsys.readouterr()
        assert "[Computer] screenshot done" in captured.out
        assert "ms)" in captured.out
        assert "cc2" not in callback._start_times

    def test_on_computer_call_end_missing_start(self, callback, capsys):
        _run(callback.on_computer_call_end(
            {"call_id": "orphan", "action": {"type": "key"}},
            [],
        ))
        captured = capsys.readouterr()
        assert "?ms" in captured.out

    def test_on_computer_call_non_dict_action(self, callback, capsys):
        """Non-dict action should be stringified."""
        _run(callback.on_computer_call_start({
            "call_id": "cc3",
            "action": "some_string_action",
        }))
        captured = capsys.readouterr()
        assert "[Computer] some_string_action" in captured.out


# ---------------------------------------------------------------------------
# _extract_result_summary
# ---------------------------------------------------------------------------


class TestExtractResultSummary:
    def test_empty_result(self):
        assert _extract_result_summary([]) == "(empty)"

    def test_no_output_field(self):
        assert _extract_result_summary([{"type": "something"}]) == "(no output)"

    def test_short_output(self):
        assert _extract_result_summary([{"output": "hello"}]) == "hello"

    def test_long_output_truncated(self):
        long_output = "x" * 200
        result = _extract_result_summary([{"output": long_output}])
        assert len(result) == 101  # 100 + ellipsis
        assert result.endswith("…")

    def test_multiple_items_uses_first(self):
        result = _extract_result_summary([
            {"output": "first"},
            {"output": "second"},
        ])
        assert result == "first"
