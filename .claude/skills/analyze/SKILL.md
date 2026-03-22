---
name: analyze
description: "Analyze the most recent agent run trajectory — inspect screenshots, agent reasoning, tool calls, and evaluation results to diagnose why the agent failed or succeeded. Appends findings to logs/loop_run/report.md."
user-invocable: true
---

# Analyze Run

**Modes:** `/analyze` (most recent run) | `/analyze <trajectory-name>` (specific trajectory)

Target: $ARGUMENTS (if empty, auto-select the most recent trajectory).

Analyze an agent run trajectory to understand what the agent did, why it failed or succeeded, and what should change for future runs.

---

## Context

### Directory Layout

- **Trajectories**: `trycua/cua-bench/mota_24_easy/task_0_agent_logs/trajectories/<timestamp>_<model>_<hash>/`
  - Each trajectory has `turn_NNN/` subdirectories
  - Each turn contains:
    - `NNNN_api_start.json` — API request payload (messages sent to model)
    - `NNNN_api_result.json` — raw API response
    - `NNNN_agent_response.json` — parsed response with `response.output[]` containing text, tool calls
    - `NNNN_screenshot_after.png` — screenshot after the action was taken
    - `NNNN_computer_call_result.json` — result of computer tool call
  - `metadata.json` — run metadata (model, timestamps, config)

- **Evaluation JSONs**: `trycua/cua-bench/mota_24_easy/GAME_MOTA_24_EZ_evaluation_<timestamp>.json`
  - Contains: `evaluations[]` with per-milestone scores, VLM responses, and file paths
  - Contains: `summary` with `total_score`, `num_evaluated`, `num_reference_files`

- **Reference images**: On the remote VM at `C:\Users\User\Desktop\game\GAME_MOTA_24_EZ\reference\`
  - `1.png`, `2.png`, `3.png` — reference screenshots for floors 1, 2, 3

- **Agent output images**: On the remote VM at `C:\Users\User\Desktop\game\GAME_MOTA_24_EZ\output\`
  - Milestone screenshots saved by the agent during the run

- **Append-only report**: `logs/loop_run/report.md`

### Game Context (Magic Tower / MOTA-24)

- Flash game running in Ruffle Player on a remote Windows VM
- Game starts in a **Prologue area** ("序 章"), then Floor 1 ("第 1 层"), Floor 2 ("第 2 层"), etc.
- Floor indicator is in the bottom-left panel of the game UI (Chinese text)
- Task goal: navigate to Floor 3, save milestone screenshots for each floor reached
- Agent saves milestones via `save_milestone_screenshot` tool to `C:\...\output\N.png`

### Known Failure Patterns (from prior analyses)

1. **Off-by-one floor counting**: Agent treats Prologue as Floor 1, causing all floor numbers to be wrong. Agent should read the in-game floor indicator text ("序 章" = Prologue, "第 N 层" = Floor N).
2. **Rationalization over observation**: Agent dismisses game UI text when it contradicts the agent's internal model (e.g., "Floor indicator shows '第 1 层' but map layout confirms this is Floor 2").
3. **Hallucinated completion**: Agent writes "TASK COMPLETED" to memory without verifying screenshots match the actual floor.
4. **Insufficient steps**: 50 steps may only reach Floor 1. Reaching Floor 3 requires navigating through monsters, keys, and locked doors.

---

## Steps

### 1. Identify the target trajectory

If a target was provided via $ARGUMENTS, use it. Otherwise, find the most recent:

```bash
ls -t trycua/cua-bench/mota_24_easy/task_0_agent_logs/trajectories/ | head -1
```

Also find the most recent evaluation JSON:
```bash
ls -t trycua/cua-bench/mota_24_easy/GAME_MOTA_24_EZ_evaluation_*.json | head -1
```

### 2. Read evaluation results

Read the evaluation JSON to get scores, VLM responses, and which milestones were evaluated.

### 3. Read trajectory metadata

Read `metadata.json` from the trajectory directory for model, step count, timing.

### 4. Inspect key screenshots

View the screenshots (PNG files) at these critical moments:
- **First screenshot** (`turn_000/..._screenshot_after.png`): Was the game loaded? What floor?
- **Last screenshot** (final turn): Where did the agent end up?
- **Milestone screenshots**: The turns where `save_milestone_screenshot` was called — verify the floor indicator matches what the agent claimed.
- **Floor transition moments**: Any turn where the map layout changed.

### 5. Extract agent reasoning

For each turn, read the `agent_response.json` files and extract:
- Text reasoning/summaries (in `response.output[].summary[].text` or `response.output[].text`)
- Tool calls (`type: "function_call"` entries)
- Compaction summaries if present (look for `[Compaction summary]` in assistant messages)

Focus on:
- What floor did the agent *think* it was on?
- Did the agent read the in-game floor indicator?
- When did the agent save milestones and what did it claim?
- Did the agent encounter any errors or get stuck?

### 6. Diagnose failure (or confirm success)

Cross-reference:
- Agent's claimed floor vs. the in-game floor indicator in screenshots
- Agent's saved milestone screenshots vs. evaluation results
- Agent's reasoning vs. actual game state

Classify the failure mode:
- **Navigation failure**: Agent couldn't reach the target floor
- **Floor misidentification**: Agent reached the floor but mislabeled it
- **Screenshot timing**: Agent saved milestone at the wrong moment
- **Insufficient steps**: Agent ran out of steps before reaching the goal
- **Game state issue**: Game crashed, didn't load, or was in unexpected state
- **Tool error**: save_milestone_screenshot or other tool failed

### 7. Append findings to report

Append a new timestamped section to `logs/loop_run/report.md` with:

```markdown
---

## <YYYY-MM-DD HH:MM> — Analysis: <trajectory-name>

**Result**: <PASS/FAIL> <score> / <total>
**Trajectory**: `<trajectory-name>` (<N> turns)
**Model**: <model-id>
**Eval file**: `<eval-filename>`

### What Happened
<2-3 sentence summary of what the agent did>

### Floor Progression
| Turn | Agent Claimed | Actual (from UI) | Screenshot |
|------|--------------|-------------------|------------|
| ... | ... | ... | ... |

### Failure Mode
<Classification and explanation>

### Key Evidence
<Specific turns, screenshots, or agent quotes that support the diagnosis>

### Recommendations
<What should change for future runs — task description, TASK_MEMORY.md, max_steps, agent behavior>
```

### 8. Report to user

Print a concise summary of findings to the user.

---

## Important Notes

- **Always view screenshots** — don't rely solely on agent text. The agent may hallucinate.
- **Read the floor indicator** in the bottom-left panel of each screenshot. It's the ground truth for which floor the agent is on.
- **Check for compaction**: If the trajectory has many turns, compaction may have occurred. Look for compaction summaries in agent responses — they can reveal what context was lost.
- **Compare with prior analyses**: Read `logs/loop_run/report.md` first to see if the same failure patterns recur.
- **Only append to report.md** — never delete or modify prior entries.
