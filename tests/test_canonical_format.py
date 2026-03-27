"""Tests for US-OC-038: Canonical internal message format.

Covers:
  - normalize_to_canonical: untyped dicts → CanonicalMessage
  - canonical_to_responses_api: CanonicalMessage → Responses API flat items
  - canonical_to_anthropic_messages: CanonicalMessage → Anthropic completion format
  - _build_compacted_items integration: verify canonical output from compaction
"""

from cua_bench.agents.openclaw.canonical import (
    COMPACTION_PREAMBLE,
    CanonicalMessage,
    CompactionSummaryBlock,
    ComputerCallBlock,
    FunctionCallBlock,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    canonical_to_anthropic_messages,
    canonical_to_responses_api,
    normalize_to_canonical,
)

# ---- Helpers ----


def _msg(role: str, content, **kwargs) -> dict:
    """Build an untyped message dict."""
    m = {"role": role, "content": content}
    m.update(kwargs)
    return m


# =========================================================================
# normalize_to_canonical
# =========================================================================


class TestNormalizeToCanonical:
    """Test ingestion from untyped dicts to typed CanonicalMessage."""

    def test_string_content_normalized_to_text_block(self):
        msgs = [_msg("user", "Hello"), _msg("assistant", "Hi")]
        result = normalize_to_canonical(msgs)

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == [{"type": "text", "text": "Hello"}]
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == [{"type": "text", "text": "Hi"}]

    def test_text_blocks_preserved(self):
        msgs = [_msg("user", [{"type": "text", "text": "Hello world"}])]
        result = normalize_to_canonical(msgs)

        assert result[0]["content"][0]["type"] == "text"
        assert result[0]["content"][0]["text"] == "Hello world"

    def test_function_call_block(self):
        msgs = [_msg("assistant", [
            {"type": "function_call", "id": "call-1", "name": "search", "arguments": '{"q": "x"}'},
        ])]
        result = normalize_to_canonical(msgs)

        block = result[0]["content"][0]
        assert block["type"] == "function_call"
        assert block["id"] == "call-1"
        assert block["name"] == "search"
        assert block["arguments"] == '{"q": "x"}'

    def test_function_call_block_with_call_id_field(self):
        """Some transcript paths use call_id instead of id."""
        msgs = [_msg("assistant", [
            {"type": "function_call", "call_id": "call-2", "name": "get", "arguments": "{}"},
        ])]
        result = normalize_to_canonical(msgs)

        block = result[0]["content"][0]
        assert block["id"] == "call-2"

    def test_computer_call_action_normalized_to_actions(self):
        """Singular action dict normalized to actions list."""
        msgs = [_msg("assistant", [
            {"type": "computer_call", "id": "cc-1", "action": {"type": "click", "x": 100, "y": 200}},
        ])]
        result = normalize_to_canonical(msgs)

        block = result[0]["content"][0]
        assert block["type"] == "computer_call"
        assert block["id"] == "cc-1"
        assert block["actions"] == [{"type": "click", "x": 100, "y": 200}]

    def test_computer_call_actions_list_preserved(self):
        """Already-list actions preserved as-is."""
        actions = [{"type": "click", "x": 10, "y": 20}, {"type": "type", "text": "hi"}]
        msgs = [_msg("assistant", [
            {"type": "computer_call", "id": "cc-2", "actions": actions},
        ])]
        result = normalize_to_canonical(msgs)

        assert result[0]["content"][0]["actions"] == actions

    def test_tool_result_block(self):
        msgs = [_msg("tool", [
            {"type": "tool_result", "tool_use_id": "call-1", "content": "done"},
        ])]
        result = normalize_to_canonical(msgs)

        block = result[0]["content"][0]
        assert block["type"] == "tool_result"
        assert block["tool_use_id"] == "call-1"
        assert block["content"] == "done"
        assert "is_error" not in block

    def test_tool_result_is_error_preserved(self):
        msgs = [_msg("tool", [
            {"type": "tool_result", "tool_use_id": "c-1", "content": "fail", "is_error": True},
        ])]
        result = normalize_to_canonical(msgs)

        assert result[0]["content"][0]["is_error"] is True

    def test_thinking_block(self):
        msgs = [_msg("assistant", [
            {"type": "thinking", "thinking": "Let me think..."},
        ])]
        result = normalize_to_canonical(msgs)

        block = result[0]["content"][0]
        assert block["type"] == "thinking"
        assert block["thinking"] == "Let me think..."
        assert "thinkingSignature" not in block

    def test_thinking_block_with_signature(self):
        msgs = [_msg("assistant", [
            {"type": "thinking", "thinking": "hmm", "thinkingSignature": "sig123"},
        ])]
        result = normalize_to_canonical(msgs)

        assert result[0]["content"][0]["thinkingSignature"] == "sig123"

    def test_stop_reason_preserved(self):
        msgs = [_msg("assistant", "I'm done", stop_reason="end_turn")]
        result = normalize_to_canonical(msgs)

        assert result[0]["stop_reason"] == "end_turn"

    def test_stop_reason_absent_when_not_provided(self):
        msgs = [_msg("user", "hello")]
        result = normalize_to_canonical(msgs)

        assert "stop_reason" not in result[0]

    def test_mixed_content_blocks(self):
        """Assistant message with text + function_call + computer_call."""
        msgs = [_msg("assistant", [
            {"type": "text", "text": "I'll help"},
            {"type": "function_call", "id": "f-1", "name": "search", "arguments": "{}"},
            {"type": "computer_call", "id": "c-1", "action": {"type": "click", "x": 50, "y": 50}},
        ])]
        result = normalize_to_canonical(msgs)

        blocks = result[0]["content"]
        assert len(blocks) == 3
        assert blocks[0]["type"] == "text"
        assert blocks[1]["type"] == "function_call"
        assert blocks[2]["type"] == "computer_call"

    def test_empty_messages(self):
        assert normalize_to_canonical([]) == []

    def test_computer_call_output_normalized_to_tool_result(self):
        """computer_call_output blocks from some transcript paths become ToolResultBlock."""
        msgs = [_msg("tool", [
            {"type": "computer_call_output", "call_id": "cc-1", "output": "screenshot data"},
        ])]
        result = normalize_to_canonical(msgs)

        block = result[0]["content"][0]
        assert block["type"] == "tool_result"
        assert block["tool_use_id"] == "cc-1"
        assert block["content"] == "screenshot data"


