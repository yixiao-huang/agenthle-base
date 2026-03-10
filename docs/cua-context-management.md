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

## Context Window Composition

Each turn, the full context sent to the API is `old_items + new_items`, processed by a callback chain. Here is the complete structure:

```
┌─────────────────────────────────────────────────────────────────┐
│  CONTEXT SENT TO API (each turn)                                │
│                                                                  │
│  ── Prepended by PromptInstructionsCallback (never truncated) ── │
│  [user] instructions= text                                       │
│         (includes TASK_MEMORY.md + MEMORY.md + tool guidance)    │
│                                                                  │
│  ── Original input (old_items) ──────────────────────────────── │
│  [user] task_description (the actual task instruction)           │
│                                                                  │
│  ── Accumulated per-turn items (new_items) ──────────────────── │
│  For each past turn, some subset of:                             │
│                                                                  │
│    [reasoning]            agent thinking (summary text)          │
│    [computer_call]        action intent (click, type, screenshot)│
│    [computer_call_output] screenshot image (base64)              │
│    [message]              agent text monologue                   │
│    [function_call]        tool invocation (memory_search, etc.)  │
│    [function_call_output] tool result text                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Item types and token cost

| Item type | Content | Token cost | Frequency |
|-----------|---------|------------|-----------|
| `user` (instructions) | TASK_MEMORY.md + MEMORY.md + tool guidance | Medium (depends on memory size) | Prepended every turn by PromptInstructionsCallback |
| `user` (task) | Task description from solver | Small (~100 tokens) | 1 total (in old_items) |
| `reasoning` | Agent's thinking summary, e.g. "Clicking Start Game option" | Small (~10-50 tokens) | 0-1 per turn |
| `computer_call` | Action payload: `{type: "click", x: 485, y: 438}` | Small (~30 tokens) | 1 per turn |
| `computer_call_output` | Screenshot as base64 image | **Large** (~1000+ image tokens) | 1 per turn |
| `message` | Agent text monologue, e.g. "I see the game menu..." | Medium (~50-200 tokens) | 0-1 per turn (not every turn produces one) |
| `function_call` | Tool name + args JSON, e.g. `memory_search(keywords=["floor"])` | Small (~30 tokens) | 0-1 per turn (only when agent invokes a tool) |
| `function_call_output` | Tool result text (search results, file content) | Medium (~100-500 tokens) | 0-1 per turn (paired with function_call) |

### Callback chain (executed in order before API call)

```
combined_messages = old_items + new_items
        │
        ▼
1. OperatorNormalizerCallback    — normalizes operator names
2. PromptInstructionsCallback    — prepends [user] with instructions= text
3. LoggingCallback               — logs messages (if verbosity set)
4. ImageRetentionCallback        — removes old screenshot triplets (keeps N most recent)
5. TrajectorySaverCallback       — saves full context to api_start.json on disk
6. BudgetManagerCallback         — stops if token budget exceeded
7. (any user-provided callbacks)
        │
        ▼
predict_step() → API call with truncation: "auto"
```

### Per-turn accumulation

After the API responds, two things are appended to `new_items`:
1. **Agent output** (`new_items += result.get("output")`) — reasoning, computer_call, message, function_call items
2. **Tool execution results** (`new_items += partial_items`) — computer_call_output (screenshots), function_call_output

This means `new_items` grows by 2-5 items per turn. At turn 100, there are ~300+ items before any truncation.

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

### Current mitigations

1. **Planner-driven observation flush** — every 10 steps, a planner LLM (gpt-4.1-mini) summarizes the agent's reasoning buffer and writes observations to `session-NNN.md`. This captures knowledge before it's lost to truncation.
2. **memory_search/memory_get** (read-only) — the agent can search and read session logs and TASK_MEMORY.md even after its own context has been truncated.
3. **Post-session compaction** — planner merges session log into TASK_MEMORY.md, injected into `instructions=` at the start of the next session.

### Remaining gaps

1. **No within-session context compaction** — the planner writes to the session log file, but this doesn't help the agent's *current* context window. The agent can't benefit from planner-written observations unless it explicitly calls memory_search. There's no mechanism to feed planner summaries back into the agent's context.
2. **`message` items are unmanaged** — they survive ImageRetentionCallback (not part of triplets) but accumulate until OpenAI's truncation blindly drops them. These are the agent's text monologues and often contain valuable observations. A compaction strategy could summarize older `message` items before they're lost.
3. **`function_call_output` items are ephemeral** — memory search/get results are gone by turn 100. The agent only benefits from tool results in the turn they're retrieved. **Note:** With the planner-driven architecture, the agent's function calls are limited to read-only `memory_search` and `memory_get`, whose results are meant to be acted on immediately. We speculate that losing these from context doesn't affect the workflow — but this assumption needs verification during real multi-session runs. Track in the compaction PRD.

## Key Source Files

| File | What it does |
|------|-------------|
| `agent/agent.py` lines 658-808 | Main agent loop, `new_items` accumulation |
| `agent/callbacks/image_retention.py` | `ImageRetentionCallback` — triplet removal |
| `agent/callbacks/base.py` | `AsyncCallbackHandler` — all available lifecycle hooks |
| `agent/callbacks/trajectory_saver.py` | `TrajectorySaverCallback` — saves full trajectory to disk |
