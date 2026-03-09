# Testing & Feedback Loops: Designing Meaningful Verification for TinyClaw

## Problem

Current acceptance criteria follow a "doesn't crash" pattern:
- **Unit tests**: Verify API contracts (correct return types, edge cases handled)
- **Integration test**: `run_magic_tower.sh` confirms tools are registered and no import errors

This tells us the code works mechanically but says nothing about whether the memory system actually helps the agent. An agent with a broken memory system would pass all current tests as long as it doesn't throw exceptions.

## Three Levels of Testing

### Level 1: Mechanical (current)
**Question**: Does the code run without errors?

- Unit tests with `tmp_path` and seeded data
- `run_magic_tower.sh --max-steps 5` smoke test
- Tool appears in trajectory JSON

**What it catches**: Import errors, type mismatches, missing files, API contract violations.

**What it misses**: Whether the agent uses the tools, whether memory content is meaningful, whether cross-session learning actually happens.

### Level 2: Behavioral
**Question**: Does the agent interact with memory in a meaningful way?

After a real run (`run_magic_tower.sh` — step count at the testing agent's discretion based on what's needed to verify the feature), verify:

1. **Tool invocation** — Did the agent call memory tools?
   - Parse trajectory JSONs (`turn_NNN/NNNN_agent_response.json`) for `memory_search`, `memory_get`, `memory_write` function calls
   - Check: at least 1 memory tool invocation per N steps (e.g., 1 per 50 steps)
   - If the agent never calls memory tools, the instructions or tool descriptions need work

2. **Memory content quality** — Is what was written useful?
   - Read `session-NNN.md` and `TASK_MEMORY.md` after the run
   - Check: entries contain task-specific observations (not just "Step 42: tokens=15000")
   - Check: entries reference game state (floor numbers, items, enemies, strategies)
   - A VLM or text LLM can judge: "Does this memory entry contain actionable information for a future session?" (YES/NO)

3. **Search relevance** — Does memory_search return useful results?
   - Seed memory with known content before the run
   - After the run, check trajectory logs: when the agent searched, were the results relevant to what it was doing?
   - Check: search queries in trajectory logs are task-relevant (not random or empty)

4. **Nudge effectiveness** — Does the periodic nudge produce observations?
   - After a run with nudge enabled (50+ steps), check session log
   - Check: nudge-appended entries exist at expected intervals (~every 20 turns)
   - Check: entries are distinct (not copy-pasted repetitions)

### Level 3: Outcome
**Question**: Does memory improve task performance across sessions?

This is the ultimate test of usefulness. Requires multiple runs:

1. **A/B comparison** (same task, with vs without memory):
   - Run A: Agent with empty memory, 200 steps on mota_24_easy → record score, floors reached
   - Run B: Agent with pre-seeded TASK_MEMORY.md from a previous run → record score, floors reached
   - Compare: Does Run B reach further? Make fewer repeated mistakes? Use fewer steps to reach the same point?

2. **Cross-session progression** (sequential runs):
   - Session 1: 200 steps, empty start → observe what gets written to session-001.md → compact to TASK_MEMORY.md
   - Session 2: 200 steps, TASK_MEMORY.md injected → check: does agent avoid Session 1's dead ends?
   - Session 3: 200 steps → check: cumulative knowledge helps further
   - Metric: floor reached per session should be non-decreasing (ideally increasing)

3. **Contradiction resolution** (compaction quality):
   - Session 1 writes "Yellow key is on floor 2"
   - Session 2 discovers "Yellow key is actually on floor 1"
   - After compaction: TASK_MEMORY.md should contain corrected info, not both contradicting statements
   - A text LLM judges the compacted output for contradictions

## Automated Evaluation: `/judge`

The `/judge` skill spawns a subagent that operationalizes this framework. It reads the PRD story, compares against golden references, audits acceptance criteria, runs a real VM test, and analyzes behavioral evidence from trajectory logs. Run `/judge US-MEM-003` (or just `/judge` for a full project audit) after implementing and before `/ship`.

## Verification Checklist (Per Story)

Every memory-related story should include verification at **all applicable levels**:

```
### Level 1 (Mechanical) — automated
- [ ] Unit tests pass (uv run pytest)
- [ ] Lint passes (uv run ruff check .)
- [ ] Smoke test: run_magic_tower.sh --max-steps 5 doesn't crash

### Level 2 (Behavioral) — after real run
- [ ] Run: run_magic_tower.sh N (step count at your discretion)
- [ ] Check trajectory JSONs: agent invoked the new tool at least once
- [ ] Check memory files: content is task-relevant (not boilerplate)
- [ ] Check agent reasoning: tool results influenced subsequent actions
  (read agent_response.json reasoning summaries after tool calls)

### Level 3 (Outcome) — milestone verification
- [ ] Only required for US-MEM-004, US-MEM-TSK, US-MEM-006
- [ ] Multi-session run shows knowledge transfer
- [ ] Performance metric (floors reached, score) is stable or improving
```

## How to Check Trajectories (Practical Guide)

After `run_magic_tower.sh`, trajectory files are at:
```
trycua/cua-bench/mota_24_easy/task_0_agent_logs/trajectories/<run_id>/
```

**Find memory tool calls:**
```bash
# Search for memory tool invocations in trajectory JSONs
grep -r '"memory_search"\|"memory_get"\|"memory_write"' \
  trycua/cua-bench/mota_24_easy/task_0_agent_logs/trajectories/
```

**Read reasoning after a memory call:**
Each `agent_response.json` contains `response.output[].summary[].text` with the agent's reasoning. After a memory tool call, the next turn's reasoning should reference the retrieved information.

**Count tool usage:**
```bash
# Count how many turns used memory tools
grep -rl '"memory_' trycua/cua-bench/mota_24_easy/task_0_agent_logs/trajectories/ | wc -l
```

## What This Means for Acceptance Criteria

Current pattern (insufficient):
```
"run_magic_tower.sh shows memory_get in the agent's available tools
 and agent runs without tool registration errors"
```

Better pattern:
```
"After run_magic_tower.sh (step count at discretion):
 1. Trajectory logs show at least 1 memory_get invocation
 2. Memory files contain task-specific observations (not just step counters)
 3. Agent reasoning after memory retrieval references the retrieved content"
```

Best pattern (for cross-session stories):
```
"After two sequential runs on mota_24_easy:
 1. Session 2's TASK_MEMORY.md contains compacted learnings from session 1
 2. Agent in session 2 does not repeat session 1's identified dead ends
 3. Floor reached in session 2 >= floor reached in session 1"
```

## Anti-Patterns to Avoid

1. **Logging as memory** — Writing "Step 42: tokens=15000" to the daily log is instrumentation, not memory. Real memory contains observations like "Floor 2 monster requires ATK > 50".

2. **Self-verification code in agent** — The current `agenthle_agent.py` has ~20 lines of post-run verification code (lines 154-171) that calls `memory_search` and logs results. This is test scaffolding embedded in production code. Verification should happen outside the agent, by reading trajectories and memory files after the run.

3. **Testing the tool, not the system** — Unit tests verify `MemorySearchTool.call()` returns formatted strings. But the real question is: when the LLM receives those strings, does it use them? This requires Level 2 behavioral checks.

4. **"Doesn't crash" as success** — A memory system that is ignored by the agent passes all Level 1 tests. The minimum bar should be Level 2: the agent actually uses it.
