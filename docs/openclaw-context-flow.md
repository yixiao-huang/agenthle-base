# OpenClaw Context Management — Reference Extract

Extracted from `openclaw-context-flow.html` (interactive visual version for browsers).
This markdown version is for AI agent consumption — covers the architecture decisions and implementation details most relevant to TinyClaw.

<!-- Last updated: 2026-03-08 -->

## Architecture Overview

OpenClaw is a personal AI assistant running across 20+ messaging channels. Its context management has 5 phases:

```
Inbound Message → Route Resolution → Message Queue (per-session FIFO)
    → runEmbeddedPiAgent() (main orchestrator, retry loop)
        → runEmbeddedAttempt() (single attempt):
            1. Load session .jsonl (replay or compaction summary)
            2. resolveBootstrapContext() (SOUL.md, AGENTS.md, USER.md, IDENTITY.md)
            3. buildAgentSystemPrompt() (8 sections, rebuilt every call)
            4. Construct API request: { system, messages[], tools[] }
            5. streamSimple() → LLM API (SSE streaming)
            6. Tool execution loop (sequential, interruptible)
            7. Persist to .jsonl
            8. Check context overflow → compaction if needed
```

## Phase 2: System Prompt Construction

### buildAgentSystemPrompt() — 8 Sections

Rebuilt on every LLM call from current workspace files. NOT persisted in .jsonl.

1. **Base instructions** — "You are a personal assistant running inside OpenClaw"
2. **Tool catalog** — one-line descriptions, filtered by profile (minimal/coding/full)
3. **Safety & constitutional rules**
4. **Memory instructions** — tells agent to use `memory_search` (memory content NOT injected)
5. **Skills section** — lists available skills, instructs to read SKILL.md when relevant
6. **Workspace files** — full text of SOUL.md, AGENTS.md, USER.md injected inline
7. **User identity + timezone**
8. **Runtime info** — `agent=main model=claude-opus-4-6`

### Memory Recall Section (verbatim from source)

```
## Memory Recall
Before answering anything about prior work, decisions, dates, people,
preferences, or todos: run memory_search on MEMORY.md + memory/*.md;
then use memory_get to pull only the needed lines. If low confidence
after search, say you checked.

Citations are disabled: do not mention file paths or line numbers in
replies unless the user explicitly asks.
```

**Key design: MEMORY.md is NOT injected into the system prompt.** Accessed on-demand via `memory_search` tool calls. Reasons:
- Memory files can be very large — injecting wastes context tokens
- Agent retrieves only what it needs
- Security: in group chats, MEMORY.md is not indexed (prevents personal context leaking)

### Bootstrap File Trimming

Two budget limits:
- **Per-file**: `DEFAULT_BOOTSTRAP_MAX_CHARS = 20,000`
- **Total**: `DEFAULT_BOOTSTRAP_TOTAL_MAX_CHARS = 150,000`

Per-file trimming when over limit:
- Keep first **70%** from start (`BOOTSTRAP_HEAD_RATIO = 0.7`)
- Keep last **20%** from end (`BOOTSTRAP_TAIL_RATIO = 0.2`)
- Insert: `[...truncated, read {fileName} for full content...]`

Files processed sequentially. If remaining budget < 64 chars, remaining files skipped entirely.

## Phase 3: Tool Loop

### Tool Execution — Sequential with Interrupt

Multiple `tool_use` blocks in one response are executed **strictly sequentially** (not parallel):

```javascript
for (let i = 0; i < toolCalls.length; i++) {
  const result = await tool.execute(toolCall.id, validatedArgs, signal)
  results.push(toolResultMessage)

  // After each tool: check for user interrupt
  if (getSteeringMessages) {
    const steering = await getSteeringMessages()
    if (steering.length > 0) {
      // User typed something — skip remaining tools
      for (const skipped of toolCalls.slice(i+1))
        results.push(skipToolCall(skipped))
      break
    }
  }
}
```

Next LLM call only fires after ALL tool results are collected.

### Tool Schemas

System prompt contains plain-text tool summaries. Full JSON schemas go in the API `tools[]` parameter:

```json
{
  "name": "memory_search",
  "description": "Search memory files...",
  "input_schema": {
    "type": "object",
    "required": ["query"],
    "properties": {
      "query": { "type": "string" },
      "maxResults": { "type": "number" },
      "minScore": { "type": "number" }
    }
  }
}
```

Full tool catalog: `read, write, edit, apply_patch, exec, process, web_search, web_fetch, browser, canvas, memory_search, memory_get, sessions_list, sessions_history, sessions_send, sessions_spawn, message, cron, gateway, image, tts` (25+ tools).

## Phase 4: Compaction

### Overflow Detection

Two methods:
- **Proactive**: After each LLM response, `shouldCompact()` checks `contextTokens > contextWindow - reserveTokens`
- **Reactive**: LLM API returns "prompt too long" error

```javascript
const DEFAULT_COMPACTION_SETTINGS = {
  enabled: true,
  reserveTokens: 16384,
  keepRecentTokens: 20000,
};
const MAX_OVERFLOW_COMPACTION_ATTEMPTS = 3;
```

