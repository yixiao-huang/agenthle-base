"""Tests for openclaw session persistence (SessionManager, SessionState, TokenUsage, TranscriptEntry)."""

import json
from pathlib import Path

from cua_bench.agents.openclaw.session import (
    DEFAULT_BASE_DIR,
    SessionManager,
    SessionState,
    TokenUsage,
    TranscriptEntry,
)


# ---------------------------------------------------------------------------
# TokenUsage
# ---------------------------------------------------------------------------


class TestTokenUsage:
    def test_defaults(self):
        t = TokenUsage()
        assert t.input_tokens == 0
        assert t.output_tokens == 0

    def test_accumulation(self):
        t = TokenUsage(input_tokens=100, output_tokens=50)
        t.accumulate(200, 30)
        assert t.input_tokens == 300
        assert t.output_tokens == 80

    def test_roundtrip(self):
        t = TokenUsage(input_tokens=42, output_tokens=7)
        d = t.to_dict()
        t2 = TokenUsage.from_dict(d)
        assert t2.input_tokens == 42
        assert t2.output_tokens == 7

    def test_from_dict_missing_keys(self):
        t = TokenUsage.from_dict({})
        assert t.input_tokens == 0
        assert t.output_tokens == 0


# ---------------------------------------------------------------------------
# SessionState
# ---------------------------------------------------------------------------


class TestSessionState:
    def test_serialization_roundtrip(self):
        state = SessionState(
            task_id="mota_24_easy",
            run_number=3,
            step_count=47,
            total_tokens=TokenUsage(125000, 8500),
            compaction_count=1,
            compaction_summaries=["Agent navigated floor 2"],
            created_at="2026-03-11T10:00:00Z",
            updated_at="2026-03-11T10:15:00Z",
        )
        d = state.to_dict()
        restored = SessionState.from_dict(d)
        assert restored.task_id == "mota_24_easy"
        assert restored.run_number == 3
        assert restored.step_count == 47
        assert restored.total_tokens.input_tokens == 125000
        assert restored.compaction_count == 1
        assert restored.compaction_summaries == ["Agent navigated floor 2"]

    def test_defaults(self):
        state = SessionState(task_id="test")
        assert state.run_number == 0
        assert state.step_count == 0
        assert state.compaction_summaries == []


# ---------------------------------------------------------------------------
# TranscriptEntry
# ---------------------------------------------------------------------------


class TestTranscriptEntry:
    def test_session_header_entry(self):
        entry = TranscriptEntry(
            type="session",
            id="sess-abc123",
            parent_id=None,
            timestamp="2026-03-11T10:00:00Z",
            data={"version": 1, "task_id": "test", "run_number": 1, "model": "claude"},
        )
        d = entry.to_dict()
        assert d["type"] == "session"
        assert d["parentId"] is None
        assert d["version"] == 1
        assert d["task_id"] == "test"

    def test_message_entry(self):
        entry = TranscriptEntry(
            type="message",
            id="msg-xyz",
            parent_id="sess-abc",
            timestamp="2026-03-11T10:01:00Z",
            data={"message": {"role": "assistant", "content": "Hello"}},
        )
        d = entry.to_dict()
        assert d["message"]["role"] == "assistant"
        assert d["parentId"] == "sess-abc"

    def test_json_serialization(self):
        entry = TranscriptEntry(
            type="compaction",
            id="cmp-123",
            parent_id="msg-456",
            timestamp="2026-03-11T10:05:00Z",
            data={"summary": "test", "firstKeptEntryId": "msg-789", "tokensBefore": 95000},
        )
        json_str = json.dumps(entry.to_dict())
        restored = TranscriptEntry.from_dict(json.loads(json_str))
        assert restored.type == "compaction"
        assert restored.parent_id == "msg-456"
        assert restored.data["summary"] == "test"
        assert restored.data["tokensBefore"] == 95000


# ---------------------------------------------------------------------------
# SessionManager — Init & Paths
# ---------------------------------------------------------------------------


