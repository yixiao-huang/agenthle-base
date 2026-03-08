# CUA Agent Context Management

How the CUA `ComputerAgent` manages its conversation context across turns, and why this matters for TinyClaw.

## The Agent Loop

The core loop lives in `submodules/cua/libs/python/agent/agent/agent.py` (lines 658-808).

Each iteration:
1. Combines `old_items + new_items` into `combined_messages` (line 720)
2. Runs callbacks via `_on_llm_start` — including `ImageRetentionCallback` (line 722)
3. Sends preprocessed messages to the model via `predict_step` (line 766)
4. Appends **agent response** items to `new_items` (line 785): `new_items += result.get("output")`
5. Appends **tool execution results** to `new_items` (line 795): `new_items += partial_items`

Both agent outputs and tool results accumulate in `new_items` — nothing is selectively excluded at this stage.

## Two Layers of Truncation

### Layer 1: ImageRetentionCallback (client-side)

**File**: `submodules/cua/libs/python/agent/agent/callbacks/image_retention.py`

Controlled by `only_n_most_recent_images` (set to 3 in our agent). Before each API call, it:

1. Finds all `computer_call_output` items with an `image_url`
2. Keeps only the **N most recent** ones
3. For each removed `computer_call_output`, also removes:
   - The immediately preceding `computer_call` with matching `call_id`
   - The `reasoning` item immediately before that (if present)

Each old screenshot is removed as a **triplet**: `reasoning → computer_call → computer_call_output`.

### Layer 2: OpenAI `truncation: "auto"` (server-side)

The API call includes `truncation: "auto"`, which tells OpenAI to drop the oldest items when the token budget is exceeded. This is a second pass that trims whatever the client-side callback left behind.

## What Survives at Turn 100

Verified from real Magic Tower trajectory data (`turn_100/api_start.json`, 186-turn run):

| Item type | Count | Notes |
|-----------|-------|-------|
| `user` (instructions) | 2 | Always preserved (initial prompt + task description) |
| `message` (agent text) | 12 | Agent's text reflections from recent turns |
| `computer_call` | 3 | Most recent 3 actions (matching `only_n_most_recent_images=3`) |
| `computer_call_output` | 3 | Most recent 3 screenshots |
| `reasoning` | 0 | All removed — either by ImageRetentionCallback (triplet removal) or API truncation |
| `function_call` | 0 | Dropped by API truncation |
| `function_call_output` | 0 | Dropped by API truncation |

**Total: 20 items** out of ~300+ accumulated over 100 turns.

### Why `message` items survive but `reasoning` doesn't

- `message` items (the agent's text monologues) are **not adjacent** to `computer_call_output` items, so `ImageRetentionCallback` never targets them. They survive client-side filtering and only get trimmed by server-side `truncation: "auto"` when token budget is tight.
- `reasoning` items sit **immediately before** their `computer_call`, so they get removed as part of the triplet whenever the associated screenshot is dropped.

## Implication for TinyClaw

The agent's context is a **narrow sliding window**. After ~50 turns:
- All action history (what it did, what it saw) beyond the last 3 turns is gone
- All reasoning is gone
- Only a handful of text reflections remain, and those are from relatively recent turns

This causes the agent to:
- Forget strategies it tried 50+ turns ago
- Repeat failed approaches (observed in Magic Tower: cycling through arrow keys, WASD, clicking)
- Hallucinate progress it never made

TinyClaw addresses this by:
1. **MemoryFlushCallback** reads full reasoning from saved trajectory files (which are never truncated) and nudges the agent to distill observations into `session-NNN.md`
2. **memory_search/memory_get** let the agent recall from session logs even after context truncation
3. **Post-session compaction** merges session learnings into `TASK_MEMORY.md`, injected at the start of the next session

## Key Source Files

| File | What it does |
|------|-------------|
| `agent/agent.py` lines 658-808 | Main agent loop, `new_items` accumulation |
| `agent/callbacks/image_retention.py` | `ImageRetentionCallback` — triplet removal |
| `agent/callbacks/base.py` | `AsyncCallbackHandler` — all available lifecycle hooks |
| `agent/callbacks/trajectory_saver.py` | `TrajectorySaverCallback` — saves full trajectory to disk |
