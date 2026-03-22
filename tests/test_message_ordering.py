"""Tests for US-OC-036: Post-compaction message ordering.

Ensures _build_compacted_items never produces a list ending with role=assistant,
which would cause API errors for models that don't support assistant prefill
(e.g., Opus 4.6).
"""

def _build_compacted_items_standalone(summary: str, kept_messages: list[dict]) -> list[dict]:
    """Standalone version of OpenClawComputerAgent._build_compacted_items for testing.

    Avoids instantiating the full agent class (requires async setup, VM connection, etc.).
    Must be kept in sync with the real implementation.
    """
    items: list[dict] = []

    if summary:
        items.append({
            "role": "user",
            "content": (
                "## Prior Context (Compacted)\n"
                "The following is a summary of earlier conversation history that was "
                "compacted to save context space. Use this to maintain continuity.\n\n"
                f"{summary}"
            ),
        })

    if kept_messages:
        items.extend(kept_messages)

    # Guard: ensure items don't end with role=assistant
    if items and items[-1].get("role") == "assistant":
        items.append({
            "role": "user",
            "content": "[Continue from where you left off.]",
        })

    return items


class TestPostCompactionMessageOrdering:
    """US-OC-036: Post-compaction message list must not end with role=assistant."""

    def test_trailing_assistant_gets_user_appended(self):
        """When kept_messages ends with assistant, a user message is appended."""
        kept = [
            {"role": "user", "content": "Do something"},
            {"role": "assistant", "content": "I did it"},
        ]
        result = _build_compacted_items_standalone("Summary of prior work", kept)

        assert result[-1]["role"] == "user"
        assert result[-1]["content"] == "[Continue from where you left off.]"
        assert len(result) == 4  # summary + 2 kept + 1 appended

    def test_trailing_user_no_change(self):
        """When kept_messages ends with user, no extra message is added."""
        kept = [
            {"role": "assistant", "content": "I did something"},
            {"role": "user", "content": "Thanks, now do more"},
        ]
        result = _build_compacted_items_standalone("Summary", kept)

        assert result[-1]["role"] == "user"
        assert result[-1]["content"] == "Thanks, now do more"
        assert len(result) == 3  # summary + 2 kept

    def test_trailing_tool_no_change(self):
        """When kept_messages ends with tool result, no extra message is added."""
        kept = [
            {"role": "assistant", "content": "Calling tool"},
            {"role": "tool", "content": "Tool result here"},
        ]
        result = _build_compacted_items_standalone("Summary", kept)

        assert result[-1]["role"] == "tool"
        assert len(result) == 3  # summary + 2 kept

    def test_empty_kept_messages(self):
        """Summary-only (no kept messages) ends with user (the summary)."""
        result = _build_compacted_items_standalone("Summary of everything", [])

        assert result[-1]["role"] == "user"
        assert len(result) == 1

    def test_only_assistant_in_kept(self):
        """Single assistant message in kept gets a user tail appended."""
        kept = [{"role": "assistant", "content": "Last thing I said"}]
        result = _build_compacted_items_standalone("Summary", kept)

        assert result[-1]["role"] == "user"
        assert len(result) == 3  # summary + 1 kept + 1 appended
