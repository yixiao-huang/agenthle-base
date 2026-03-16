"""Tests for transcript replay — cross-run continuity (US-OC-012).

Tests build_replay_messages, sanitize_history, and limit_history_turns.
"""

from cua_bench.agents.openclaw.session import (
    SessionManager,
    TranscriptEntry,
    build_replay_messages,
    limit_history_turns,
    sanitize_history,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _msg_entry(
    role: str,
    content,
    entry_id: str = "msg-001",
    parent_id: str | None = None,
    usage: dict | None = None,
    stop_reason: str | None = None,
    api: str | None = None,
) -> TranscriptEntry:
    """Create a message TranscriptEntry for testing."""
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    msg_data: dict = {"role": role, "content": content}
    if usage:
        msg_data["usage"] = usage
    if stop_reason:
        msg_data["stopReason"] = stop_reason
    if api:
        msg_data["api"] = api
    return TranscriptEntry(
        type="message",
        id=entry_id,
        parent_id=parent_id,
        timestamp="2026-03-16T10:00:00Z",
        data={"message": msg_data},
    )


def _session_entry(run_number: int = 1) -> TranscriptEntry:
    return TranscriptEntry(
        type="session",
        id=f"sess-{run_number:03d}",
        parent_id=None,
        timestamp="2026-03-16T10:00:00Z",
        data={"version": 1, "task_id": "test", "run_number": run_number, "model": "claude"},
    )


def _compaction_entry(
    summary: str,
    first_kept_id: str,
    entry_id: str = "cmp-001",
) -> TranscriptEntry:
    return TranscriptEntry(
        type="compaction",
        id=entry_id,
        parent_id=None,
        timestamp="2026-03-16T10:00:00Z",
        data={"summary": summary, "firstKeptEntryId": first_kept_id, "tokensBefore": 90000},
    )


# ---------------------------------------------------------------------------
# build_replay_messages
# ---------------------------------------------------------------------------


class TestBuildReplayMessages:
    def test_converts_message_entries(self):
        entries = [
            _session_entry(),
            _msg_entry("user", "Do the task", entry_id="msg-001"),
            _msg_entry("assistant", "I'll click", entry_id="msg-002", parent_id="msg-001"),
        ]
        messages = build_replay_messages(entries)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    def test_skips_session_entries(self):
        entries = [
            _session_entry(1),
            _msg_entry("user", "Hello", entry_id="msg-001"),
            _session_entry(2),
            _msg_entry("user", "World", entry_id="msg-002"),
        ]
        messages = build_replay_messages(entries)
        assert len(messages) == 2
        assert all(m["role"] == "user" for m in messages)

    def test_strips_stale_metadata(self):
        entries = [
            _msg_entry(
                "assistant",
                "Hello",
                entry_id="msg-001",
                usage={"input": 100, "output": 20},
                stop_reason="end_turn",
                api="openai-responses",
            ),
        ]
        messages = build_replay_messages(entries)
        msg = messages[0]
        assert "usage" not in msg
        assert "stopReason" not in msg
        assert "api" not in msg

    def test_maps_toolResult_to_user(self):
        entries = [
            _msg_entry(
                "toolResult",
                [{"type": "text", "text": "result data"}],
                entry_id="msg-001",
            ),
        ]
        messages = build_replay_messages(entries)
        assert messages[0]["role"] == "user"

    def test_compaction_replaces_prior_messages(self):
        entries = [
            _session_entry(),
            _msg_entry("user", "Old message 1", entry_id="msg-001"),
            _msg_entry("assistant", "Old reply 1", entry_id="msg-002"),
            _msg_entry("user", "Kept message", entry_id="msg-003"),
            _compaction_entry("Summary of old context", "msg-003"),
            _msg_entry("assistant", "Reply to kept", entry_id="msg-004"),
        ]
        messages = build_replay_messages(entries)
        # Should have: compaction summary + kept message + reply
        assert len(messages) == 3
        assert "[Compaction summary]" in messages[0]["content"][0]["text"]
        assert "Summary of old context" in messages[0]["content"][0]["text"]

    def test_compaction_no_matching_id(self):
        """When firstKeptEntryId doesn't match, summary is prepended."""
        entries = [
            _msg_entry("user", "Hello", entry_id="msg-001"),
            _compaction_entry("Summary", "nonexistent-id"),
        ]
        messages = build_replay_messages(entries)
        assert messages[0]["role"] == "assistant"
        assert "[Compaction summary]" in messages[0]["content"][0]["text"]

    def test_empty_entries(self):
        assert build_replay_messages([]) == []

    def test_preserves_content_arrays(self):
        content = [
            {"type": "text", "text": "I'll search"},
            {"type": "function_call", "id": "fc-1", "name": "memory_search", "arguments": "{}"},
        ]
        entries = [_msg_entry("assistant", content, entry_id="msg-001")]
        messages = build_replay_messages(entries)
        assert len(messages[0]["content"]) == 2
        assert messages[0]["content"][1]["type"] == "function_call"


# ---------------------------------------------------------------------------
# sanitize_history
# ---------------------------------------------------------------------------


class TestSanitizeHistory:
    def test_strips_base64_images_from_text(self):
        b64 = "data:image/png;base64," + "A" * 200
        messages = [
            {"role": "user", "content": "Look at this"},
            {"role": "assistant", "content": f"Here is the image: {b64} done"},
        ]
        result = sanitize_history(messages)
        assert "base64" not in str(result)
        assistant_msg = [m for m in result if m["role"] == "assistant"][0]
        assert "[image removed]" in assistant_msg["content"]

    def test_strips_image_blocks(self):
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": "Look at this"},
                {"type": "image_url", "url": "data:image/png;base64,abc"},
            ],
        }]
        result = sanitize_history(messages)
        content = result[0]["content"]
        assert all(b["type"] == "text" for b in content)
        assert any("[screenshot from prior run]" in b.get("text", "") for b in content)

    def test_strips_thinking_blocks(self):
        messages = [
            {"role": "user", "content": "Do something"},
            {"role": "assistant", "content": "Before <THINKING>internal reasoning\nmultiline</THINKING> After"},
        ]
        result = sanitize_history(messages)
        assistant_msg = [m for m in result if m["role"] == "assistant"][0]
        text = assistant_msg["content"]
        assert "<THINKING>" not in text
        assert "Before" in text
        assert "After" in text

    def test_strips_thinking_from_content_array(self):
        messages = [
            {"role": "user", "content": "Do something"},
            {"role": "assistant", "content": [{"type": "text", "text": "<THINKING>thoughts</THINKING>Visible"}]},
        ]
        result = sanitize_history(messages)
        assistant_msg = [m for m in result if m["role"] == "assistant"][0]
        assert "<THINKING>" not in assistant_msg["content"][0]["text"]
        assert "Visible" in assistant_msg["content"][0]["text"]

    def test_does_not_strip_thinking_from_user(self):
        messages = [{
            "role": "user",
            "content": "User says <THINKING>not stripped</THINKING> here",
        }]
        result = sanitize_history(messages)
        assert "<THINKING>" in result[0]["content"]

    def test_strips_usage_keys(self):
        messages = [{
            "role": "assistant",
            "content": "Hello",
            "usage": {"input": 100},
            "stopReason": "end_turn",
            "api": "openai-responses",
        }]
        result = sanitize_history(messages)
        assert "usage" not in result[0]
        assert "stopReason" not in result[0]
        assert "api" not in result[0]

    def test_ensures_user_first(self):
        messages = [
            {"role": "assistant", "content": "I start"},
            {"role": "user", "content": "Hello"},
        ]
        result = sanitize_history(messages)
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "[session history follows]"
        assert len(result) == 3

    def test_no_prepend_when_user_first(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        result = sanitize_history(messages)
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"

    def test_repairs_orphaned_tool_results(self):
        """tool_result without matching function_call is removed."""
        messages = [
            {"role": "user", "content": "Do something"},
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "orphan-id", "content": "result"},
                ],
            },
        ]
        result = sanitize_history(messages)
        # The orphaned tool_result message should be removed entirely
        assert len(result) == 1

    def test_repairs_orphaned_function_calls(self):
        """function_call without matching tool_result is removed."""
        messages = [
            {"role": "user", "content": "Do something"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me search"},
                    {"type": "function_call", "id": "orphan-call", "name": "search", "arguments": "{}"},
                ],
            },
        ]
        result = sanitize_history(messages)
        # function_call block removed, text kept
        assistant_msg = [m for m in result if m["role"] == "assistant"][0]
        assert len(assistant_msg["content"]) == 1
        assert assistant_msg["content"][0]["type"] == "text"

    def test_keeps_paired_tool_calls(self):
        """Matched function_call + tool_result are preserved."""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "function_call", "id": "call-1", "name": "search", "arguments": "{}"},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "call-1", "content": "found it"},
                ],
            },
        ]
        result = sanitize_history(messages)
        # Both should be kept (plus prepended user-first message)
        non_bootstrap = [m for m in result if m.get("content") != "[session history follows]"]
        assert len(non_bootstrap) == 2

    def test_empty_messages(self):
        assert sanitize_history([]) == []

    def test_strips_base64_source_blocks(self):
        """Image blocks with base64 source are replaced."""
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "data": "abc123"}},
            ],
        }]
        result = sanitize_history(messages)
        assert result[0]["content"][0]["type"] == "text"
        assert "[screenshot from prior run]" in result[0]["content"][0]["text"]


