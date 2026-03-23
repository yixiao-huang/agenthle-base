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

If `/test-task` is invoked with **no arguments**, prompt the user for parameters. Use AskUserQuestion:

```
Please provide the run parameters (press Enter to accept defaults):
- Task path [./tasks/game/mota_24_easy]:
- Steps per run [500]:
- Max attempts [5]:
- Model [anthropic/claude-sonnet-4-20250514]:
- Summary model [same as model]:
- Context window override [none]:
```

Parse the user's response — accept blank/empty for defaults. Then proceed to Step 1.

---

## Steps

### 1. Onboard

Invoke `/onboard` to build full codebase context (Layer 0 files, repo sync, git state). Skip the planning mode and story selection steps — this is a test run, not a development session.

### 2. Derive task_id

Extract the task name from the task path:
```bash
task_id=$(basename "$task_path")   # e.g. mota_24_easy, helloworld
```

### 3. Deprecate current memory and session

Move existing memory and session data to deprecated directories with a timestamp suffix:

```bash
timestamp=$(date +%Y%m%d_%H%M)
# Move memory
if [ -d "openclaw_memory/tasks/${task_id}" ]; then
    mkdir -p openclaw_memory/deprecated
    mv "openclaw_memory/tasks/${task_id}" "openclaw_memory/deprecated/${task_id}_${timestamp}"
fi
# Move session
if [ -d "openclaw_sessions/${task_id}" ]; then
    mkdir -p openclaw_sessions/deprecated
    mv "openclaw_sessions/${task_id}" "openclaw_sessions/deprecated/${task_id}_${timestamp}"
fi
```

Report what was deprecated (number of session files, whether TASK_MEMORY.md existed).
If no prior data exists, report "No prior memory/session to deprecate."

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
- Deprecated prior memory (<N> sessions) and session state
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