# =========================================================================
# canonical_to_responses_api
# =========================================================================


class TestCanonicalToResponsesApi:
    """Test conversion from canonical messages to Responses API flat items."""

    def test_user_text_to_input_text(self):
        msgs = [CanonicalMessage(
            role="user",
            content=[TextBlock(type="text", text="Hello")],
        )]
        items = canonical_to_responses_api(msgs)

        assert len(items) == 1
        assert items[0]["type"] == "message"
        assert items[0]["role"] == "user"
        assert items[0]["content"] == [{"type": "input_text", "text": "Hello"}]

    def test_assistant_text_to_output_text(self):
        msgs = [CanonicalMessage(
            role="assistant",
            content=[TextBlock(type="text", text="Hi there")],
        )]
        items = canonical_to_responses_api(msgs)

        assert items[0]["type"] == "message"
        assert items[0]["role"] == "assistant"
        assert items[0]["content"] == [{"type": "output_text", "text": "Hi there"}]

    def test_compaction_summary_to_user_with_preamble(self):
        msgs = [CanonicalMessage(
            role="user",
            content=[CompactionSummaryBlock(type="compaction_summary", text="Prior work summary")],
        )]
        items = canonical_to_responses_api(msgs)

        assert len(items) == 1
        assert items[0]["type"] == "message"
        assert items[0]["role"] == "user"
        text = items[0]["content"][0]["text"]
        assert text.startswith(COMPACTION_PREAMBLE)
        assert "Prior work summary" in text

    def test_function_call_id_to_call_id(self):
        msgs = [CanonicalMessage(
            role="assistant",
            content=[FunctionCallBlock(
                type="function_call", id="f-1", name="search", arguments='{"q": "test"}',
            )],
        )]
        items = canonical_to_responses_api(msgs)

        assert items[0]["type"] == "function_call"
        assert items[0]["call_id"] == "f-1"
        assert items[0]["name"] == "search"
        assert items[0]["arguments"] == '{"q": "test"}'

    def test_computer_call_converted_to_text(self):
        """Compacted computer_call blocks become text (screenshots gone, OpenAI rejects placeholders)."""
        msgs = [CanonicalMessage(
            role="assistant",
            content=[ComputerCallBlock(
                type="computer_call", id="cc-1",
                actions=[{"type": "click", "x": 100, "y": 200}],
            )],
        )]
        items = canonical_to_responses_api(msgs)

        assert items[0]["type"] == "message"
        assert items[0]["role"] == "assistant"
        assert "computer action" in items[0]["content"][0]["text"]

    def test_function_call_output(self):
        msgs = [
            CanonicalMessage(
                role="assistant",
                content=[FunctionCallBlock(
                    type="function_call", id="f-1", name="tool", arguments="{}",
                )],
            ),
            CanonicalMessage(
                role="tool",
                content=[ToolResultBlock(
                    type="tool_result", tool_use_id="f-1", content="result",
                )],
            ),
        ]
        items = canonical_to_responses_api(msgs)

        assert items[1]["type"] == "function_call_output"
        assert items[1]["call_id"] == "f-1"
        assert items[1]["output"] == "result"

    def test_computer_call_output_converted_to_text(self):
        """Compacted computer_call results become text (no screenshot data available)."""
        msgs = [
            CanonicalMessage(
                role="assistant",
                content=[ComputerCallBlock(
                    type="computer_call", id="cc-1",
                    actions=[{"type": "click", "x": 10, "y": 20}],
                )],
            ),
            CanonicalMessage(
                role="tool",
                content=[ToolResultBlock(
                    type="tool_result", tool_use_id="cc-1", content="screenshot",
                )],
            ),
        ]
        items = canonical_to_responses_api(msgs)

        # Both computer_call and its result become text messages
        assert all(i["type"] == "message" for i in items)
        assert "computer action" in items[0]["content"][0]["text"]
        assert "computer result" in items[1]["content"][0]["text"]

    def test_thinking_blocks_skipped(self):
        msgs = [CanonicalMessage(
            role="assistant",
            content=[
                ThinkingBlock(type="thinking", thinking="Let me think..."),
                TextBlock(type="text", text="Here's my answer"),
            ],
        )]
        items = canonical_to_responses_api(msgs)

        assert len(items) == 1
        assert items[0]["type"] == "message"
        assert items[0]["content"][0]["text"] == "Here's my answer"

    def test_tool_adjacency(self):
        """Tool call should be immediately followed by its output."""
        msgs = [
            CanonicalMessage(
                role="assistant",
                content=[FunctionCallBlock(
                    type="function_call", id="f-1", name="tool", arguments="{}",
                )],
            ),
            CanonicalMessage(
                role="user",
                content=[TextBlock(type="text", text="interleaved message")],
            ),
            CanonicalMessage(
                role="tool",
                content=[ToolResultBlock(
                    type="tool_result", tool_use_id="f-1", content="result",
                )],
            ),
        ]
        items = canonical_to_responses_api(msgs)

        # function_call should be immediately followed by function_call_output
        assert items[0]["type"] == "function_call"
        assert items[1]["type"] == "function_call_output"
        # interleaved message comes after
        assert items[2]["type"] == "message"

    def test_full_conversation_roundtrip(self):
        """Realistic conversation preserves all data through canonical → Responses API."""
        msgs = [
            CanonicalMessage(
                role="user",
                content=[CompactionSummaryBlock(type="compaction_summary", text="Prior context here")],
            ),
            CanonicalMessage(
                role="user",
                content=[TextBlock(type="text", text="Navigate to floor 3")],
            ),
            CanonicalMessage(
                role="assistant",
                content=[
                    TextBlock(type="text", text="I'll click the stairs"),
                    ComputerCallBlock(type="computer_call", id="cc-1", actions=[{"type": "click", "x": 50, "y": 50}]),
                ],
            ),
            CanonicalMessage(
                role="tool",
                content=[ToolResultBlock(type="tool_result", tool_use_id="cc-1", content="screenshot")],
            ),
            CanonicalMessage(
                role="assistant",
                content=[
                    TextBlock(type="text", text="I see floor 3. Let me save a milestone."),
                    FunctionCallBlock(type="function_call", id="f-1", name="milestone", arguments='{"label": "floor3"}'),
                ],
            ),
            CanonicalMessage(
                role="tool",
                content=[ToolResultBlock(type="tool_result", tool_use_id="f-1", content="saved")],
            ),
        ]
        items = canonical_to_responses_api(msgs)

        types = [i["type"] for i in items]
        assert "message" in types  # text, summary, and computer call/result all become messages
        assert "function_call" in types
        assert "function_call_output" in types

        # Computer calls/results become text (screenshots gone after compaction)
        assert "computer_call" not in types
        assert "computer_call_output" not in types

        # Verify summary preamble
        assert COMPACTION_PREAMBLE in items[0]["content"][0]["text"]

        # Verify function call has call_id (not id)
        fn_calls = [i for i in items if i["type"] == "function_call"]
        for c in fn_calls:
            assert "call_id" in c
            assert "id" not in c


