---
name: test-task
description: "End-to-end test workflow for any task: deprecate old memory/session, run the agent loop, and periodically analyze trajectories."
user-invocable: true
---

# Test Task

**Usage:** `/test-task [task_path] [steps] [attempts] [model] [summary_model] [context_window]`

Run a full test session for any task: fresh memory, agent loop, and periodic analysis.

**Defaults:**
- task_path: ./tasks/game/mota_24_easy
- steps: 500
- attempts: 5
- model: anthropic/claude-sonnet-4-20250514
- summary_model: same as model
- context_window: (none — use model default)

## Parsing

Parse arguments from the input. Arguments can be positional or use key=value syntax.

**Positional examples:**
- `/test-task` → all defaults
- `/test-task ./tasks/game/mota_24 200 3 openai/gpt-5.4` → mota_24, 200 steps, 3 attempts, gpt-5.4
- `/test-task ./tasks/helloworld 50 3`

**Recognition rules:**
- An argument starting with `./tasks/` or `tasks/` is the task_path
- An argument containing `/` (but not starting with `tasks/`) is a model ID
- A bare number ≤ 1000 is steps (first) or attempts (second)
- A bare number > 1000 is context_window

**Known task shortcuts** (expand to full path):
- `mota` or `mota_easy` → `./tasks/game/mota_24_easy`
- `mota_24` or `mota_hard` → `./tasks/game/mota_24`
- `hello` or `helloworld` → `./tasks/helloworld`

### Interactive mode

If `/test-task` is invoked with **no arguments** (or only partial arguments), prompt the user for missing parameters using AskUserQuestion. Use up to 4 questions per call (AskUserQuestion limit):

**Call 1** — Task and model:
```
Q1: "Which task do you want to test?"
  options: mota_24_easy, mota_24, helloworld, Other
Q2: "Which model for the agent (CUA loop)?"
  options: openai/gpt-5.4, anthropic/claude-sonnet-4-20250514, anthropic/claude-opus-4-6, Other
Q3: "Which model for summarization/compaction?"
  options: Same as agent model (Recommended), openai/gpt-5.4, anthropic/claude-sonnet-4-20250514, Other
Q4: "Steps per run and max attempts?"
  options: 500 steps / 5 attempts, 200 steps / 3 attempts, 50 steps / 1 attempt, Other
```

**Call 2** (only if needed) — Context window:
```
Q1: "Context window override?"
  options: None (model default), 100000, 50000, Other
```

Parse responses — map option labels to values. Then proceed to Step 1.

If arguments are provided inline, skip interactive prompts and use them directly.

---

## Steps

### 1. Onboard

Invoke `/onboard` to build full codebase context (Layer 0 files, repo sync, git state). Skip the planning mode and story selection steps — this is a test run, not a development session.

### 2. Derive task_id

Extract the task name from the task path:
```bash
task_id=$(basename "$task_path")   # e.g. mota_24_easy, helloworld
```

### 3. Session mode: fresh or continue?

Check if prior memory/session data exists for this task:
```bash
ls openclaw_memory/tasks/${task_id}/memory/ 2>/dev/null | wc -l   # session count
test -f openclaw_memory/tasks/${task_id}/TASK_MEMORY.md && echo "has TASK_MEMORY"
test -f openclaw_sessions/${task_id}/state.json && echo "has session state"
```

If prior data exists, ask the user with AskUserQuestion:

```
question: "Prior memory/session found for ${task_id} (<N> sessions, TASK_MEMORY: yes/no). Start fresh or continue?"
options:
  - label: "Fresh session"
    description: "Deprecate existing memory and session — agent starts with no prior context"
  - label: "Continue previous session"
    description: "Keep existing memory and session — agent resumes with accumulated knowledge"
```

**If fresh** (or no prior data exists): deprecate by moving to `deprecated/` with timestamp:
```bash
timestamp=$(date +%Y%m%d_%H%M)
if [ -d "openclaw_memory/tasks/${task_id}" ]; then
    mkdir -p openclaw_memory/deprecated
    mv "openclaw_memory/tasks/${task_id}" "openclaw_memory/deprecated/${task_id}_${timestamp}"
fi
if [ -d "openclaw_sessions/${task_id}" ]; then
    mkdir -p openclaw_sessions/deprecated
    mv "openclaw_sessions/${task_id}" "openclaw_sessions/deprecated/${task_id}_${timestamp}"
fi
```

**If continue**: leave memory and session in place. The agent will load TASK_MEMORY.md into its system prompt and replay prior transcript on startup.

### 4. Verify environment

```bash
uv run python -c "import cua_bench; print('cua_bench OK')"
```

If this fails, run `uv sync --reinstall` and retry. If it still fails, stop and report.

### 5. Start the agent loop (background)

Run the generic loop in background using `run_task_loop.sh`:

```bash
CONTEXT_WINDOW_OVERRIDE=${context_window} bash run_task_loop.sh ${task_path} ${steps} ${attempts} ${model} ${summary_model}
```

Omit `CONTEXT_WINDOW_OVERRIDE` if no context_window was specified.

### 6. Schedule periodic analysis

Use CronCreate to schedule `/analyze <task_id>` every 10 minutes (recurring). This monitors the run and appends findings to `logs/<task_id>/report.md`.

```
CronCreate: cron="*/10 * * * *", prompt="/analyze <task_id>", recurring=true
```

### 7. Run first analysis immediately

Invoke `/analyze` once right away (don't wait for the first cron tick).

### 8. Report to user

```
## Test Started

**Task**: <task_path> (<task_id>)
**Model**: <model>
**Steps per run**: <steps>
**Max attempts**: <attempts>
**Context window**: <context_window or "model default">
**Summary model**: <summary_model>

### Actions taken
- Session mode: <Fresh (deprecated N sessions) | Continue (N prior sessions)>
- Started loop in background (job ID: <id>)
- Scheduled /analyze every 10 min (cron ID: <cron_id>)
- First analysis: <brief status>

### Monitoring
- Log file: `logs/<task_id>/<logfile>`
- Analysis report: `logs/<task_id>/report.md`
- Cancel analysis cron: `CronDelete <cron_id>`
```

---

## Important Notes

- Always deprecate (never delete) prior memory/session data
- Uses `run_task_loop.sh` which accepts any task path
- If the background loop finishes before a cron analysis fires, the next `/analyze` will analyze the final state
- The cron job auto-expires after 7 days
- If the user wants to stop early, they can kill the loop process and cancel the cron
