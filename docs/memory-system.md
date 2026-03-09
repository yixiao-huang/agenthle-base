# Memory System Design: OpenClaw vs TinyClaw

This document captures the research on OpenClaw's production memory system and the proposed TinyClaw design for AgentHLE. TinyClaw is intentionally simpler — it takes the ideas that matter for a benchmark agent and leaves the rest behind.

For OpenClaw's full context management pipeline (system prompt construction, compaction prompts, tool loop, sub-agents), see [openclaw-context-flow.md](openclaw-context-flow.md). That doc covers the broader architecture; this doc focuses specifically on the memory subsystem.

## Part 1: OpenClaw Memory System (Reference)

OpenClaw is a personal AI assistant running across 20+ messaging channels. Its memory system is built for long-running, multi-session conversations with persistent user context.

### Storage

- **Backend**: SQLite with 5 tables (`files`, `chunks`, `chunks_fts`, `chunks_vec`, `embedding_cache`)
- **Files tracked**: `MEMORY.md`, `memory/*.md` (dated daily logs), session transcripts (JSONL)
- **Alternative backend**: QMD (external CLI for semantic search, falls back to builtin on failure)
- **Extension backend**: LanceDB (vector DB for episodic memory with auto-capture)

### Chunking

Content is split into overlapping segments before embedding:

```
Document (1200 tokens)
  ├─ Chunk 1: tokens   1-400  (lines 1-10)
  ├─ Chunk 2: tokens 320-720  (lines 8-18)   ← 80-token overlap
  └─ Chunk 3: tokens 640-1040 (lines 16-26)  ← 80-token overlap
```

- Default: 400 tokens/chunk, 80 tokens overlap
- Token estimation: 4 chars ~ 1 token (approximation, not precise)
- Each chunk retains `start_line`, `end_line`, `file_path`, `content_hash`

Why overlap? Without it, a paragraph split across two chunks loses its meaning at the boundary. Overlap ensures context is preserved.

### Search

Three modes available:

**Keyword (FTS5 + BM25)**
- SQLite FTS5 full-text search with BM25 ranking
- Stop word filtering
- Always available, no external dependencies

**Semantic (Vector similarity)**
- Embeds query via same provider used for chunks
- Cosine similarity against stored chunk embeddings
- Optional `sqlite-vec` extension for faster queries; falls back to pure JS cosine

**Hybrid (default)**
- Merges vector and keyword results: `score = 0.7 * vector_score + 0.3 * keyword_score`
- Deduplication across result sets
- Optional enhancements (all disabled by default):
  - **MMR** (Maximal Marginal Relevance): re-ranks for diversity, reduces redundant results
  - **Temporal decay**: `e^(-lambda * age_days)`, older memories score lower. Dated files parsed from filename (`memory/2026-03-07.md`). Undated files (MEMORY.md) unaffected.

### Embedding Providers

| Provider | Default Model | Notes |
|----------|--------------|-------|
| OpenAI | text-embedding-3-small | Batch API, cost-optimized |
| Gemini | gemini-embedding-001 | Free tier available |
| Voyage | voyage-4-large | High quality, premium |
| Mistral | mistral-embed | EU-friendly |
| Ollama | nomic-embed-text | 100% offline |
| Local | embeddinggemma-300m | node-llama-cpp, ~300M params |

Auto-detection order: openai -> gemini -> voyage -> mistral -> local -> FTS-only fallback.

### Embedding Cache

Identical content is never re-embedded:
- Cache key: `(provider, model, content_hash)`
- Stored in `embedding_cache` SQLite table
- On file change: content hash compared, only changed chunks re-embedded

### Sync

- **File watcher**: Chokidar monitors `MEMORY.md` and `memory/` directory
- **Debounce**: 1.5s after last change before re-indexing
- **Hash-based**: Only re-processes files whose content hash changed
- **Session sync**: Separate timer checks session transcript size/message deltas
- **Batch embedding**: Groups chunks for remote API calls (max 8000 tokens/batch, concurrency 4)

### Tools

Two tools available to the agent:

```
memory_search(query, maxResults?, minScore?)
  -> Returns: results with file path, line range, content, score, citations

memory_get(path, from?, lines?)
  -> Returns: file content with safe line-range extraction
```

The agent writes to memory indirectly — via file tools (it has access to the local filesystem) or via lifecycle hooks that export session summaries.

### Lifecycle Hooks

- `onSessionStart`: Sync memory index
- `onMessage`: LanceDB extension auto-captures memories via regex triggers ("remember", "prefer", etc.)
- `onSessionEnd`: Export session summary to memory file

### Pre-Compaction Memory Flush

When the agent's conversation approaches the context window limit, before compaction summarizes and discards old messages:

