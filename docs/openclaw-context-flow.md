# OpenClaw Context Management — Reference Pointers

<!-- Last updated: 2026-03-10 -->

This file points to the authoritative references for OpenClaw's context management pipeline. The previous markdown extract was too simplified — it omitted verbatim prompts, constants, algorithms, and implementation details.

## Primary Reference

**`docs/openclaw-context-flow.html`** — Interactive visual covering the full OpenClaw context pipeline:
- System prompt construction (8 sections, bootstrap trimming constants)
- Compaction pipeline (overflow detection, safeguard flush, 3 summarization prompt variants with verbatim text)
- Tool loop (sequential execution, interrupt handling, schema format)
- Session persistence (.jsonl format, compaction entries, auto-prune)
- Sub-agent spawning (recursive runEmbeddedPiAgent)
- Message queue modes (collect, steer, followup, interrupt)

Open in a browser for interactive exploration. For AI agent consumption, read the relevant concept docs below.

## Component-Level References

**`openclaw/docs/concepts/`** — Official OpenClaw documentation, one file per component:

| File | Covers |
|------|--------|
| `memory.md` | Memory system: search, get, storage, indexing, embedding providers |
| `compaction.md` | Compaction pipeline: overflow detection, summarization prompts, safeguard flush |
| `system-prompt.md` | System prompt construction: 8 sections, bootstrap trimming, memory recall |
| `agent-loop.md` | Agent loop: tool execution, streaming, retry, interrupt handling |
| `context.md` | Context management: token budgets, truncation, reserved tokens |
| `session.md` | Session persistence: .jsonl format, replay, compaction entries |
| `multi-agent.md` | Sub-agents: sessions_spawn, depth limits, blocking execution |
| `agent.md` | Agent configuration: profiles, model selection, tool filtering |
| `agent-workspace.md` | Workspace: SOUL.md, AGENTS.md, USER.md, IDENTITY.md |
| `queue.md` | Message queue: modes (collect, steer, followup, interrupt) |

Read the specific concept doc(s) relevant to your current story rather than loading everything.

## CUA-Side Constraints

**`docs/cua-context-management.md`** — How the CUA framework manages context:
- Two-layer truncation (ImageRetentionCallback + OpenAI `truncation:auto`)
- What survives at turn 100 (only `instructions=` is never truncated)
- Callback chain and item lifecycle
- Token costs per item type

This is essential context for any adaptation that maps OpenClaw concepts to CUA.

## Legacy Reference

**`docs/memory-system.md`** — TinyClaw memory system design (Phase 1) + OpenClaw reproduction framing (Phase 2). Covers the agent-planner separation, storage layout, tool design, and cross-session flow.
