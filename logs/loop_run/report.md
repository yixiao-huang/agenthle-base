# Loop Run Report (Append-Only)

---

## 2026-03-21 17:04 — Loop Run: 50 steps, 2 attempts

**Result**: FAILED 0.0 / 3 on both attempts

### Attempt 1 (full setup + agent + eval)
- Solver started 17:00:55, eval finished 17:03:32
- Model: `anthropic/claude-sonnet-4-20250514`
- Agent ran 50 steps, wrote memory claiming "TASK COMPLETED SUCCESSFULLY"
- Agent saved milestone screenshots for floors 2 and 3 (floor 1 missing from output)
- VLM judge (gpt-5.2) returned **NO** for both 2.png and 3.png
- Only 2 milestones evaluated out of 3 references → floor 1 screenshot not saved by agent
- Eval file: `GAME_MOTA_24_EZ_evaluation_20260321_170332.json`

### Attempt 2 (task-only + evaluate-only)
- `--task-only` correctly skipped setup (game reused), agent ran again
- `--evaluate-only` correctly skipped setup+agent, ran eval only
- Same result: NO for 2.png and 3.png, 0.0/3
- Eval file: `GAME_MOTA_24_EZ_evaluation_20260321_170417.json`

### Observations & Open Questions
1. **Agent hallucinated success**: Wrote "TASK COMPLETED SUCCESSFULLY" to memory but screenshots don't match references. This is a known failure mode — agent believes it completed the task without visual verification.
2. **Floor 1 screenshot missing**: Agent saved 2.png and 3.png but not 1.png. Task description says to save milestone for each new floor. Agent may have skipped floor 1 (starting floor) or misunderstood the instruction.
3. **VLM judge rejected both screenshots**: Need to visually inspect the agent's 2.png/3.png vs references to determine if:
   - (a) Game didn't load / was in wrong state
   - (b) Agent took screenshots at wrong moments (e.g., transition screens, menus)
   - (c) Agent never actually reached floors 2/3
   - (d) Screenshots are correct but VLM judge is too strict
4. **Loop script worked correctly**: Setup ran on attempt 1, was skipped on attempt 2. task-only and evaluate-only flags behaved as expected.

### TODO for next investigation
- [x] Inspect agent trajectory turn-by-turn to see what the game screen looked like
- [ ] Compare agent's 2.png/3.png vs reference 2.png/3.png visually (references are on remote VM)
- [x] Check if game actually loaded (first screenshot in trajectory)
- [ ] Check if the game was still open for attempt 2 or had crashed/closed

---

## 2026-03-21 17:30 — Trajectory Analysis: Attempt 1

**Trajectory**: `2026-03-21_claudesonnet4_170112_ca9c` (12 turns, turn_000–turn_011)

### Root Cause: Agent Miscounted Floors (Off-by-One)

The game has a **Prologue area** ("序 章") before Floor 1. The agent treated the Prologue as Floor 1, causing all floor numbers to be off by one:

| Agent Believes | Actual Floor | Evidence |
|---|---|---|
| Floor 1 (starting) | Prologue ("序 章") | Turn 0 screenshot: bottom-left panel shows "序 章" |
| Floor 2 → saved `2.png` | Floor 1 ("第 1 层") | Turn 6: agent called save_milestone claiming "Floor 2", but game shows same prologue map — the agent didn't even change floors here |
| Floor 3 → saved `3.png` | Floor 1 ("第 1 层") | Turn 10 screenshot: bottom-left shows "第 1 层" (Floor 1). Agent explicitly noted this but rationalized: "Floor indicator shows '第 1 层' but map layout confirms this is Floor 2" |

### Detailed Turn-by-Turn

- **Turn 0–5**: Agent on Prologue floor, moved up toward stairs. Game shows "序 章" (Prologue).
- **Turn 6**: Agent pressed Up then Right. Called `save_milestone_screenshot` for "Floor 2" — but screenshot shows agent is still on the **same prologue map**. The agent may have hit a dialogue/fairy NPC instead of ascending. The milestone was saved showing the wrong floor.
- **Turn 7–10**: Agent navigated a different-looking map. Floor indicator now shows "第 1 层" (Floor 1). Agent rationalized the discrepancy instead of correcting.
- **Turn 11**: Agent called `save_milestone_screenshot` for "Floor 3", then `memory_write` claiming task complete. But the agent was actually on Floor 1 at best.

### Why VLM Judge Said NO
- Agent's `2.png` likely shows the prologue area, not Floor 2 reference
- Agent's `3.png` likely shows Floor 1, not Floor 3 reference
- The screenshots are genuinely wrong — VLM judge is correct to reject

### Key Failure Modes Identified

1. **Floor counting error**: Agent doesn't read the in-game floor indicator text (Chinese: "序 章", "第 N 层"). Instead it infers floor from map layout changes, leading to off-by-one.
2. **Rationalization over observation**: When the floor indicator contradicted the agent's belief ("第 1 层" but agent thinks Floor 2), the agent dismissed the game UI rather than updating its model.
3. **No Floor 1 milestone**: Agent never saved `1.png` because it thought the prologue WAS floor 1. The task has 3 reference files (1.png, 2.png, 3.png) but agent only saved 2.png and 3.png.
4. **Insufficient game progress**: In 12 turns (~50 steps), the agent only got from Prologue to Floor 1. It needs to reach Floor 3, which requires significantly more steps or better pathfinding.

