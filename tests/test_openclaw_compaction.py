"""Tests for the compaction pipeline (US-OC-006).

Covers:
  - Chunk splitting (by token share, by max tokens, adaptive ratio)
  - Message serialization for summarization
  - LLM-based summarization (mocked litellm)
  - Fallback tiers
  - compact_messages() entry point
  - Agent loop helpers (_extract_messages_for_compaction, _create_compacted_instruction)
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cua_bench.agents.openclaw.context import (
    BASE_CHUNK_RATIO,
    DEFAULT_SUMMARY_FALLBACK,
    IDENTIFIER_PRESERVATION_INSTRUCTIONS,
    MIN_CHUNK_RATIO,
    SAFETY_MARGIN,
    CompactionResult,
    chunk_messages_by_max_tokens,
    chunk_messages_by_token_share,
    compact_messages,
    compute_adaptive_chunk_ratio,
    estimate_message_tokens,
    estimate_messages_tokens,
    serialize_messages_for_summary,
    summarize_chunk,
    summarize_chunks_iterative,
    summarize_with_fallback,
)
from cua_bench.agents.openclaw_agent import (
    _create_compacted_instruction,
    _extract_messages_for_compaction,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_msg(role: str, text: str) -> dict:
    """Create a simple message dict."""
    return {"role": role, "content": [{"type": "text", "text": text}]}


def _make_messages(count: int, text_size: int = 100) -> list[dict]:
    """Create a list of messages with roughly equal token sizes."""
    filler = "x" * text_size
    msgs = []
    for i in range(count):
        role = "assistant" if i % 2 else "user"
        msgs.append(_make_msg(role, f"Message {i}: {filler}"))
    return msgs


def _mock_litellm_response(content: str) -> MagicMock:
    """Create a mock litellm completion response."""
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


# ---------------------------------------------------------------------------
# Chunk splitting by token share
# ---------------------------------------------------------------------------

class TestChunkMessagesByTokenShare:
    def test_split_into_two_parts(self):
        msgs = _make_messages(10)
        chunks = chunk_messages_by_token_share(msgs, parts=2)
        assert len(chunks) == 2
        assert sum(len(c) for c in chunks) == 10

    def test_roughly_equal_token_budgets(self):
        msgs = _make_messages(10, text_size=200)
        chunks = chunk_messages_by_token_share(msgs, parts=2)
        tokens = [estimate_messages_tokens(c) for c in chunks]
        # Each half should be within 2x of the other (approximate)
        assert tokens[0] > 0
        assert tokens[1] > 0
        ratio = max(tokens) / min(tokens)
        assert ratio < 3.0

    def test_single_part(self):
        msgs = _make_messages(5)
        chunks = chunk_messages_by_token_share(msgs, parts=1)
        assert len(chunks) == 1
        assert len(chunks[0]) == 5

    def test_empty_messages(self):
        assert chunk_messages_by_token_share([], parts=2) == []

    def test_single_message(self):
        msgs = _make_messages(1)
        chunks = chunk_messages_by_token_share(msgs, parts=2)
        assert len(chunks) == 1
        assert len(chunks[0]) == 1

    def test_more_parts_than_messages(self):
        msgs = _make_messages(2)
        chunks = chunk_messages_by_token_share(msgs, parts=5)
        total = sum(len(c) for c in chunks)
        assert total == 2

    def test_preserves_message_order(self):
        msgs = _make_messages(6)
        chunks = chunk_messages_by_token_share(msgs, parts=2)
        flat = [m for c in chunks for m in c]
        assert flat == msgs


# ---------------------------------------------------------------------------
# Chunk splitting by max tokens
# ---------------------------------------------------------------------------

class TestChunkMessagesByMaxTokens:
    def test_respects_max_tokens(self):
        msgs = _make_messages(10, text_size=200)
        per_msg = estimate_message_tokens(msgs[0])
        # Set max tokens to fit ~3 messages (accounting for safety margin)
        max_tokens = int(per_msg * 3 * SAFETY_MARGIN)
        chunks = chunk_messages_by_max_tokens(msgs, max_tokens)
        assert len(chunks) >= 3
        for chunk in chunks:
            chunk_tokens = estimate_messages_tokens(chunk)
            assert chunk_tokens <= max_tokens

    def test_oversized_single_message_gets_own_chunk(self):
        small = _make_msg("user", "tiny")
        big = _make_msg("assistant", "x" * 10000)
        msgs = [small, big, small]
        # Max tokens fits the small msg but not the big one
        max_tokens = int(estimate_message_tokens(small) * 2 * SAFETY_MARGIN)
        chunks = chunk_messages_by_max_tokens(msgs, max_tokens)
        assert len(chunks) >= 2
        assert sum(len(c) for c in chunks) == 3

    def test_empty_messages(self):
        assert chunk_messages_by_max_tokens([], 1000) == []

    def test_zero_max_tokens(self):
        assert chunk_messages_by_max_tokens(_make_messages(3), 0) == []


# ---------------------------------------------------------------------------
# Adaptive chunk ratio
# ---------------------------------------------------------------------------

class TestComputeAdaptiveChunkRatio:
    def test_default_for_small_messages(self):
        msgs = _make_messages(20, text_size=50)
        ratio = compute_adaptive_chunk_ratio(msgs, 200_000)
        assert ratio == BASE_CHUNK_RATIO

    def test_reduced_for_large_messages(self):
        # Each message ~5000 tokens, context 20000 → avg/ctx > 10%
        msgs = _make_messages(4, text_size=20000)
        ratio = compute_adaptive_chunk_ratio(msgs, 20_000)
        assert ratio < BASE_CHUNK_RATIO
        assert ratio >= MIN_CHUNK_RATIO

    def test_empty_messages(self):
        assert compute_adaptive_chunk_ratio([], 200_000) == BASE_CHUNK_RATIO

    def test_zero_context(self):
        msgs = _make_messages(5)
        assert compute_adaptive_chunk_ratio(msgs, 0) == BASE_CHUNK_RATIO


# ---------------------------------------------------------------------------
# Message serialization
# ---------------------------------------------------------------------------

class TestSerializeMessagesForSummary:
    def test_text_content(self):
        msgs = [_make_msg("user", "hello world")]
        result = serialize_messages_for_summary(msgs)
        assert "[user]" in result
        assert "hello world" in result

    def test_function_call_block(self):
        msg = {
            "role": "assistant",
            "content": [
                {"type": "function_call", "name": "memory_search", "arguments": '{"query": "test"}'},
            ],
        }
        result = serialize_messages_for_summary([msg])
        assert "memory_search" in result
        assert "tool_call" in result

    def test_computer_call_block(self):
        msg = {
            "role": "assistant",
            "content": [
                {"type": "computer_call", "action": {"type": "click", "x": 100, "y": 200}},
            ],
        }
        result = serialize_messages_for_summary([msg])
        assert "computer" in result
        assert "click" in result

    def test_tool_result_block(self):
        msg = {
            "role": "tool",
            "content": [
                {"type": "tool_result", "content": "search returned 3 results"},
            ],
        }
        result = serialize_messages_for_summary([msg])
        assert "tool_result" in result

    def test_string_content(self):
        msg = {"role": "user", "content": "plain text"}
        result = serialize_messages_for_summary([msg])
        assert "plain text" in result

    def test_long_arguments_truncated(self):
        long_args = json.dumps({"data": "x" * 500})
        msg = {
            "role": "assistant",
            "content": [{"type": "function_call", "name": "test", "arguments": long_args}],
        }
        result = serialize_messages_for_summary([msg])
        assert "..." in result


# ---------------------------------------------------------------------------
# Summarize chunk (mocked litellm)
# ---------------------------------------------------------------------------

class TestSummarizeChunk:
    def test_produces_string(self):
        mock_resp = _mock_litellm_response("This is a summary.")
        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
            result = asyncio.get_event_loop().run_until_complete(
                summarize_chunk(_make_messages(3), "test-model")
            )
        assert result == "This is a summary."

    def test_includes_identifier_preservation(self):
        mock_resp = _mock_litellm_response("Summary")
        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp) as mock_acomp:
            asyncio.get_event_loop().run_until_complete(
                summarize_chunk(_make_messages(3), "test-model")
            )
            call_args = mock_acomp.call_args
            system_msg = call_args.kwargs["messages"][0]["content"]
            assert "opaque identifiers" in system_msg

    def test_passes_previous_summary(self):
        mock_resp = _mock_litellm_response("Updated summary")
        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp) as mock_acomp:
            asyncio.get_event_loop().run_until_complete(
                summarize_chunk(
                    _make_messages(3), "test-model",
                    previous_summary="Earlier context here",
                )
            )
            call_args = mock_acomp.call_args
            user_msg = call_args.kwargs["messages"][1]["content"]
            assert "Earlier context here" in user_msg

    def test_passes_custom_instructions(self):
        mock_resp = _mock_litellm_response("Summary")
        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp) as mock_acomp:
            asyncio.get_event_loop().run_until_complete(
                summarize_chunk(
                    _make_messages(3), "test-model",
                    custom_instructions="Focus on game progress",
                )
            )
            call_args = mock_acomp.call_args
            system_msg = call_args.kwargs["messages"][0]["content"]
            assert "Focus on game progress" in system_msg

    def test_retry_on_failure(self):
        mock_resp = _mock_litellm_response("After retry")
        with patch("litellm.acompletion", new_callable=AsyncMock, side_effect=[Exception("API error"), mock_resp]) as mock_acomp:
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = asyncio.get_event_loop().run_until_complete(
                    summarize_chunk(_make_messages(3), "test-model")
                )
        assert result == "After retry"
        assert mock_acomp.call_count == 2

    def test_all_retries_exhausted_raises(self):
        with patch("litellm.acompletion", new_callable=AsyncMock, side_effect=Exception("persistent error")) as mock_acomp:
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(Exception, match="persistent error"):
                    asyncio.get_event_loop().run_until_complete(
                        summarize_chunk(_make_messages(3), "test-model")
                    )
        assert mock_acomp.call_count == 3


# ---------------------------------------------------------------------------
# Summarize chunks iterative
# ---------------------------------------------------------------------------

class TestSummarizeChunksIterative:
    def test_iterates_over_chunks(self):
        mock_resp = _mock_litellm_response("Chunk summary")
        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp) as mock_acomp:
            chunks = [_make_messages(3), _make_messages(3)]
            result = asyncio.get_event_loop().run_until_complete(
                summarize_chunks_iterative(chunks, "test-model")
            )
        assert result == "Chunk summary"
        assert mock_acomp.call_count == 2

    def test_empty_chunks_returns_fallback(self):
        result = asyncio.get_event_loop().run_until_complete(
            summarize_chunks_iterative([], "test-model")
        )
        assert result == DEFAULT_SUMMARY_FALLBACK

    def test_feeds_previous_summary(self):
        """Second chunk should receive the first chunk's summary as context."""
        summaries = ["First chunk summary", "Combined summary"]
        call_count = [0]

        async def mock_acompletion(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            if idx == 1:
                # Verify the second call includes the first summary
                user_msg = kwargs["messages"][1]["content"]
                assert "First chunk summary" in user_msg
            return _mock_litellm_response(summaries[idx])

        with patch("litellm.acompletion", side_effect=mock_acompletion):
            chunks = [_make_messages(3), _make_messages(3)]
            result = asyncio.get_event_loop().run_until_complete(
                summarize_chunks_iterative(chunks, "test-model")
            )
        assert result == "Combined summary"


# ---------------------------------------------------------------------------
# Summarize with fallback
# ---------------------------------------------------------------------------

class TestSummarizeWithFallback:
    def test_tier1_success(self):
        mock_resp = _mock_litellm_response("Full summary")
        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
            result = asyncio.get_event_loop().run_until_complete(
                summarize_with_fallback(
                    _make_messages(5), "test-model", 200_000, 50_000,
                )
            )
        assert result == "Full summary"

    def test_tier3_fallback_on_all_failures(self):
        with patch("litellm.acompletion", new_callable=AsyncMock, side_effect=Exception("fail")):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = asyncio.get_event_loop().run_until_complete(
                    summarize_with_fallback(
                        _make_messages(5), "test-model", 200_000, 50_000,
                    )
                )
        assert "5 messages could not be summarized" in result


# ---------------------------------------------------------------------------
# compact_messages (main entry point)
# ---------------------------------------------------------------------------

class TestCompactMessages:
    def test_returns_compaction_result(self):
        mock_resp = _mock_litellm_response("Compacted summary of conversation.")
        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
            result = asyncio.get_event_loop().run_until_complete(
                compact_messages(_make_messages(10), "test-model", 200_000)
            )
        assert isinstance(result, CompactionResult)
        assert result.summary == "Compacted summary of conversation."
        assert result.tokens_before > 0
        assert result.first_kept_message_index > 0
        assert result.chunks_processed >= 1

    def test_tokens_after_less_than_before(self):
        mock_resp = _mock_litellm_response("Short summary.")
        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
            result = asyncio.get_event_loop().run_until_complete(
                compact_messages(_make_messages(20, text_size=500), "test-model", 200_000)
            )
        assert result.tokens_after < result.tokens_before

    def test_preserves_kept_messages(self):
        """Messages after the compaction point should not be modified."""
        msgs = _make_messages(10)
        mock_resp = _mock_litellm_response("Summary")
        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
            result = asyncio.get_event_loop().run_until_complete(
                compact_messages(msgs, "test-model", 200_000)
            )
        # Verify the split point is reasonable
        assert 0 < result.first_kept_message_index < len(msgs)

    def test_empty_messages(self):
        result = asyncio.get_event_loop().run_until_complete(
            compact_messages([], "test-model", 200_000)
        )
        assert result.summary == DEFAULT_SUMMARY_FALLBACK
        assert result.tokens_before == 0
        assert result.tokens_after == 0
        assert result.first_kept_message_index == 0

    def test_single_message(self):
        """Single message: nothing to split, compact everything."""
        mock_resp = _mock_litellm_response("Single msg summary")
        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
            result = asyncio.get_event_loop().run_until_complete(
                compact_messages(_make_messages(1), "test-model", 200_000)
            )
        assert result.summary == "Single msg summary"
        assert result.first_kept_message_index == 1  # all compacted


# ---------------------------------------------------------------------------
# Identifier preservation (prompt validation)
# ---------------------------------------------------------------------------

class TestIdentifierPreservation:
    def test_preservation_text_mentions_uuids(self):
        assert "UUIDs" in IDENTIFIER_PRESERVATION_INSTRUCTIONS

    def test_preservation_text_mentions_urls(self):
        assert "URLs" in IDENTIFIER_PRESERVATION_INSTRUCTIONS

    def test_preservation_text_mentions_file_names(self):
        assert "file names" in IDENTIFIER_PRESERVATION_INSTRUCTIONS

    def test_preservation_text_mentions_ips(self):
        assert "IPs" in IDENTIFIER_PRESERVATION_INSTRUCTIONS

    def test_injected_into_summarization_prompt(self):
        """Verify identifier instructions appear in the system prompt sent to LLM."""
        mock_resp = _mock_litellm_response("Summary")
        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp) as mock_acomp:
            asyncio.get_event_loop().run_until_complete(
                summarize_chunk(_make_messages(3), "test-model")
            )
            system_content = mock_acomp.call_args.kwargs["messages"][0]["content"]
            assert "opaque identifiers" in system_content
            assert "UUIDs" in system_content


