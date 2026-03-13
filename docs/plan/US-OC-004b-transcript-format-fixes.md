# US-OC-004b: Transcript JSONL Format Fixes

## Context

US-OC-004 implemented `SessionManager` + transcript.jsonl. Investigation of the actual
runtime `openclaw_sessions/mota_24_easy/transcript.jsonl` against the golden reference
(OpenClaw `transcript.ts` + `sessions.test.ts` + plan doc spec) reveals 5 concrete problems.
US-OC-004b fixes them before US-OC-006 (Compaction Pipeline) consumes the transcript.

---

## Investigation: Transcript Differences

### Problem 1 — Turn fragmentation (most critical)

A single agent step yields `result["output"]` with multiple items (text + tool call).
We currently log **one message entry per output item**, so a step with text + tool_call
produces 2 separate assistant entries:

```
Line N:   {"role": "assistant", "content": [{"type":"text","text":"..."}], "usage":{...}}
Line N+1: {"role": "assistant", "content": [{"type":"toolCall",...}], "stopReason":"tool_use"}
```

**Problems:**
- Usage only on the first entry, not associated with the tool call
- Two assistant entries in a row violates the user/assistant alternation expected by APIs
- Compaction (US-OC-006) receives incoherent "turns" instead of logical messages
- Cannot replay transcript as API messages without complex reconstruction

**Golden reference (sessions.test.ts + transcript.ts):**
One message entry per logical turn — assistant turn with all content blocks together.

### Problem 2 — `role: "toolResult"` is non-standard

We use `role: "toolResult"` for all tool and computer call outputs.

**Problems:**
- Not a valid API role (`user`, `assistant`, `tool` are the valid roles)
- Can't round-trip to API without remapping
- Differs from OpenClaw which uses standard roles

**Fix:** Use `role: "tool"` (OpenAI Responses API standard for tool results).

### Problem 3 — `usage.total` missing

Plan doc spec shows `usage: {input, output, total, cost}` but we write `{input, output, cost}`.
`total` = `input + output` is trivial to compute but missing.

### Problem 4 — Content block type inconsistency

We write `type: "toolCall"` in content blocks but:
- CUA SDK uses `type: "function_call"` for tool calls
- OpenClaw uses `type: "tool_use"` (Anthropic API format)

`type: "toolCall"` is a made-up name that doesn't match any standard.
Fix: use `type: "function_call"` to match the CUA SDK / OpenAI Responses API.

### Problem 5 — Missing `api` field on messages

OpenClaw includes `api: "openai-responses"` on each assistant message for observability.
We don't include this. Minor but useful for identifying which API generated each turn.

---

## What the Golden Reference Looks Like

**Session header (from `transcript.ts` `ensureSessionHeader`):**
```json
{"type":"session","version":1,"id":"sess-...","timestamp":"...","cwd":"/path"}
```
Our additions (`parentId`, `task_id`, `run_number`, `model`) are intentional CUA-specific metadata — keep them.

**Message entry — assistant turn with text + tool call:**
```json
{
  "type": "message", "id": "msg-...", "parentId": "...", "timestamp": "...",
  "message": {
    "role": "assistant",
    "content": [
      {"type": "text", "text": "I'll search memory first."},
      {"type": "function_call", "id": "call_...", "name": "memory_search", "arguments": "{...}"}
    ],
    "usage": {"input": 3402, "output": 93, "total": 3495, "cost": 0.011601},
    "stopReason": "tool_use",
    "api": "openai-responses"
  }
}
```

**Tool result entry:**
```json
{
  "type": "message", "id": "msg-...", "parentId": "...", "timestamp": "...",
  "message": {
    "role": "tool",
    "content": [
      {"type": "tool_result", "tool_use_id": "call_...", "content": "result text"},
      {"type": "tool_result", "tool_use_id": "call_...", "content": "image:trajectory"}
    ]
  }
}
```

---

## OpenClaw Design Rationale

### What OpenClaw Does
OpenClaw's pi-coding-agent SessionManager writes one entry per logical message using
`appendMessage({role, content[], usage:{input,output,cacheRead,cacheWrite,totalTokens,cost:{...}},api,provider,model,stopReason,timestamp})`.
Each turn (user sends, assistant responds with tool calls, tool results come back) produces
exactly one assistant entry and one user/tool entry.

### What We Keep and Why
- `parentId` chain — same linked-list traversal as OpenClaw; needed for compaction entry referencing
- `type: "message"` wrapping — identical to OpenClaw's format
- `role: "assistant"` / `role: "tool"` — standard roles matching OpenAI Responses API
- `usage.{input,output,total,cost}` — matches plan doc spec; total makes compaction token estimation trivial

### What We Drop and Why
- `usage.cacheRead`, `usage.cacheWrite` — CUA SDK (via OpenAI Responses API) doesn't return these; can add when SDK exposes them
- `usage.cost` as nested object `{input,output,...}` — CUA SDK returns a flat `response_cost` float; keep flat
- `api`, `provider`, `model` per message — add `api` only (matches observable benefit; `provider`/`model` redundant with session header)