# ---------------------------------------------------------------------------
# limit_history_turns
# ---------------------------------------------------------------------------


class TestLimitHistoryTurns:
    def test_keeps_last_n_user_turns(self):
        messages = [
            {"role": "user", "content": "Turn 1"},
            {"role": "assistant", "content": "Reply 1"},
            {"role": "user", "content": "Turn 2"},
            {"role": "assistant", "content": "Reply 2"},
            {"role": "user", "content": "Turn 3"},
            {"role": "assistant", "content": "Reply 3"},
        ]
        result = limit_history_turns(messages, 2)
        assert len(result) == 4
        assert result[0]["content"] == "Turn 2"
        assert result[-1]["content"] == "Reply 3"

    def test_none_returns_all(self):
        messages = [{"role": "user", "content": f"Turn {i}"} for i in range(10)]
        result = limit_history_turns(messages, None)
        assert len(result) == 10

    def test_zero_returns_all(self):
        messages = [{"role": "user", "content": "Hello"}]
        result = limit_history_turns(messages, 0)
        assert len(result) == 1

    def test_negative_returns_all(self):
        messages = [{"role": "user", "content": "Hello"}]
        result = limit_history_turns(messages, -1)
        assert len(result) == 1

    def test_limit_greater_than_turns(self):
        messages = [
            {"role": "user", "content": "Turn 1"},
            {"role": "assistant", "content": "Reply 1"},
        ]
        result = limit_history_turns(messages, 100)
        assert len(result) == 2

    def test_single_turn(self):
        messages = [
            {"role": "user", "content": "Only turn"},
            {"role": "assistant", "content": "Only reply"},
        ]
        result = limit_history_turns(messages, 1)
        assert len(result) == 2

    def test_empty_messages(self):
        assert limit_history_turns([], 5) == []

    def test_keeps_assistant_responses_with_user_turns(self):
        messages = [
            {"role": "user", "content": "T1"},
            {"role": "assistant", "content": "R1"},
            {"role": "assistant", "content": "R1b"},  # multi-assistant
            {"role": "user", "content": "T2"},
            {"role": "assistant", "content": "R2"},
        ]
        result = limit_history_turns(messages, 1)
        # Should keep from T2 onward
        assert len(result) == 2
        assert result[0]["content"] == "T2"