### Recommendations for Future Runs
- The task description or AGENTS.md could hint that the game starts in a Prologue area before Floor 1
- Agent should be instructed to read the floor indicator text in the bottom-left panel to confirm actual floor number
- 50 steps may not be enough to reach Floor 3 — the agent needs to navigate through monsters, keys, and locked doors on each floor
- Consider increasing max_steps or improving the agent's pathfinding strategy via TASK_MEMORY.md seeding

---

## 2026-03-21 17:35 — Analysis: Fresh 200-step loop (attempts 1-2)

**Result**: FAIL 0.0 / 3 on both attempts
**Model**: `anthropic/claude-sonnet-4-20250514`
**Config**: 200 steps, 10 attempts, fresh memory (all prior sessions cleared)

### Attempt 1: `2026-03-21_claudesonnet4_172109_4639` (47 turns)

**Eval**: `GAME_MOTA_24_EZ_evaluation_20260321_172808.json` — 0.0/3, all NO

#### What Happened
Agent started from Prologue, navigated for 47 turns. Saved all 3 milestones but on wrong floors. Same off-by-one error as prior runs.

#### Floor Progression
| Turn | Milestone | Agent Claimed | Actual (from UI) |
|------|-----------|--------------|-------------------|
| 1 | `1.png` | "Reached floor 1" | **Prologue ("序 章")** — dialogue with fairy NPC visible |
| 37 | `2.png` | "Reached floor 2" | **Prologue ("序 章")** — still same prologue map! |
| 45 | (no save) | — | **Floor 1 ("第 1 层")** — first real floor transition |
| 46 | `3.png` | "Reached floor 3" | **Floor 1 ("第 1 层")** at best — no screenshot available |

#### Failure Mode
**Floor misidentification (off-by-one) + Insufficient progress**
- Agent treated Prologue as Floor 1, causing all labels to be off by one
- Agent spent 37 turns on the Prologue before reaching Floor 1
- Never reached Floor 2 or Floor 3 in 47 turns / 200 steps
- All 3 milestone screenshots show the wrong floors

### Attempt 2: `2026-03-21_claudesonnet4_172822_9edf` (2 turns)

**Eval**: `GAME_MOTA_24_EZ_evaluation_20260321_173004.json` — 0.0/3, all NO

#### What Happened
Agent read session logs from attempt 1, saw "reached Floor 3", and **immediately believed it was already on Floor 3** without verifying the floor indicator. Saved `3.png` and declared DONE in 2 turns.

#### Failure Mode
**Hallucinated completion from stale memory**
- Screenshot clearly shows "第 1 层" (Floor 1) — game continued from where attempt 1 left off
- Agent trusted its own prior session log ("Successfully reached Floor 3") over the actual game UI
- This is a compounding error: attempt 1's wrong memory poisons attempt 2's judgment
- New failure pattern: **cross-run memory poisoning** — bad conclusions from run N propagate to run N+1

### New Failure Pattern Identified

5. **Cross-run memory poisoning**: Agent writes incorrect conclusions to session memory (e.g., "reached Floor 3" when actually on Floor 1). Next run reads this memory and trusts it over visual evidence, leading to instant false completion. This is worse than a single-run hallucination because it persists across attempts.

### Recommendations
1. **CRITICAL: Seed TASK_MEMORY.md** with floor indicator guidance before running. Without it, the off-by-one error is 100% reproducible.
2. **Clear output directory between attempts** — old milestone screenshots from failed runs shouldn't persist, as they can mislead the evaluator or agent.
3. **Consider clearing session memory between attempts** — or at minimum, add a "verification required" note so the agent re-checks floor indicators instead of trusting prior session logs.
4. **200 steps is still not enough** — agent only reached Floor 1 in 47 turns. Floors 2 and 3 each require navigating monsters, keys, and doors. May need 500+ steps.

---

## 2026-03-21 17:40 — Analysis: Attempts 3-7 (memory poisoning cascade)

**Result**: FAIL 0.0 / 3 on all attempts (6 total evals, all 0.0/3)
**Model**: `anthropic/claude-sonnet-4-20250514`

### Summary

| Attempt | Trajectory | Turns | Failure Mode |
|---------|-----------|-------|-------------|
| 1 | `172109_4639` | 47 | Off-by-one floor counting, reached Floor 1 only |
| 2 | `172822_9edf` | 2 | Memory poisoning — trusted false "Floor 3" claim |
| 3 | `173012_64a7` | 2 | Memory poisoning |
| 4 | `173139_10b3` | 2 | Memory poisoning |
| 5 | `173305_b3d0` | 2 | Memory poisoning |
| 6 | `173423_a19e` | 2 | Memory poisoning |
| 7 | `173547_d257` | 10 | Memory poisoning (slightly longer — re-saved milestones) |

### What Happened
Attempt 1 played the game for 47 turns but miscounted floors (off-by-one). It wrote false success claims to session memory and TASK_MEMORY.md. All subsequent attempts (2-7) read this poisoned memory, believed the task was already done, and immediately re-saved milestones without navigating — typically completing in 2 turns.

### Confirmed Failure Patterns
1. **Off-by-one** (attempt 1): Still 100% reproducible without TASK_MEMORY.md guidance
2. **Memory poisoning** (attempts 2-7): Devastating — makes all retry attempts useless. Agent reads "TASK COMPLETED" from prior session, trusts it over visual evidence, declares done in 2 turns.
3. **The loop is fundamentally broken without memory clearing**: Retrying with task-only does NOT clear memory. Each failed attempt adds more false-success entries, making the problem worse.

### Critical Fix Required Before Next Loop
The loop script must **clear memory between attempts**, or seeded TASK_MEMORY.md must include a verification step that forces the agent to re-check floor indicators regardless of what prior sessions claim. Without this, attempts 2+ are wasted.

---