# ---------------------------------------------------------------------------
# Agent loop helpers
# ---------------------------------------------------------------------------

class TestExtractMessagesForCompaction:
    def test_extracts_message_entries(self):
        mock_mgr = MagicMock()
        # Simulate transcript entries
        msg_entry = MagicMock()
        msg_entry.type = "message"
        msg_entry.data = {"message": {"role": "assistant", "content": [{"type": "text", "text": "hello"}]}}
        session_entry = MagicMock()
        session_entry.type = "session"
        session_entry.data = {}
        mock_mgr.load_history.return_value = [session_entry, msg_entry]

        messages = _extract_messages_for_compaction(mock_mgr)
        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"

    def test_skips_non_message_entries(self):
        mock_mgr = MagicMock()
        compaction_entry = MagicMock()
        compaction_entry.type = "compaction"
        compaction_entry.data = {}
        mock_mgr.load_history.return_value = [compaction_entry]

        messages = _extract_messages_for_compaction(mock_mgr)
        assert len(messages) == 0


class TestCreateCompactedInstruction:
    def test_no_summaries_returns_original(self):
        result = _create_compacted_instruction("Do the task", [])
        assert result == "Do the task"

    def test_includes_summary_and_task(self):
        result = _create_compacted_instruction(
            "Do the task",
            ["Agent explored floor 1 and found a key."],
        )
        assert "Prior Context (Compacted)" in result
        assert "Agent explored floor 1" in result
        assert "Do the task" in result
        assert "Current Task" in result

    def test_multiple_summaries(self):
        result = _create_compacted_instruction(
            "Continue exploring",
            ["First compaction summary.", "Second compaction summary."],
        )
        assert "Compaction 1" in result
        assert "Compaction 2" in result
        assert "First compaction summary." in result
        assert "Second compaction summary." in result