### Key Differences from OpenClaw
1. `cost` is a flat float not a nested object (CUA SDK constraint)
2. No `cacheRead`/`cacheWrite` in usage (CUA SDK doesn't surface them)
3. No `provider`/`model` per message (session header has this, no per-turn model switching in CUA)
4. Computer calls represented as content blocks (no OpenClaw equivalent; CUA-specific)

---

## Implementation Plan

### File 1 (MODIFY): `submodules/cua/libs/cua-bench/cua_bench/agents/openclaw_agent.py`

Replace the per-item logging loop with a turn-aware grouping approach.

**Logic (replaces the `for item in result["output"]` loop for transcript logging):**

```python
# Group step output into logical turns
assistant_content = []   # text + function_call + computer_call blocks
tool_results = []        # function_call_output + computer_call_output blocks

for item in result["output"]:
    item_type = item.get("type")
    if item_type == "message":
        for block in item.get("content", []):
            if block.get("text"):
                assistant_content.append({"type": "text", "text": block["text"]})
    elif item_type == "function_call":
        assistant_content.append({
            "type": "function_call",
            "id": item.get("call_id", ""),
            "name": item.get("name", ""),
            "arguments": item.get("arguments", ""),
        })
    elif item_type == "computer_call":
        assistant_content.append({
            "type": "computer_call",
            "id": item.get("call_id", ""),
            "action": item.get("action", {}),
        })
    elif item_type == "function_call_output":
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": item.get("call_id", ""),
            "content": item.get("output", ""),
        })
    elif item_type == "computer_call_output":
        output = item.get("output", {})
        content_str = (
            "image:trajectory"
            if isinstance(output, dict) and output.get("type") == "input_image"
            else str(output)[:500]
        )
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": item.get("call_id", ""),
            "content": content_str,
        })

# Log assistant turn (one entry per step, even if only tool calls, no text)
if assistant_content:
    usage = {
        "input": step_input,
        "output": step_output,
        "total": step_input + step_output,
        "cost": result["usage"].get("response_cost", 0),
    }
    has_tools = any(b["type"] in ("function_call", "computer_call") for b in assistant_content)
    session_mgr.append_message(
        "assistant",
        assistant_content,
        usage=usage,
        stop_reason=result.get("stop_reason") or ("tool_use" if has_tools else None),
        api="openai-responses",
    )

# Log tool results (one entry batching all results from this step)
if tool_results:
    session_mgr.append_message("tool", tool_results)
```

### File 2 (MODIFY): `submodules/cua/libs/cua-bench/cua_bench/agents/openclaw/session.py`

Add optional `api` parameter to `append_message`:

```python
def append_message(
    self,
    role: str,
    content: str | list[dict[str, Any]],
    usage: dict[str, Any] | None = None,
    stop_reason: str | None = None,
    api: str | None = None,          # NEW: e.g. "openai-responses"
) -> TranscriptEntry:
```

Inside, add `if api is not None: message_data["api"] = api` before building the entry.

### File 3 (MODIFY): `tests/test_openclaw_session.py`

Add 2 tests:
- `test_append_message_with_api_field` — api="openai-responses" appears in serialized message dict
- `test_append_message_no_api_field` — api=None → key absent from serialized dict

### File 4 (NEW): `tests/test_openclaw_transcript_format.py`

8 tests exercising the grouping logic directly (mock `result["output"]` structures, call the
grouping logic, verify transcript entries):

| Test | Verifies |
|------|---------|
| `test_assistant_turn_grouping` | Text + tool call → 1 assistant entry with 2 content blocks |
| `test_tool_result_grouping` | Two tool results → 1 `role:"tool"` entry with 2 `tool_result` blocks |
| `test_usage_total` | `usage.total == usage.input + usage.output` |
| `test_role_is_tool_not_tool_result` | No `"toolResult"` role appears |
| `test_function_call_type` | Content block type is `"function_call"` not `"toolCall"` |
| `test_computer_call_grouping` | Computer call block grouped with text in assistant entry |
| `test_computer_result_tool_role` | computer_call_output → `role:"tool"` entry |
| `test_no_consecutive_assistant_entries` | After grouping, no two adjacent entries both have `role:"assistant"` |

---

## Acceptance Criteria

- Level 1: `uv run ruff check .` — lint passes
- Level 1: `uv run pytest tests/ -v` — all existing 58+ tests pass
- Level 1: `tests/test_openclaw_transcript_format.py` — 8 new tests pass
- Level 1: `tests/test_openclaw_session.py` — 2 new `api` field tests pass
- Level 1: `role: "toolResult"` never appears in new transcripts
- Level 1: `usage.total` present in every assistant message with usage
- Level 2: `run_magic_tower.sh 50` — transcript shows ≤2 entries per step (no consecutive assistant entries)

---

## Files Changed

| File | Change |
|------|--------|
| `submodules/cua/.../openclaw_agent.py` | Replace per-item loop with turn-aware grouping |
| `submodules/cua/.../openclaw/session.py` | Add `api` param to `append_message` |
| `tests/test_openclaw_session.py` | +2 tests for `api` field |
| `tests/test_openclaw_transcript_format.py` | NEW — 8 format correctness tests |
