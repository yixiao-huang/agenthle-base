"""Tests for _normalize_messages_for_gpt54 (US-OC-037).

Covers the 7+ code paths in the normalization function:
  - Already-valid Responses API items (passthrough)
  - computer_call_output (strip acknowledged_safety_checks)
  - String content wrapping (user vs assistant text types)
  - Text block conversion (text → input_text/output_text)
  - computer_call expansion (single action, batched actions, stale empty)
  - function_call expansion
  - tool_result → function_call_output conversion
  - Already-valid content block types (input_text, output_text, etc.)
  - Unknown block types (serialized as text)
"""

import json

from agent.loops.openai import (
    _drop_opaque_reasoning_segments,
    _normalize_messages_for_gpt54,
    _repair_reasoning_item_pairing,
)


# ---------------------------------------------------------------------------
# Passthrough: items that already have a Responses API "type" (no "role")
# ---------------------------------------------------------------------------


class TestPassthrough:
    def test_responses_api_item_passes_through(self):
        item = {"type": "computer_call", "call_id": "c1", "action": {"type": "click"}}
        result = _normalize_messages_for_gpt54([item])
        assert result == [item]

    def test_top_level_reasoning_item_passes_through_for_pairing_repair(self):
        """Reasoning survives normalization and is handled by the pairing repair step."""
        item = {
            "type": "reasoning",
            "id": "rs_1",
            "summary": [{"type": "summary_text", "text": "internal"}],
        }
        result = _normalize_messages_for_gpt54([item])
        assert result == [item]


class TestReasoningPairRepair:
    def test_reasoning_kept_adjacent_to_function_call(self):
        items = [
            {"type": "reasoning", "id": "rs_1"},
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "flush"}]},
            {"type": "function_call", "call_id": "fc_1", "name": "memory_search", "arguments": "{}"},
        ]
        result = _repair_reasoning_item_pairing(items)
        assert result[0]["type"] == "reasoning"
        assert result[1]["type"] == "function_call"
        assert result[2]["type"] == "message"

    def test_reasoning_reordered_before_assistant_message_then_computer_call(self):
        items = [
            {"type": "reasoning", "id": "rs_1"},
            {"type": "computer_call", "call_id": "cc_1", "actions": [{"type": "click"}]},
            {
                "role": "assistant",
                "content": [{"type": "output_text", "text": "I will click the game canvas."}],
            },
            {
                "type": "computer_call_output",
                "call_id": "cc_1",
                "output": {"type": "computer_screenshot", "image_url": "data:image/png;base64,abc"},
            },
        ]
        result = _repair_reasoning_item_pairing(items)
        assert result[0]["type"] == "reasoning"
        assert result[1]["role"] == "assistant"
        assert result[2]["type"] == "computer_call"
        assert result[3]["type"] == "computer_call_output"

    def test_reasoning_keeps_multiple_assistant_messages_before_calls(self):
        items = [
            {"type": "reasoning", "id": "rs_1"},
            {"type": "function_call", "call_id": "fc_1", "name": "memory_search", "arguments": "{}"},
            {"role": "assistant", "content": [{"type": "output_text", "text": "Checking memory first."}]},
            {"role": "assistant", "content": [{"type": "output_text", "text": "Then I will act."}]},
            {"type": "function_call_output", "call_id": "fc_1", "output": "ok"},
        ]
        result = _repair_reasoning_item_pairing(items)
        assert result[0]["type"] == "reasoning"
        assert result[1]["role"] == "assistant"
        assert result[2]["role"] == "assistant"
        assert result[3]["type"] == "function_call"
        assert result[4]["type"] == "function_call_output"

    def test_reasoning_with_assistant_message_is_kept(self):
        items = [
            {"type": "reasoning", "id": "rs_1"},
            {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "hello"}]},
        ]
        result = _repair_reasoning_item_pairing(items)
        assert result[0]["type"] == "reasoning"
        assert result[1]["role"] == "assistant"

    def test_orphaned_reasoning_dropped(self):
        items = [
            {"type": "reasoning", "id": "rs_1"},
            {"type": "function_call_output", "call_id": "fc_1", "output": "ok"},
        ]
        result = _repair_reasoning_item_pairing(items)
        assert all(item.get("type") != "reasoning" for item in result)


