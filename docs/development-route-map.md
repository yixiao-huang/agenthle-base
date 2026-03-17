# AgentHLE — OpenClaw Reproduction Development Map

> Auto-generated 2026-03-16. 16/28 stories done (57%).

```
═══ PHASE 1: Independent Modules ════════════════════════════════════

  ✓ US-OC-001 (P1)                ✓ US-OC-002 (P2)         ✓ US-OC-004 (P4)
  System Prompt Builder           Memory Store              Session Persistence
  [prompt.py]                     [memory.py]               [session.py]
       │                               │                         │
       │                               ▼                         ├──→ ✓ US-OC-004a (P4.1)
       │                         ✓ US-OC-003 (P3)               │    Session State Schema
       │                         Memory Tools                    │
       │                         [tools: search/get/write]       ├──→ ✓ US-OC-004b (P4.2)
       │                               │                         │    Transcript JSONL Fixes
       │                               │                         │
       │                               │                         ▼
       │                               │                   ✓ US-OC-012 (P8.1)
       │                               │                   Transcript Replay
       │                               │                         │
       │                               │                         ▼
       │                               │                   ✗ US-OC-022 (P8.2)
       │                               │                   Replay → Responses API
       │                               │
       ▼                               ▼
═══ PHASE 2: Context Management + Tool Wiring ═══════════════════════

  ✓ US-OC-005 (P5)              ✓ US-OC-007 (P7)
  Context Overflow Detection     Tool Registry & Logging
       │                               │
       ├──→ ✓ US-OC-005a (P5.1)        │
       │    Wire Memory Flush           │
       │         │                      │
       │         ▼                      │
       │    ✗ US-OC-025 (P5.2) ◄───────┘   ← CURRENT STORY
       │    Fix Memory Flush Timing         (highest priority failing)
       │                                │
       ▼                                │
  ✓ US-OC-006 (P6)                     │
  Compaction Pipeline                   │
       │                                │
       ├──→ ✓ US-OC-013 (P12)          │
       │    Budget-Aware Split          │
       │         │                      │
       │         ▼                      │
       │    ✓ US-OC-018 (P12.1)        │
       │    Structured Summarization    │
       │         │                      │
       │         ▼                      │
       │    ✗ US-OC-015 (P13.1)        │
       │    Summarization Timeout       │
       │         │                      │
       │         ▼                      │
       │    ✗ US-OC-016 (P14)          │
       │    Multi-Stage Summarization   │
       │                                │
       ▼                                ▼
═══ PHASE 3: Agent Loop Integration ═════════════════════════════════

              ✓ US-OC-008 (P8)
              Agent Loop Integration
              [openclaw_agent.py — wires everything together]
                     │
                     ├──────────────────────────────┐
                     │                              │
                     ▼                              ▼
         ✗ US-OC-014 (P13)              ✓ US-OC-021 (P18)
         Transcript Fidelity            CLI: --summary-model
         (on_llm_start capture)


═══ CROSS-CUTTING / ENHANCEMENTS ════════════════════════════════════

  ┌─────────────────────────┐   ┌─────────────────────────┐
  │  Thinking Mode          │   │  Audits & Reviews       │
  │                         │   │                         │
  │  ✗ US-OC-019 (P16)     │   │  ✗ US-OC-009 (P9)      │
  │  Config + CLI + Loop    │   │  CUA SDK Audit          │
  │         │               │   │                         │
  │         ▼               │   │  ✗ US-OC-010 (P10)     │
  │  ✗ US-OC-020 (P17)     │   │  Skipped Component      │
  │  Wire into Flush &      │   │  Review                 │
  │  Compaction             │   │                         │
  └─────────────────────────┘   └─────────────────────────┘

  ┌─────────────────────────┐   ┌─────────────────────────┐
  │  Architecture           │   │  Content                │
  │                         │   │                         │
  │  ✗ US-OC-017 (P15)     │   │  ✗ US-OC-024 (P15.1)   │
  │  Custom Loop Explore    │   │  AGENTS.md Enrichment   │
  │                         │   │                         │
  │  ✗ US-OC-023 (P23)     │   └─────────────────────────┘
  │  Opus 4.6 Tool Compat   │
  └─────────────────────────┘
```

## Component Map

```
openclaw_agent.py ──┬──→ prompt.py (System Prompt)
                    ├──→ memory.py (Memory Store)
                    ├──→ tools.py  (Memory Tools)
                    ├──→ session.py (Session Persistence + Replay)
                    ├──→ compaction.py (Context Compaction)
                    ├──→ callbacks/ (Overflow, Flush, Budget)
                    └──→ CUA SDK (ComputerAgent, Computer tool)
```

## Progress

| Status  | Count | Bar |
|---------|-------|-----|
| Done    | 16    | ████████████████░░░░░░░░░░░░ 57% |
| Failing | 12    | ████████████░░░░░░░░░░░░░░░░ 43% |

## Priority Queue (Next Up)

| Priority | ID | Title |
|----------|----|-------|
| 5.2 | US-OC-025 | Fix Memory Flush Timing: Pre-Turn Check |
| 8.2 | US-OC-022 | Replay Message Format: Unnest to Responses API |
| 9 | US-OC-009 | Post-Eval: CUA SDK Component Audit |
| 10 | US-OC-010 | Post-Eval: Skipped Component Review |
| 13 | US-OC-014 | Transcript Fidelity: Capture on_llm_start |
| 13.1 | US-OC-015 | Summarization Safety Timeout |
| 14 | US-OC-016 | Multi-Stage Summarization for Scale |
| 15 | US-OC-017 | Custom Loop Architecture Exploration |
| 15.1 | US-OC-024 | AGENTS.md Memory Guidance Enrichment |
| 16 | US-OC-019 | Thinking Mode: Config, CLI, Main Agent Loop |
| 17 | US-OC-020 | Thinking Mode: Wire into Memory Flush & Compaction |
| 23 | US-OC-023 | CUA Anthropic Loop: Opus 4.6 Tool Version Compat |

## Key Takeaways

- **Phase 1** (independent modules) is fully complete — prompt, memory, session all done
- **Phase 2** (context management) is mostly done, with US-OC-025 (memory flush timing) being the current blocker
- **Phase 3** (integration) core is done, but refinements remain (transcript fidelity, replay format)
- **Cross-cutting** work (thinking mode, audits, architecture exploration) is all still pending — lower priority polish/exploration items
