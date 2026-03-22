"""Tests for ImageRetentionCallback — ensures old screenshots are removed
without breaking tool_use/tool_result pairing.

Key scenario: computer_20251124 models (Opus 4.6) return both function_call
and computer_call in the same response, causing function_call_output to be
interleaved between computer_call and computer_call_output. The callback must
find the matching computer_call by call_id, not by position.
"""

from agent.callbacks.image_retention import ImageRetentionCallback


def _make_computer_call(call_id: str, action_type: str = "click") -> dict:
    return {"type": "computer_call", "call_id": call_id, "action": {"type": action_type}}


def _make_computer_call_output(call_id: str, image_url: str = "data:image/png;base64,abc") -> dict:
    return {
        "type": "computer_call_output",
        "call_id": call_id,
        "output": {"type": "input_image", "image_url": image_url},
    }


def _make_function_call(call_id: str, name: str = "memory_search") -> dict:
    return {"type": "function_call", "call_id": call_id, "name": name, "arguments": "{}"}


def _make_function_call_output(call_id: str, output: str = "result") -> dict:
    return {"type": "function_call_output", "call_id": call_id, "output": output}


def _make_reasoning() -> dict:
    return {"type": "reasoning", "id": "r1", "summary": [{"type": "summary_text", "text": "thinking"}]}


def _make_user_msg(text: str = "hello") -> dict:
    return {"type": "message", "role": "user", "content": text}


# ---------------------------------------------------------------------------
# Adjacent pairs (original behavior — should still work)
# ---------------------------------------------------------------------------

def test_adjacent_pairs_keep_recent():
    """With 3 adjacent screenshot pairs, keep=2 removes the oldest."""
    cb = ImageRetentionCallback(only_n_most_recent_images=2)
    messages = [
        _make_user_msg("start"),
        _make_computer_call("c1"),
        _make_computer_call_output("c1"),
        _make_computer_call("c2"),
        _make_computer_call_output("c2"),
        _make_computer_call("c3"),
        _make_computer_call_output("c3"),
    ]
    result = cb._apply_image_retention(messages)
    # c1 pair removed, c2 and c3 kept
    types = [(m.get("type"), m.get("call_id")) for m in result]
    assert ("computer_call", "c1") not in types
    assert ("computer_call_output", "c1") not in types
    assert ("computer_call", "c2") in types
    assert ("computer_call_output", "c2") in types
    assert ("computer_call", "c3") in types
    assert ("computer_call_output", "c3") in types


def test_no_removal_when_under_limit():
    """When image count <= limit, nothing is removed."""
    cb = ImageRetentionCallback(only_n_most_recent_images=5)
    messages = [
        _make_computer_call("c1"),
        _make_computer_call_output("c1"),
        _make_computer_call("c2"),
        _make_computer_call_output("c2"),
    ]
    result = cb._apply_image_retention(messages)
    assert len(result) == len(messages)


def test_none_limit_passes_through():
    """When only_n_most_recent_images is None, messages pass through unchanged."""
    cb = ImageRetentionCallback(only_n_most_recent_images=None)
    messages = [_make_computer_call("c1"), _make_computer_call_output("c1")] * 10
    result = cb._apply_image_retention(messages)
    assert len(result) == len(messages)


# ---------------------------------------------------------------------------
# Interleaved pairs (the bug fix — function_call_output between call/output)
# ---------------------------------------------------------------------------

def test_interleaved_function_call_output():
    """When function_call_output sits between computer_call and computer_call_output,
    the callback must still find and remove the matching computer_call by call_id."""
    cb = ImageRetentionCallback(only_n_most_recent_images=1)
    messages = [
        _make_user_msg("start"),
        # Turn 1: model returns function_call + computer_call together
        _make_function_call("fc1"),
        _make_computer_call("cc1"),
        _make_function_call_output("fc1"),  # interleaved!
        _make_computer_call_output("cc1"),
        _make_user_msg("screenshot path 1"),
        # Turn 2: simple computer_call
        _make_computer_call("cc2"),
        _make_computer_call_output("cc2"),
    ]
    result = cb._apply_image_retention(messages)

    types = [(m.get("type"), m.get("call_id")) for m in result]
    # cc1 pair should be removed (oldest), cc2 kept (most recent)
    assert ("computer_call", "cc1") not in types
    assert ("computer_call_output", "cc1") not in types
    # function_call and its output should be preserved
    assert ("function_call", "fc1") in types
    assert ("function_call_output", "fc1") in types
    # cc2 kept
    assert ("computer_call", "cc2") in types
    assert ("computer_call_output", "cc2") in types


def test_interleaved_with_reasoning():
    """Reasoning before computer_call should also be removed when the pair is removed."""
    cb = ImageRetentionCallback(only_n_most_recent_images=1)
    messages = [
        _make_reasoning(),
        _make_computer_call("cc1"),
        _make_function_call_output("fc0"),  # interleaved
        _make_computer_call_output("cc1"),
        # Second pair (kept)
        _make_computer_call("cc2"),
        _make_computer_call_output("cc2"),
    ]
    result = cb._apply_image_retention(messages)

    types = [m.get("type") for m in result]
    assert "reasoning" not in types  # reasoning before cc1 removed
    assert ("computer_call", "cc1") not in [(m.get("type"), m.get("call_id")) for m in result]


def test_multiple_interleaved_removals():
    """Multiple old interleaved pairs are all correctly removed."""
    cb = ImageRetentionCallback(only_n_most_recent_images=1)
    messages = [
        # Turn 1: interleaved
        _make_function_call("fc1"),
        _make_computer_call("cc1"),
        _make_function_call_output("fc1"),
        _make_computer_call_output("cc1"),
        # Turn 2: interleaved
        _make_function_call("fc2"),
        _make_computer_call("cc2"),
        _make_function_call_output("fc2"),
        _make_computer_call_output("cc2"),
        # Turn 3: simple (kept)
        _make_computer_call("cc3"),
        _make_computer_call_output("cc3"),
    ]
    result = cb._apply_image_retention(messages)

    call_ids = [(m.get("type"), m.get("call_id")) for m in result]
    # cc1 and cc2 pairs removed
    assert ("computer_call", "cc1") not in call_ids
    assert ("computer_call_output", "cc1") not in call_ids
    assert ("computer_call", "cc2") not in call_ids
    assert ("computer_call_output", "cc2") not in call_ids
    # function calls preserved
    assert ("function_call", "fc1") in call_ids
    assert ("function_call", "fc2") in call_ids
    # cc3 kept
    assert ("computer_call", "cc3") in call_ids
    assert ("computer_call_output", "cc3") in call_ids