1. System detects context usage crossing a soft threshold (default 4000 tokens before compaction triggers)
2. Also triggers when transcript file exceeds 2MB (`forceFlushTranscriptBytes`)
3. Injects a **silent user message** prompting the agent to **append** to `memory/YYYY-MM-DD.md`
4. The prompt explicitly says: "If the file already exists, APPEND new content only and do not overwrite existing entries"
5. Agent writes using its file tools; uses `NO_REPLY` convention so the user sees nothing
6. Then compaction runs, summarizing old messages into a compact transcript entry (in-memory only — disk files untouched)
7. Fires once per compaction cycle (tracked via `memoryFlushCompactionCount`)

This is **agent-driven but system-triggered** — the system decides WHEN to prompt, the agent decides WHAT to save. Key insight: **compaction only affects the in-memory conversation history, not the on-disk memory files.** The daily logs are permanent, append-only records.

### MEMORY.md and Daily Log Curation

- **`MEMORY.md`**: Managed by user commands ("remember X", "forget Y") and agent writes. No automatic compaction — grows until manually rewritten.
- **`memory/YYYY-MM-DD.md`**: Append-only. Never revised or compacted. Pre-compaction flush appends to it; the file only grows.

---

## Part 2: TinyClaw Design (AgentHLE)

TinyClaw is the memory system for AgentHLE benchmark agents. These agents operate on remote Windows VMs via screenshots and mouse/keyboard — they have no local file access. The memory system must be explicit (tools for read/write) and simple (markdown files, no database). Tasks can span multiple sessions (roughly up to ~1k steps per session, ~10 sessions for a complex task).

### Design Principles

1. **Markdown as source of truth** — no database, no binary formats. Human-readable, git-friendly.
2. **Explicit tools** — the agent has no local file access, so every memory operation goes through a tool.
3. **Task-scoped memory** — memories are organized per task, persisting across sessions so the agent never starts from zero.
4. **Trajectory-driven nudges** — a callback periodically reads recent turn trajectories and summarizes them into the session log. Currently done by the computer-use agent; later replaceable by a planner LLM.
5. **Graceful upgrade path** — starts with keyword search, upgrades to hybrid when corpus grows.

### Storage

```
memory_data/
  ├── MEMORY.md                            # Global memory (cross-task knowledge)
  └── tasks/
      └── mota_24_easy/                    # Task-scoped memory (task_id from config)
          ├── TASK_MEMORY.md               # Compacted cross-session knowledge
          ├── session-001.md               # Session 1 log (append-only)
          ├── session-002.md               # Session 2 log (append-only)
          └── session-003.md               # Current session log (append-only)
```

**Three layers of memory:**

| Layer | Scope | Lifecycle | Content |
|-------|-------|-----------|---------|
| `MEMORY.md` | Global | Persistent | Knowledge useful across all tasks |
| `TASK_MEMORY.md` | Per-task | Compacted after each session | Curated task-specific learnings |
| `session-NNN.md` | Per-session | Append-only | Detailed log of one run |