# =========================================================================
# canonical_to_anthropic_messages
# =========================================================================


class TestCanonicalToAnthropicMessages:
    """Test conversion from canonical to Anthropic completion format."""

    def test_user_text(self):
        msgs = [CanonicalMessage(
            role="user",
            content=[TextBlock(type="text", text="Hello")],
        )]
        result = canonical_to_anthropic_messages(msgs)

        assert result[0]["role"] == "user"
        assert result[0]["content"] == [{"type": "text", "text": "Hello"}]

    def test_assistant_text(self):
        msgs = [CanonicalMessage(
            role="assistant",
            content=[TextBlock(type="text", text="Hi there")],
        )]
        result = canonical_to_anthropic_messages(msgs)

        assert result[0]["role"] == "assistant"
        assert result[0]["content"] == [{"type": "text", "text": "Hi there"}]

    def test_function_call_to_tool_use(self):
        msgs = [CanonicalMessage(
            role="assistant",
            content=[FunctionCallBlock(
                type="function_call", id="f-1", name="search",
                arguments='{"query": "test"}',
            )],
        )]
        result = canonical_to_anthropic_messages(msgs)

        block = result[0]["content"][0]
        assert block["type"] == "tool_use"
        assert block["id"] == "f-1"
        assert block["name"] == "search"
        assert block["input"] == {"query": "test"}

    def test_computer_call_to_tool_use(self):
        msgs = [CanonicalMessage(
            role="assistant",
            content=[ComputerCallBlock(
                type="computer_call", id="cc-1",
                actions=[{"type": "click", "x": 100, "y": 200}],
            )],
        )]
        result = canonical_to_anthropic_messages(msgs)

        block = result[0]["content"][0]
        assert block["type"] == "tool_use"
        assert block["id"] == "cc-1"
        assert block["name"] == "computer"
        assert block["input"] == {"actions": [{"type": "click", "x": 100, "y": 200}]}

    def test_tool_result_to_user_tool_result(self):
        """Anthropic tool results are sent as role=user with type=tool_result."""
        msgs = [CanonicalMessage(
            role="tool",
            content=[ToolResultBlock(
                type="tool_result", tool_use_id="f-1", content="done",
            )],
        )]
        result = canonical_to_anthropic_messages(msgs)

        assert result[0]["role"] == "user"
        block = result[0]["content"][0]
        assert block["type"] == "tool_result"
        assert block["tool_use_id"] == "f-1"
        assert block["content"] == "done"

    def test_tool_result_is_error(self):
        msgs = [CanonicalMessage(
            role="tool",
            content=[ToolResultBlock(
                type="tool_result", tool_use_id="f-1", content="fail", is_error=True,
            )],
        )]
        result = canonical_to_anthropic_messages(msgs)

        assert result[0]["content"][0]["is_error"] is True

    def test_thinking_block_preserved(self):
        msgs = [CanonicalMessage(
            role="assistant",
            content=[
                ThinkingBlock(type="thinking", thinking="hmm", thinkingSignature="sig1"),
                TextBlock(type="text", text="answer"),
            ],
        )]
        result = canonical_to_anthropic_messages(msgs)

        blocks = result[0]["content"]
        assert blocks[0]["type"] == "thinking"
        assert blocks[0]["thinking"] == "hmm"
        assert blocks[0]["signature"] == "sig1"
        assert blocks[1]["type"] == "text"

    def test_compaction_summary_in_user_message(self):
        msgs = [CanonicalMessage(
            role="user",
            content=[CompactionSummaryBlock(type="compaction_summary", text="Summary text")],
        )]
        result = canonical_to_anthropic_messages(msgs)

        assert result[0]["role"] == "user"
        text = result[0]["content"][0]["text"]
        assert COMPACTION_PREAMBLE in text
        assert "Summary text" in text

    def test_full_conversation_roundtrip(self):
        """Realistic conversation → Anthropic format preserves all data."""
        msgs = [
            CanonicalMessage(
                role="user",
                content=[TextBlock(type="text", text="Do something")],
            ),
            CanonicalMessage(
                role="assistant",
                content=[
                    TextBlock(type="text", text="OK"),
                    FunctionCallBlock(type="function_call", id="f-1", name="tool", arguments='{"x": 1}'),
                ],
            ),
            CanonicalMessage(
                role="tool",
                content=[ToolResultBlock(type="tool_result", tool_use_id="f-1", content="done")],
            ),
            CanonicalMessage(
                role="assistant",
                content=[TextBlock(type="text", text="All done")],
            ),
        ]
        result = canonical_to_anthropic_messages(msgs)

        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert len(result[1]["content"]) == 2  # text + tool_use
        assert result[1]["content"][1]["type"] == "tool_use"
        assert result[1]["content"][1]["input"] == {"x": 1}
        assert result[2]["role"] == "user"  # Anthropic: tool results as user
        assert result[2]["content"][0]["type"] == "tool_result"
        assert result[3]["role"] == "assistant"