# ---------------------------------------------------------------------------
# Re-sanitize after truncation
# ---------------------------------------------------------------------------


class TestResanitizeAfterTruncation:
    def test_truncation_orphans_are_repaired(self):
        """Truncation can orphan tool results at the cut boundary; re-sanitize fixes them."""
        messages = [
            {"role": "user", "content": "T1"},
            {
                "role": "assistant",
                "content": [
                    {"type": "function_call", "id": "call-1", "name": "search", "arguments": "{}"},
                ],
            },
            # This result pairs with call-1, but after truncation call-1 is gone
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "call-1", "content": "result"},
                ],
            },
            {"role": "user", "content": "T2"},
            {"role": "assistant", "content": "Reply 2"},
        ]
        # Limit to 1 user turn — keeps T2 + Reply 2
        truncated = limit_history_turns(messages, 1)
        # Re-sanitize to fix any orphans
        result = sanitize_history(truncated)
        # Should just have T2 + Reply 2
        non_bootstrap = [m for m in result if m.get("content") != "[session history follows]"]
        assert len(non_bootstrap) == 2


# ---------------------------------------------------------------------------
# Integration: full pipeline with SessionManager
# ---------------------------------------------------------------------------


class TestReplayIntegration:
    def test_full_replay_pipeline(self, tmp_path):
        """End-to-end: create transcript, replay, sanitize, limit."""
        sm = SessionManager("test-task", base_dir=tmp_path)
        sm.init_session(model="claude")

        # Simulate a multi-step conversation
        sm.append_message("user", "Navigate to floor 2")
        sm.append_message(
            "assistant",
            [
                {"type": "text", "text": "I'll click the door"},
                {"type": "computer_call", "id": "cc-1", "action": {"type": "click", "x": 100, "y": 200}},
            ],
            stop_reason="tool_use",
        )
        sm.append_message(
            "tool",
            [{"type": "tool_result", "tool_use_id": "cc-1", "content": "image:trajectory"}],
        )
        sm.append_message("assistant", "I can see floor 2 now")

        # Load and replay
        entries = sm.load_history()
        messages = build_replay_messages(entries)
        assert len(messages) == 4

        messages = sanitize_history(messages)
        # Should have user-first bootstrap + 4 messages
        assert messages[0]["role"] == "user"

        messages = limit_history_turns(messages, 2)
        # Re-sanitize
        messages = sanitize_history(messages)
        assert len(messages) > 0

    def test_multi_run_replay(self, tmp_path):
        """Replay across two runs produces combined history."""
        sm = SessionManager("test-task", base_dir=tmp_path)

        # Run 1
        sm.init_session(model="claude")
        sm.append_message("user", "Start task")
        sm.append_message("assistant", "Working on it")

        # Run 2
        sm.init_session(model="claude")
        sm.append_message("user", "Continue task")
        sm.append_message("assistant", "Continuing")

        entries = sm.load_history()
        messages = build_replay_messages(entries)
        # 4 messages (2 per run, session entries skipped)
        assert len(messages) == 4

    def test_replay_with_compaction(self, tmp_path):
        """Compaction entry collapses prior messages."""
        sm = SessionManager("test-task", base_dir=tmp_path)
        sm.init_session(model="claude")

        sm.append_message("user", "Old message")
        sm.append_message("assistant", "Old reply")
        e3 = sm.append_message("user", "Kept message")

        sm.append_compaction("Summary of old conversation", e3.id, 90000)

        sm.append_message("assistant", "Reply to kept")

        entries = sm.load_history()
        messages = build_replay_messages(entries)
        # Old messages replaced by compaction summary, kept message + reply preserved
        assert len(messages) == 3
        assert "[Compaction summary]" in messages[0]["content"][0]["text"]

    def test_empty_history_produces_empty_replay(self, tmp_path):
        """No prior entries means empty replay messages."""
        sm = SessionManager("test-task", base_dir=tmp_path)
        sm.init_session(model="claude")

        # Only session header, no messages
        entries = sm.load_history()
        messages = build_replay_messages(entries)
        assert messages == []