class TestOpaqueReasoningDrop:
    def test_drops_opaque_reasoning_and_paired_computer_segment_until_next_user(self):
        items = [
            {"role": "user", "content": [{"type": "input_text", "text": "goal"}]},
            {"type": "reasoning", "id": "rs_1", "summary": []},
            {"type": "computer_call", "call_id": "cc_1", "actions": [{"type": "click"}]},
            {
                "type": "computer_call_output",
                "call_id": "cc_1",
                "output": {"type": "computer_screenshot", "image_url": "data:image/png;base64,abc"},
            },
            {"role": "user", "content": [{"type": "input_text", "text": "[Screenshot saved to: turn_001.png]"}]},
        ]
        result = _drop_opaque_reasoning_segments(items)
        assert result == [
            {"role": "user", "content": [{"type": "input_text", "text": "goal"}]},
            {"role": "user", "content": [{"type": "input_text", "text": "[Screenshot saved to: turn_001.png]"}]},
        ]

    def test_keeps_reasoning_segment_when_summary_text_exists(self):
        items = [
            {
                "type": "reasoning",
                "id": "rs_1",
                "summary": [{"type": "summary_text", "text": "internal summary"}],
            },
            {"type": "function_call", "call_id": "fc_1", "name": "memory_search", "arguments": "{}"},
            {"type": "function_call_output", "call_id": "fc_1", "output": "ok"},
        ]
        result = _drop_opaque_reasoning_segments(items)
        assert result == items

    def test_non_dict_passes_through(self):
        result = _normalize_messages_for_gpt54(["raw_string"])
        assert result == ["raw_string"]

    def test_non_dict_content_message_passes_through(self):
        """Message with content that is neither str nor list."""
        msg = {"role": "user", "content": 42}
        result = _normalize_messages_for_gpt54([msg])
        assert result == [msg]


# ---------------------------------------------------------------------------
# computer_call_output: strip acknowledged_safety_checks
# ---------------------------------------------------------------------------


class TestComputerCallOutput:
    def test_strips_acknowledged_safety_checks(self):
        item = {
            "type": "computer_call_output",
            "call_id": "c1",
            "output": {"type": "computer_screenshot", "image_url": "data:..."},
            "acknowledged_safety_checks": [{"id": "sc1"}],
        }
        result = _normalize_messages_for_gpt54([item])
        assert len(result) == 1
        assert "acknowledged_safety_checks" not in result[0]
        assert result[0]["call_id"] == "c1"

    def test_keeps_other_fields(self):
        item = {
            "type": "computer_call_output",
            "call_id": "c2",
            "output": "screenshot",
        }
        result = _normalize_messages_for_gpt54([item])
        assert result == [item]


# ---------------------------------------------------------------------------
# String content wrapping
# ---------------------------------------------------------------------------


class TestStringContent:
    def test_user_string_becomes_input_text(self):
        msg = {"role": "user", "content": "hello"}
        result = _normalize_messages_for_gpt54([msg])
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == [{"type": "input_text", "text": "hello"}]

    def test_assistant_string_becomes_output_text(self):
        msg = {"role": "assistant", "content": "reply"}
        result = _normalize_messages_for_gpt54([msg])
        assert result[0]["content"] == [{"type": "output_text", "text": "reply"}]


# ---------------------------------------------------------------------------
# Text block conversion
# ---------------------------------------------------------------------------


class TestTextBlocks:
    def test_user_text_block_becomes_input_text(self):
        msg = {"role": "user", "content": [{"type": "text", "text": "hi"}]}
        result = _normalize_messages_for_gpt54([msg])
        assert result == [
            {"role": "user", "content": [{"type": "input_text", "text": "hi"}]}
        ]

    def test_assistant_text_block_becomes_output_text(self):
        msg = {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}
        result = _normalize_messages_for_gpt54([msg])
        assert result == [
            {"role": "assistant", "content": [{"type": "output_text", "text": "ok"}]}
        ]


# ---------------------------------------------------------------------------
# computer_call expansion
# ---------------------------------------------------------------------------


class TestComputerCallExpansion:
    def test_single_action_expanded(self):
        msg = {
            "role": "assistant",
            "content": [
                {"type": "computer_call", "id": "cc1", "action": {"type": "click", "x": 10, "y": 20}},
            ],
        }
        result = _normalize_messages_for_gpt54([msg])
        assert len(result) == 1
        assert result[0]["type"] == "computer_call"
        assert result[0]["call_id"] == "cc1"
        assert result[0]["action"] == {"type": "click", "x": 10, "y": 20}

    def test_batched_actions_expanded(self):
        msg = {
            "role": "assistant",
            "content": [
                {
                    "type": "computer_call",
                    "call_id": "cc2",
                    "actions": [{"type": "click"}, {"type": "type"}],
                },
            ],
        }
        result = _normalize_messages_for_gpt54([msg])
        assert len(result) == 1
        assert result[0]["actions"] == [{"type": "click"}, {"type": "type"}]

    def test_stale_empty_action_becomes_text(self):
        """computer_call with no valid action/actions → serialized as text."""
        msg = {
            "role": "assistant",
            "content": [
                {"type": "computer_call", "id": "cc3", "action": {}},
            ],
        }
        result = _normalize_messages_for_gpt54([msg])
        assert len(result) == 1
        assert result[0]["role"] == "assistant"
        content = result[0]["content"]
        assert len(content) == 1
        assert content[0]["type"] == "output_text"
        assert "details unavailable" in content[0]["text"]

    def test_text_before_computer_call_flushed(self):
        """Text blocks before a computer_call are flushed as a separate message."""
        msg = {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "I will click"},
                {"type": "computer_call", "id": "cc4", "action": {"type": "click"}},
            ],
        }
        result = _normalize_messages_for_gpt54([msg])
        assert len(result) == 2
        assert result[0]["role"] == "assistant"
        assert result[0]["content"] == [{"type": "output_text", "text": "I will click"}]
        assert result[1]["type"] == "computer_call"