# =========================================================================
# _build_compacted_items integration (standalone)
# =========================================================================


class TestBuildCompactedItemsCanonical:
    """Verify _build_compacted_items outputs canonical messages.

    Uses the standalone version from test_message_ordering to avoid
    instantiating the full agent class.
    """

    def _build(self, summary: str, kept: list[dict]) -> list[CanonicalMessage]:
        from tests.test_message_ordering import _build_compacted_items_standalone
        return _build_compacted_items_standalone(summary, kept)

    def test_returns_canonical_messages(self):
        result = self._build("Summary", [_msg("user", "Hello")])

        for msg in result:
            assert "role" in msg
            assert "content" in msg
            assert isinstance(msg["content"], list)

    def test_summary_is_compaction_summary_block(self):
        result = self._build("My summary", [])

        assert result[0]["role"] == "user"
        assert result[0]["content"][0]["type"] == "compaction_summary"
        assert result[0]["content"][0]["text"] == "My summary"

    def test_kept_messages_normalized(self):
        kept = [
            _msg("assistant", [
                {"type": "text", "text": "I'll click"},
                {"type": "computer_call", "id": "cc-1", "action": {"type": "click", "x": 1, "y": 2}},
            ]),
            _msg("tool", [
                {"type": "tool_result", "tool_use_id": "cc-1", "content": "ok"},
            ]),
        ]
        result = self._build("Summary", kept)

        # summary + 2 kept messages
        assert len(result) == 3
        # assistant message has normalized blocks
        assistant = result[1]
        assert assistant["role"] == "assistant"
        assert assistant["content"][1]["type"] == "computer_call"
        assert assistant["content"][1]["actions"] == [{"type": "click", "x": 1, "y": 2}]

    def test_trailing_assistant_gets_continuation(self):
        kept = [_msg("assistant", "Last thing")]
        result = self._build("Summary", kept)

        assert result[-1]["role"] == "user"
        assert result[-1]["content"][0]["type"] == "text"
        assert result[-1]["content"][0]["text"] == "[Continue from where you left off.]"

    def test_canonical_to_responses_api_after_build(self):
        """Verify the bridge: canonical → Responses API items produces valid output."""
        kept = [
            _msg("user", "Navigate"),
            _msg("assistant", [
                {"type": "function_call", "id": "f-1", "name": "milestone", "arguments": "{}"},
            ]),
            _msg("tool", [
                {"type": "tool_result", "tool_use_id": "f-1", "content": "saved"},
            ]),
        ]
        canonical = self._build("Prior context", kept)
        items = canonical_to_responses_api(canonical)

        # Should have: summary message + user message + function_call + function_call_output
        types = [i["type"] for i in items]
        assert "message" in types
        assert "function_call" in types
        assert "function_call_output" in types

        # Summary has preamble
        assert COMPACTION_PREAMBLE in items[0]["content"][0]["text"]