class TestSessionManagerInit:
    def test_default_base_dir(self):
        sm = SessionManager("task1")
        assert sm.task_dir == Path(DEFAULT_BASE_DIR) / "task1"

    def test_custom_base_dir(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        assert sm.task_dir == tmp_path / "task1"
        assert sm.state_path == tmp_path / "task1" / "state.json"
        assert sm.transcript_path == tmp_path / "task1" / "transcript.jsonl"

    def test_default_base_dir_value(self):
        assert DEFAULT_BASE_DIR == "openclaw_sessions"


# ---------------------------------------------------------------------------
# SessionManager — init_session
# ---------------------------------------------------------------------------


class TestInitSession:
    def test_first_session_creates_run_1(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        state = sm.init_session(model="claude-sonnet")
        assert state.run_number == 1
        assert state.step_count == 0
        assert state.task_id == "task1"
        assert state.created_at != ""

    def test_increments_run_number(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        state2 = sm.init_session()
        assert state2.run_number == 2

    def test_preserves_cumulative_tokens(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        sm.update_tokens(1000, 200)

        sm2 = SessionManager("task1", base_dir=tmp_path)
        state = sm2.init_session()
        assert state.total_tokens.input_tokens == 1000
        assert state.total_tokens.output_tokens == 200

    def test_preserves_compaction_summaries(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        sm.add_compaction_summary("Floor 2 cleared")

        sm2 = SessionManager("task1", base_dir=tmp_path)
        state = sm2.init_session()
        assert state.compaction_summaries == ["Floor 2 cleared"]

    def test_resets_step_count(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        sm.update_step_count(25)

        sm2 = SessionManager("task1", base_dir=tmp_path)
        state = sm2.init_session()
        assert state.step_count == 0

    def test_appends_session_header_to_transcript(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session(model="claude-sonnet")

        entries = sm.load_history()
        assert len(entries) == 1
        assert entries[0].type == "session"
        assert entries[0].data["model"] == "claude-sonnet"
        assert entries[0].data["run_number"] == 1


# ---------------------------------------------------------------------------
# SessionManager — save/load state
# ---------------------------------------------------------------------------


class TestSaveLoadState:
    def test_roundtrip(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        sm.update_tokens(500, 100)

        sm2 = SessionManager("task1", base_dir=tmp_path)
        state = sm2.load_state()
        assert state is not None
        assert state.run_number == 1
        assert state.total_tokens.input_tokens == 500

    def test_missing_returns_none(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        assert sm.load_state() is None

    def test_corrupt_returns_none(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.task_dir.mkdir(parents=True)
        sm.state_path.write_text("not json", encoding="utf-8")
        assert sm.load_state() is None

    def test_updated_at_changes(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        first_updated = sm.load_state().updated_at

        sm.update_tokens(1, 1)
        second_updated = sm.load_state().updated_at
        assert second_updated >= first_updated


# ---------------------------------------------------------------------------
# SessionManager — append_message
# ---------------------------------------------------------------------------


class TestAppendMessage:
    def test_single_message_string(self, tmp_path):
        """String content is auto-wrapped as content array."""
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        entry = sm.append_message("assistant", "I'll click the door.")
        assert entry.type == "message"
        assert entry.data["message"]["role"] == "assistant"
        content = entry.data["message"]["content"]
        assert content == [{"type": "text", "text": "I'll click the door."}]

    def test_content_array(self, tmp_path):
        """Content array with multiple block types."""
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        blocks = [
            {"type": "text", "text": "Let me search memory"},
            {"type": "toolCall", "id": "call_1", "name": "memory_search", "arguments": "{}"},
        ]
        entry = sm.append_message("assistant", blocks, stop_reason="tool_use")
        content = entry.data["message"]["content"]
        assert len(content) == 2
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "toolCall"
        assert content[1]["name"] == "memory_search"

    def test_tool_result_message(self, tmp_path):
        """Tool result messages with toolResult role."""
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        entry = sm.append_message(
            "toolResult",
            [{"type": "text", "text": "Search returned 3 results"}],
        )
        assert entry.data["message"]["role"] == "toolResult"
        assert entry.data["message"]["content"][0]["text"] == "Search returned 3 results"

    def test_computer_call_message(self, tmp_path):
        """Computer call actions in content array."""
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        entry = sm.append_message(
            "assistant",
            [{"type": "computer_call", "id": "cc_1", "action": {"type": "click", "x": 100, "y": 200}}],
            stop_reason="tool_use",
        )
        content = entry.data["message"]["content"]
        assert content[0]["type"] == "computer_call"
        assert content[0]["action"]["type"] == "click"

    def test_image_reference(self, tmp_path):
        """Screenshot image references in tool results."""
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        entry = sm.append_message(
            "toolResult",
            [{"type": "image", "source": "trajectory"}],
        )
        assert entry.data["message"]["content"][0]["type"] == "image"

    def test_multiple_messages(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        sm.append_message("assistant", "Action 1")
        sm.append_message("user", "Result 1")
        sm.append_message("assistant", "Action 2")

        entries = sm.load_history()
        messages = [e for e in entries if e.type == "message"]
        assert len(messages) == 3

    def test_parent_id_chain(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        e1 = sm.append_message("assistant", "A")
        e2 = sm.append_message("user", "B")
        e3 = sm.append_message("assistant", "C")

        # Each message's parentId should point to the previous entry
        assert e2.parent_id == e1.id
        assert e3.parent_id == e2.id

    def test_usage_tracking(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        entry = sm.append_message(
            "assistant",
            "Hello",
            usage={"input": 100, "output": 20, "total": 120, "cost": 0.001},
            stop_reason="end_turn",
        )
        msg = entry.data["message"]
        assert msg["usage"]["input"] == 100
        assert msg["stopReason"] == "end_turn"


# ---------------------------------------------------------------------------
# SessionManager — load_history
# ---------------------------------------------------------------------------


class TestLoadHistory:
    def test_read_all_entries(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        sm.append_message("assistant", "Run 1 action")
        sm.init_session()
        sm.append_message("assistant", "Run 2 action")

        entries = sm.load_history()
        assert len(entries) == 4  # 2 session headers + 2 messages

    def test_filter_by_run_number(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        sm.append_message("assistant", "Run 1 action")
        sm.init_session()
        sm.append_message("assistant", "Run 2 action")

        run1 = sm.load_history(run_number=1)
        messages_r1 = [e for e in run1 if e.type == "message"]
        assert len(messages_r1) == 1
        assert messages_r1[0].data["message"]["content"][0]["text"] == "Run 1 action"

        run2 = sm.load_history(run_number=2)
        messages_r2 = [e for e in run2 if e.type == "message"]
        assert len(messages_r2) == 1
        assert messages_r2[0].data["message"]["content"][0]["text"] == "Run 2 action"

    def test_empty_transcript(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        assert sm.load_history() == []

    def test_nonexistent_run_returns_empty(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        sm.append_message("assistant", "Hello")
        assert sm.load_history(run_number=99) == []


# ---------------------------------------------------------------------------
# SessionManager — update_tokens
# ---------------------------------------------------------------------------


class TestUpdateTokens:
    def test_accumulation(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        sm.update_tokens(1000, 200)
        sm.update_tokens(500, 100)

        state = sm.load_state()
        assert state.total_tokens.input_tokens == 1500
        assert state.total_tokens.output_tokens == 300

    def test_persistence(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        sm.update_tokens(1000, 200)

        sm2 = SessionManager("task1", base_dir=tmp_path)
        state = sm2.load_state()
        assert state.total_tokens.input_tokens == 1000


# ---------------------------------------------------------------------------
# SessionManager — compaction
# ---------------------------------------------------------------------------


class TestCompaction:
    def test_add_summary(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        sm.add_compaction_summary("Floor 2 cleared")

        state = sm.load_state()
        assert state.compaction_count == 1
        assert state.compaction_summaries == ["Floor 2 cleared"]

    def test_increment_count(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        sm.add_compaction_summary("Summary 1")
        sm.add_compaction_summary("Summary 2")

        state = sm.load_state()
        assert state.compaction_count == 2

    def test_get_summaries(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        sm.add_compaction_summary("S1")
        sm.add_compaction_summary("S2")

        assert sm.get_compaction_summaries() == ["S1", "S2"]

    def test_get_summaries_without_init(self, tmp_path):
        """get_compaction_summaries loads from disk if no state in memory."""
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        sm.add_compaction_summary("Persisted")

        sm2 = SessionManager("task1", base_dir=tmp_path)
        assert sm2.get_compaction_summaries() == ["Persisted"]

    def test_append_compaction_entry(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        sm.append_message("assistant", "Action")
        entry = sm.append_compaction("Summary text", "msg-kept-123", 95000)

        assert entry.type == "compaction"
        assert entry.data["summary"] == "Summary text"
        assert entry.data["firstKeptEntryId"] == "msg-kept-123"
        assert entry.data["tokensBefore"] == 95000

        # Also updates state
        state = sm.load_state()
        assert state.compaction_count == 1
        assert state.compaction_summaries == ["Summary text"]

    def test_compaction_in_transcript(self, tmp_path):
        sm = SessionManager("task1", base_dir=tmp_path)
        sm.init_session()
        sm.append_compaction("Compacted", "msg-1", 50000)

        entries = sm.load_history()
        compactions = [e for e in entries if e.type == "compaction"]
        assert len(compactions) == 1
        assert compactions[0].data["summary"] == "Compacted"