# ---------------------------------------------------------------------------
# function_call expansion
# ---------------------------------------------------------------------------


class TestFunctionCallExpansion:
    def test_function_call_expanded(self):
        msg = {
            "role": "assistant",
            "content": [
                {
                    "type": "function_call",
                    "id": "fc1",
                    "name": "memory_search",
                    "arguments": '{"q": "test"}',
                },
            ],
        }
        result = _normalize_messages_for_gpt54([msg])
        assert len(result) == 1
        assert result[0]["type"] == "function_call"
        assert result[0]["call_id"] == "fc1"
        assert result[0]["name"] == "memory_search"
        assert result[0]["arguments"] == '{"q": "test"}'


# ---------------------------------------------------------------------------
# tool_result → function_call_output
# ---------------------------------------------------------------------------


class TestToolResultConversion:
    def test_tool_result_becomes_function_call_output(self):
        msg = {
            "role": "tool",
            "content": [
                {"type": "tool_result", "tool_use_id": "fc1", "content": "result text"},
            ],
        }
        result = _normalize_messages_for_gpt54([msg])
        assert len(result) == 1
        assert result[0]["type"] == "function_call_output"
        assert result[0]["call_id"] == "fc1"
        assert result[0]["output"] == "result text"

    def test_tool_result_list_content_serialized(self):
        """List content in tool_result should be JSON-serialized."""
        msg = {
            "role": "tool",
            "content": [
                {"type": "tool_result", "id": "fc2", "content": [{"key": "val"}]},
            ],
        }
        result = _normalize_messages_for_gpt54([msg])
        assert result[0]["output"] == json.dumps([{"key": "val"}])

    def test_tool_result_non_string_content_stringified(self):
        msg = {
            "role": "tool",
            "content": [
                {"type": "tool_result", "id": "fc3", "content": 42},
            ],
        }
        result = _normalize_messages_for_gpt54([msg])
        assert result[0]["output"] == "42"


# ---------------------------------------------------------------------------
# Already-valid Responses API content block types
# ---------------------------------------------------------------------------


class TestValidBlockTypes:
    def test_input_text_passes_through(self):
        msg = {
            "role": "user",
            "content": [{"type": "input_text", "text": "hi"}],
        }
        result = _normalize_messages_for_gpt54([msg])
        assert result == [msg]

    def test_output_text_passes_through(self):
        msg = {
            "role": "assistant",
            "content": [{"type": "output_text", "text": "hi"}],
        }
        result = _normalize_messages_for_gpt54([msg])
        assert result == [msg]

    def test_input_image_passes_through(self):
        msg = {
            "role": "user",
            "content": [{"type": "input_image", "image_url": "data:..."}],
        }
        result = _normalize_messages_for_gpt54([msg])
        assert result == [msg]


# ---------------------------------------------------------------------------
# Unknown block types
# ---------------------------------------------------------------------------


class TestUnknownBlockTypes:
    def test_unknown_type_serialized_as_text(self):
        msg = {
            "role": "assistant",
            "content": [{"type": "weird_thing", "data": "xyz"}],
        }
        result = _normalize_messages_for_gpt54([msg])
        assert len(result) == 1
        content = result[0]["content"]
        assert len(content) == 1
        assert content[0]["type"] == "output_text"
        assert "weird_thing" in content[0]["text"]


# ---------------------------------------------------------------------------
# Mixed content: multiple block types in one message
# ---------------------------------------------------------------------------


class TestMixedContent:
    def test_text_then_function_call_then_text(self):
        msg = {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "before"},
                {"type": "function_call", "id": "f1", "name": "fn", "arguments": "{}"},
                {"type": "text", "text": "after"},
            ],
        }
        result = _normalize_messages_for_gpt54([msg])
        # Should produce: text msg, function_call item, text msg
        assert len(result) == 3
        assert result[0]["role"] == "assistant"
        assert result[0]["content"] == [{"type": "output_text", "text": "before"}]
        assert result[1]["type"] == "function_call"
        assert result[2]["role"] == "assistant"
        assert result[2]["content"] == [{"type": "output_text", "text": "after"}]

    def test_empty_content_list(self):
        msg = {"role": "user", "content": []}
        result = _normalize_messages_for_gpt54([msg])
        # Empty content list → no text blocks flushed → nothing emitted
        assert result == []