- `task_id` derived from the task config tag/name (e.g., `mota_24_easy`)
- `TASK_MEMORY.md` is auto-injected into the agent's initial context at session start — no search needed
- Session files are append-only during a run (like OpenClaw's daily logs) and searchable via `memory_search`

### Tools

Three tools, all registered via `@register_tool` and wired into `ComputerAgent`:

| Tool | Parameters | Purpose |
|------|-----------|---------|
| `memory_search` | `keywords: list[str]`, `max_results?: int`, `task_id?: str` | Search across memory files by keyword (later: hybrid). When task_id set, searches task-scoped files first |
| `memory_get` | `file_path: str`, `start_line?: int`, `end_line?: int` | Read a specific file or line range. Path restricted to `memory_data/` tree |
| `memory_write` | `content: str`, `target?: "session" \| "memory" \| "task_memory"` | Append to current session log (default), overwrite global MEMORY.md, or overwrite TASK_MEMORY.md |

### MemoryFlushCallback (during session)

A callback that runs alongside the agent. During a session, only `session-NNN.md` is written to. `TASK_MEMORY.md` is read-only during a session, compacted only at session end.

**Trajectory-driven nudge** (every N turns, default 20):
1. Reads the last N turns' trajectory data (reasoning summaries from `agent_response.json`)
2. Summarizes observations into the session log via `memory_write`
3. Adaptive interval: can increase for long runs to avoid nudge fatigue

Currently the computer-use agent performs the summarization (it sees the nudge as a system message with recent trajectory context). Later this can be replaced by a dedicated planner LLM.

### Post-Session Compaction (after session)

After the session ends, a separate LLM call compacts session learnings into `TASK_MEMORY.md`:

```
Input:  1. Finalized session-NNN.md (containing all nudge-appended observations)
        2. Current TASK_MEMORY.md
Prompt: "Merge these session learnings into TASK_MEMORY.md.
         Remove contradictions, deduplicate, keep only actionable
         knowledge."
Model:  gpt-5-mini with reasoning (configurable via MEMORY_COMPACTION_MODEL)
Output: Rewritten TASK_MEMORY.md
```

Why a separate LLM: the computer-use agent is optimized for screen interaction, not text reasoning. A reasoning model (same one used for nudge summarization when upgraded to planner) produces better compaction. If the call fails, the session log and raw trajectories are still preserved.

### Cross-Session Flow (mota_24_easy example)

```
Session 1: Agent explores floor 3, gets stuck at yellow door
  → Nudge every 20 turns: trajectory summaries → session-001.md
  → Run ends → LLM compacts session-001.md into TASK_MEMORY.md:
    "Floor 3 yellow door requires yellow key. Key location unknown."

Session 2: Starts with TASK_MEMORY.md injected into context
  → Agent already knows about yellow door, explores floor 2
  → Finds key but dies to monster (200 HP)
  → Run ends → LLM compacts session-002.md into TASK_MEMORY.md:
    "Floor 3 yellow door requires yellow key.
     Yellow key is on floor 2, behind hidden wall.
     Floor 2 monster has 200 HP — need ATK > 50 before attempting."

Session 3: Starts knowing both facts
  → Farms ATK first → gets key → opens door → progresses
```

### Within-Session Memory Flow

```
During session:
  CUA trajectories → automatic raw logging (every turn)
  TASK_MEMORY.md   → read-only (injected at start, searchable)
  session-NNN.md   → append-only (nudge reads trajectories, writes here)

After session:
  session-NNN.md   → finalized (no more appends)
  TASK_MEMORY.md   → rewritten by LLM compaction (session-NNN.md → TASK_MEMORY.md)
```

Session logs are strictly append-only during the run (like OpenClaw's daily logs). Compaction only happens after the session ends. TinyClaw adds LLM-driven compaction of `TASK_MEMORY.md` at session end — the automation that OpenClaw leaves to the human.

### Relationship with CUA Trajectories

The CUA framework automatically logs raw trajectories via `TrajectorySaverCallback` — a callback built into `ComputerAgent` that hooks into 10 lifecycle events. This is completely separate from TinyClaw and requires no setup beyond passing `trajectory_dir` to `ComputerAgent()`.

**What CUA trajectories capture (per turn):**

```
turn_NNN/
  0000_api_start.json          # Full API request (messages, tools, model)
  0001_api_result.json         # Raw API response
  0002_agent_response.json     # Round-trip: messages + response + usage + reasoning summary
  0003_screenshot_after.png    # Screenshot after action
  0004_computer_call_result.json  # Tool result fed back to model
  0005_screenshot_action.png   # (optional) Screenshot with crosshair annotation
```

Plus `metadata.json` per trajectory with status, total usage, and trajectory ID.

**How the two systems complement each other:**

```
CUA Trajectories (automatic, raw)       TinyClaw Memory (curated)
─────────────────────────────────────    ────────────────────────────────────────
Every API call, action, screenshot       Distilled observations per N turns
Reasoning summaries per turn             session-NNN.md (append-only)
Token usage per turn                     TASK_MEMORY.md (compacted learnings)
Written by CUA SDK callbacks             Written by nudge (reads trajectories)
Raw data — grows with every turn         Distilled knowledge — compacted
Input to within-session nudges           Input to post-session compaction
```

TinyClaw does NOT duplicate trajectory data. The nudge callback reads recent trajectory reasoning summaries and distills them into the session log. The session log is then the sole input (alongside existing TASK_MEMORY.md) for post-session compaction.

### Search Modes

**Phase 1 (current): Keyword**
- Case-insensitive substring matching across all `.md` files
- Results scored by keyword hit count
- Returns: file path, line number, content, score

**Phase 2 (planned): Hybrid**
- Adds semantic search via embeddings (OpenAI text-embedding-3-small default)
- Markdown files chunked: 400 tokens/chunk, 80 token overlap
- Hybrid merge: `0.7 * vector_score + 0.3 * keyword_score`
- Embedding cache by content hash (no re-embedding unchanged chunks)
- Graceful fallback to keyword-only if embedding API unavailable

### Scaling for Long Runs (6h / 10k steps)

| Challenge | Solution |
|-----------|----------|
| Session log grows large | Append-only is fine; search handles retrieval. Compaction distills into TASK_MEMORY.md at session end |
| Search quality degrades | Hybrid search (US-MEM-006) becomes essential at scale |
| Too many nudges | Adaptive flush interval (20 → 50+ as run progresses) |
| Early observations contradict later ones | LLM compaction removes contradictions at session end |
| TASK_MEMORY.md grows too large | Size-capped compaction with aggressive summarization when exceeding threshold |
| Context window fills mid-session | Step nudges persist observations to session log before they're lost to context compaction |

### Memory Recall: How the Agent Decides to Search

A key design question: how does the agent know *when* to call `memory_search`? OpenClaw and TinyClaw take different approaches, and TinyClaw has clear room to improve.

#### OpenClaw's Approach (Reference)

OpenClaw uses three reinforcing layers:

1. **Dedicated system prompt section** (`## Memory Recall`): Injected only when memory tools are available. States a categorical rule:
   > "Before answering anything about prior work, decisions, dates, people, preferences, or todos: run memory_search"

2. **Tool description**: Reinforces with "**Mandatory recall step**" framing and the same trigger category list.

3. **Two-step workflow**: Search first (`memory_search`), then targeted read (`memory_get`) to "pull only the needed lines and keep context small."

4. **Failure guidance**: "If low confidence after search, say you checked."

#### TinyClaw's Current Approach

A single vague sentence in the general instructions:
> "You have a memory_search tool — use it to recall past observations, strategies, or mistakes before making decisions."

No specific trigger categories, no "mandatory" framing, no failure guidance, no dedicated prompt section.

#### Identified Improvements for TinyClaw

1. **Task-agnostic trigger categories**: Replace "before making decisions" with concrete but general categories, following OpenClaw's pattern (prior work, decisions, dates, strategies, mistakes). The categories should apply to any CUA task, not just game tasks. Exact wording to be determined during implementation.

2. **"Mandatory recall" framing**: Stronger framing ("mandatory recall step") increases actual tool invocation rates vs. a soft suggestion.

3. **Dedicated `## Memory Recall` section**: A separate heading in the system prompt makes it more prominent to the model vs. being a clause in a run-on paragraph.

4. **Failure/low-confidence guidance**: Tell the agent what to do when search returns nothing relevant ("proceed without it" or "say you checked").

5. **Session-start nudge**: Programmatically call `memory_search` with task-relevant keywords before the first real step, so the agent begins with prior context loaded rather than hoping it decides to search.

6. **Two-step search→get workflow**: Once `memory_get` is wired in (US-MEM-003), instruct the agent to use search for discovery and get for targeted reads, keeping context small.

### What TinyClaw Intentionally Omits

| OpenClaw Feature | Why Omitted |
|-----------------|-------------|
| SQLite storage | Markdown is sufficient, human-readable, git-friendly |
| FTS5 / BM25 | Substring matching is adequate initially; hybrid search planned |
| Multiple embedding providers | Single provider (OpenAI) + keyword fallback is enough |
| MMR diversity re-ranking | Small result sets don't need diversity optimization |
| Temporal decay | Task-scoped memory + compaction handles recency better for our use case |
| File watcher (Chokidar) | Memory files only change via tools during a run; no external modifications |
| QMD alternative backend | One backend is sufficient |
| LanceDB extension | Overkill for markdown-based system |
| Auto-capture via regex | Explicit `memory_write` tool is clearer for benchmark agents |

### Implementation Status

| Component | Story | Status |
|-----------|-------|--------|
| MemoryStore | US-MEM-001 | Done |
| memory_search (keyword) | US-MEM-002 | Done |
| memory_get | US-MEM-003 | Planned |
| memory_write | US-MEM-W01 | Planned |
| MemoryFlushCallback | US-MEM-004 | Planned |
| Task-scoped memory + compaction | US-MEM-TSK | Planned |
| Hybrid search + chunking | US-MEM-006 | Future |

---

## Comparison Summary

```
                    OpenClaw                    TinyClaw
Storage:            SQLite + FTS5 + vec         Markdown files
Memory scope:       Per-agent                   Per-task (cross-session)
Search:             Hybrid (vector+keyword)     Keyword → Hybrid (planned)
Chunking:           400 tokens, 80 overlap      Same (planned)
Embeddings:         6 providers + auto-detect   OpenAI + keyword fallback
Tools:              memory_search, memory_get   + memory_write (agent has no FS)
Write mechanism:    File tools + hooks          memory_write tool + callback
Session logs:       Append-only daily logs      Append-only session logs
Compaction:         Pre-compaction flush to      LLM post-hoc at session end
                    daily log (agent-driven,     (merges session summary into
                    system-triggered at           TASK_MEMORY.md; removes
                    context limit)                contradictions)
MEMORY.md:          Human-curated               Agent + LLM-curated (TASK_MEMORY.md)
Sync:               File watcher + debounce     Not needed (tool-driven writes)
Persistence:        SQLite tables               Flat markdown files
Target use case:    Long-running assistant       Long benchmark runs (up to 10k steps)
```
