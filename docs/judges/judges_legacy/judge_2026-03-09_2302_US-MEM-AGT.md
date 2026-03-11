## AgentHLE Audit Report

**Raw audit log**: `logs/judge_2026-03-09_2302_US-MEM-AGT.log`
**Report**: `docs/judges/judge_2026-03-09_2302_US-MEM-AGT.md`

### Overall Assessment

US-MEM-AGT is substantially complete — all memory tools are wired in, scaffolding is removed, TASK_MEMORY.md is correctly injected into instructions, and the agent autonomously uses memory tools during real VM runs. The main gap is task_id derivation (env var instead of auto-derived from task config).

### Rubric Scorecard

| Axis | Score (/100) | Key Gap | Top Action to Improve |
|------|-------------|---------|----------------------|
| Implementation Progress | 85 | task_id not auto-derived (AC #3 partial) | Auto-derive task_id from task directory name in perform_task() |
| Code Quality | 85 | Post-run consolidation is naive append | Replace with LLM compaction (US-MEM-CMP) |
| Design Soundness | 80 | MEMORY.md injected into instructions will grow unboundedly | Stop injecting global MEMORY.md; use memory_search for global access |
| Real-World Behavior | 78 | Agent never called memory_get; search-then-get workflow not exercised | Improve recall prompting (US-MEM-RCL) |
| **Overall** | **82** | | |

### Golden Reference Audit

| Story | Reference | Alignment | Issue |
|-------|-----------|-----------|-------|
| US-MEM-AGT | openclaw/src/agents/system-prompt.ts | INTENTIONAL DEVIATION | TinyClaw injects TASK_MEMORY.md into instructions= (correct for CUA sliding window); OpenClaw uses on-demand search. Well-documented design decision. |
| US-MEM-AGT | docs/cua-context-management.md | ALIGNED | instructions= is the only non-truncated content; implementation correctly uses it for cross-session knowledge. |
| US-MEM-AGT | docs/openclaw-context-flow.md | PARTIAL | OpenClaw has categorical triggers in ## Memory Recall section; TinyClaw has flat instructions. Deferred to US-MEM-RCL. |

### PRD Story Audit

| Story | Claimed | Actual | Issue | Fix |
|-------|---------|--------|-------|-----|
| US-MEM-AGT | passes: false | PASS (with findings) | AC #3 partial — task_id from env var, not auto-derived | Consider auto-deriving from task directory name |

### Acceptance Criteria Audit

| Story | # | Criterion | Verdict | Issue |
|-------|---|-----------|---------|-------|
| US-MEM-AGT | 1 | Remove step counter logging | OK | Gone from production code |
| US-MEM-AGT | 2 | Remove self-verification code | OK | Replaced with session consolidation |
| US-MEM-AGT | 3 | MemoryStore initialized with task_id from task config | WEAK | Uses MEMORY_TASK_ID env var, not derived from task config/directory. Works but requires external coordination. |
| US-MEM-AGT | 4 | init_session() called at start | OK | Line 82, gated on task_id being set |
| US-MEM-AGT | 5 | TASK_MEMORY.md injected into instructions | OK | Lines 86-101, both global and task memory injected |
| US-MEM-AGT | 6 | All three tools wired in | OK | Line 106: memory_search, memory_get, memory_write all in tools= |
| US-MEM-AGT | 7 | Instructions describe all three tools | OK | Lines 112-134: detailed usage guidance |
| US-MEM-AGT | 8 | Smoke test passes | OK | 49/50 steps, no crash |
| US-MEM-AGT | 9 | Level 2: memory tools invoked | OK | 5 calls (1 search, 4 writes) |
| US-MEM-AGT | 10 | Level 2: content task-relevant | OK | Floor navigation, game observations, not step counters |
| US-MEM-AGT | 11 | Lint passes | OK | Clean for memory/ and agenthle_agent.py |
| US-MEM-AGT | — | — | MISSING | Need: "Level 2: memory_get invoked at least once during a real run (search-then-get workflow exercised)" |

### Code Quality Issues

| File | Line(s) | Severity | Issue | Fix |
|------|---------|----------|-------|-----|
| agenthle_agent.py | 74 | MEDIUM | task_id from MEMORY_TASK_ID env var, not auto-derived from task config | Derive from task directory name or task_description parsing |
| agenthle_agent.py | 87-93 | LOW | Global MEMORY.md injected into instructions — will grow unboundedly as more tasks run | Consider removing global memory injection; use memory_search for global access |
| agenthle_agent.py | 195-231 | LOW | Post-run consolidation appends raw session log to TASK_MEMORY.md and MEMORY.md verbatim | Replace with LLM compaction (US-MEM-CMP) — already planned |
| agenthle_agent.py | 81 | INFO | init_session() only called when task_id is set; no-session mode is silent | Add a log warning when task_id is not set |

### Design Concerns

1. **MEMORY.md growth** (Design Soundness): Global MEMORY.md is both injected into instructions AND appended to after every run. As the agent runs many different tasks, this file will grow and consume context tokens in instructions=. OpenClaw intentionally does NOT inject global memory into the system prompt. *Recommendation:* Stop injecting MEMORY.md; keep TASK_MEMORY.md injection only (it's task-scoped and bounded).

2. **Naive consolidation before US-MEM-CMP** (Design Soundness): Post-run consolidation appends raw session observations to TASK_MEMORY.md. After 5 sessions, TASK_MEMORY.md will contain 5 raw observation blocks plus whatever compacted summary exists. This redundancy wastes context tokens. *Recommendation:* Acceptable as interim; US-MEM-CMP will fix this.

3. **memory_get never exercised** (Real-World Behavior): The agent's instructions describe a search-then-get workflow, but in 49 steps the agent never called memory_get. Search results may be sufficient for current memory sizes, but as memory grows, the agent will need targeted reads. *Recommendation:* Address in US-MEM-RCL with stronger prompting.

### Real VM Test Results

- **Run config**: 50 max-steps, mota_24_easy, 2026-03-09
- **Trajectory**: `2026-03-09_computerusepre_225148_d4b0` — 20 turns, 49 steps
- **Memory tool invocations**: 5 total (1 memory_search, 4 memory_write, 0 memory_get)
- **Search query quality**: "Magic Tower Ruffle" — task-relevant, good keywords
- **Memory content quality**: Task-relevant observations about floor navigation, key presses, movement — not step counters. Ratio: ~100% task-relevant.
- **Tool output retention window**: Instructions (with injected prior knowledge) survive at all 20 turns. Function call outputs (search results) visible in the turn they're returned; not verified in later turns.
- **Post-run consolidation**: Session observations appended to both TASK_MEMORY.md and MEMORY.md.

### Prioritized Suggestions

1. **Auto-derive task_id** — Parse task directory name from task_description or accept it as a parameter in perform_task(). *Impact: medium. Effort: low. Rubric: Implementation Progress.*
2. **Stop injecting MEMORY.md into instructions** — Use memory_search for global access; keep only TASK_MEMORY.md in instructions. *Impact: medium (prevents context bloat). Effort: low. Rubric: Design Soundness.*
3. **Add warning when task_id not set** — Log a warning so operators know memory is in degraded mode. *Impact: low. Effort: trivial. Rubric: Code Quality.*
4. **Add memory_get criterion** — Add "Level 2: memory_get invoked at least once" to acceptance criteria. *Impact: low (prompting issue). Effort: low. Rubric: Real-World Behavior.*

### Blockers for Next Story

- Current next story: US-MEM-004 - MemoryFlushCallback
- Ready to start: YES (depends on US-MEM-AGT which passes)
- Blockers: None — US-MEM-AGT is functionally complete. The task_id derivation issue is cosmetic for current usage.

### Verdict

**PASS** — All core acceptance criteria met. Memory tools are wired in, scaffolding is removed, TASK_MEMORY.md is correctly injected into the non-truncated instructions= parameter, and the agent autonomously searches and writes memory during real VM runs. The main gaps (task_id derivation, MEMORY.md growth, naive consolidation) are either low-impact or already addressed by downstream stories (US-MEM-CMP, US-MEM-RCL).