### Safeguard: Pre-Compaction Memory Flush

When `compaction.mode = "safeguard"`, a silent user message is injected before compaction:

```
Pre-compaction memory flush. Store durable memories now
(use memory/2026-03-06.md; create memory/ if needed).
IMPORTANT: If the file already exists, APPEND new content only.
If nothing to store, reply NO_REPLY.
Current time: Friday, March 6th, 2026
```

- One flush per compaction cycle (prevents loops)
- Agent actively decides what to preserve before forgetting
- Agent responds `NO_REPLY` if nothing worth saving — no user-visible output

### Compaction Summary — LLM Summarization

Dropped messages are serialized to text and sent to a summarization LLM:

```javascript
const response = await completeSimple(model, {
  systemPrompt: SUMMARIZATION_SYSTEM_PROMPT,
  messages: serializedConversation
}, {
  maxTokens: Math.floor(0.8 * reserveTokens),  // ~13,107 tokens
  reasoning: "high"
});
```

**System prompt:**
```
You are a context summarization assistant.
Your task is to read a conversation between a user and an AI coding
assistant, then produce a structured summary following the exact
format specified.
Do NOT continue the conversation. Do NOT respond to any questions
in the conversation. ONLY output the structured summary.
```

**User prompt (SUMMARIZATION_PROMPT):**
```
Create a structured context checkpoint summary that another LLM
will use to continue the work.

Use this EXACT format:
## Goal
## Constraints & Preferences
## Progress
  ### Done  /  ### In Progress  /  ### Blocked
## Key Decisions
## Next Steps
## Critical Context

Keep each section concise. Preserve exact file paths, function names,
and error messages.
```

**Three prompt variants:**
1. **Fresh** (`SUMMARIZATION_PROMPT`) — first compaction, full structured summary
2. **Incremental** (`UPDATE_SUMMARIZATION_PROMPT`) — merges new messages into existing summary
3. **Turn-prefix split** (`TURN_PREFIX_SUMMARIZATION_PROMPT`) — single turn too large, lower budget at 0.5× reserveTokens

**Safeguard mode extras** appended to summary:
- `## Tool Failures` — collected tool errors
- File operations — read/modified files listed as XML tags
- Workspace rules — "Session Startup" and "Red Lines" from AGENTS.md

### Tool Result Truncation (Fallback)

If compaction alone isn't enough:
- `HARD_MAX_TOOL_RESULT_CHARS = 400,000` (~100K tokens)
- Walks message history, truncates oversized tool results
- Only attempted after compaction has already run

### Recovery Decision Tree

1. No overflow → retry LLM with compacted context
2. Still overflowing, attempts < 3 → increment counter, retry
3. Still overflowing, no compaction yet → attempt compaction
4. Still overflowing after compaction → try tool result truncation (one-shot)
5. All exhausted → fatal error: "Context overflow: prompt too large"

## Phase 5: Sub-Agents

`sessions_spawn` creates an isolated child session running full `runEmbeddedPiAgent()` recursively:
- Own session .jsonl, own system prompt, own tool loop
- **Blocking**: parent awaits the entire sub-agent run
- Child's final text becomes the parent's `tool_result`
- Depth limit via `getSubagentDepth()` prevents infinite recursion

## Session Persistence

### .jsonl Format

```
~/.openclaw/agents/<agentId>/sessions/
  sessions.json         // index: key → metadata
  <sessionId>.jsonl     // append-only transcript
```

Entry types: `session` (metadata), `model_change`, `message` (user/assistant/toolResult), `compaction` (summary + firstKeptEntryId), `custom`.

After compaction: messages before `firstKeptEntryId` are replaced by the compaction summary as the first user message.

Auto-prune: stale after 30 days, cap 500 sessions, rotate at 10 MB.

## Message Queue Modes

| Mode | Behavior |
|------|----------|
| **collect** (default) | Buffer messages while agent runs; deliver all as single batched turn |
| **steer** | Inject new message into current run (agent sees it mid-generation) |
| **followup** | Queue as new turn after current run finishes |
| **interrupt** | Cancel current run, start fresh with new message |
| **steer-backlog** | Steer current run + keep overflow for follow-up |

## TinyClaw Relevance Map

| OpenClaw Component | TinyClaw Story | What to Adopt |
|-------------------|---------------|---------------|
| Memory Recall prompt | US-MEM-RCL | Categorical triggers, mandatory framing, two-step search→get |
| Safeguard memory flush | US-MEM-004 | Trajectory-driven nudge (adapted: reads CUA trajectories instead of conversation) |
| Compaction prompts | US-MEM-CMP | Structured summary format, merge-with-existing pattern |
| MEMORY.md NOT injected | US-MEM-AGT | Validates TASK_MEMORY.md in `instructions` (always visible) vs memory files via tools |
| Bootstrap trimming | — | Not needed (TinyClaw's TASK_MEMORY.md is small enough) |
| Session .jsonl | — | Not adopted (CUA has its own trajectory system) |
| Sub-agents | — | Not adopted (single-agent benchmark) |
