---
name: test-mota
description: "End-to-end test workflow for Magic Tower: deprecate old memory/session, run the agent loop, and periodically analyze trajectories."
user-invocable: true
---

# Test MOTA

**Usage:** `/test-mota [steps] [attempts] [model] [summary_model] [context_window]`

Run a full Magic Tower test session: fresh memory, agent loop, and periodic analysis.

**Defaults:**
- steps: 500
- attempts: 5
- model: anthropic/claude-sonnet-4-20250514
- summary_model: same as model
- context_window: (none — use model default)

## Parsing

Parse positional arguments from the input. Examples:
- `/test-mota` → all defaults
- `/test-mota 200 3 openai/gpt-5.4` → 200 steps, 3 attempts, gpt-5.4, summary=gpt-5.4
- `/test-mota 500 5 openai/gpt-5.4 openai/gpt-5.4 100000` → explicit context window override

Any argument containing `/` is treated as a model ID. A bare number > 1000 at the end is treated as context_window.

### Interactive mode

If `/test-mota` is invoked with **no arguments** (or only partial arguments), prompt the user for the missing parameters before proceeding. Use AskUserQuestion to ask all missing params in a single prompt:

```
Please provide the run parameters (press Enter to accept defaults):
- Steps per run [500]:
- Max attempts [5]:
- Model [anthropic/claude-sonnet-4-20250514]:
- Summary model [same as model]:
- Context window override [none]:
```

Parse the user's response — accept blank/empty for defaults. Then proceed to Step 1.

If arguments are provided inline, skip the interactive prompt and use them directly.

---

## Steps

### 1. Onboard

Invoke `/onboard` to build full codebase context (Layer 0 files, repo sync, git state). Skip the planning mode and story selection steps — this is a test run, not a development session.

### 2. Deprecate current memory and session

Move existing memory and session data to deprecated directories with a timestamp suffix:

```bash
timestamp=$(date +%Y%m%d_%H%M)
# Move memory
if [ -d "openclaw_memory/tasks/mota_24_easy" ]; then
    mkdir -p openclaw_memory/deprecated
    mv openclaw_memory/tasks/mota_24_easy openclaw_memory/deprecated/mota_24_easy_${timestamp}
fi
# Move session
if [ -d "openclaw_sessions/mota_24_easy" ]; then
    mkdir -p openclaw_sessions/deprecated
    mv openclaw_sessions/mota_24_easy openclaw_sessions/deprecated/mota_24_easy_${timestamp}
fi
```

Report what was deprecated (number of session files, whether TASK_MEMORY.md existed).

### 3. Verify environment

```bash
uv run python -c "import cua_bench; print('cua_bench OK')"
```

If this fails, run `uv sync --reinstall` and retry. If it still fails, stop and report.

### 4. Start the agent loop (background)

Run the loop in background:

```bash
CONTEXT_WINDOW_OVERRIDE=${context_window} bash run_magic_tower_loop.sh ${steps} ${attempts} ${model} ${summary_model}
```

Omit `CONTEXT_WINDOW_OVERRIDE` if no context_window was specified.

### 5. Schedule periodic analysis

Use CronCreate to schedule `/analyze` every 10 minutes (recurring). This monitors the run and appends findings to `logs/loop_run/report.md`.

```
CronCreate: cron="*/10 * * * *", prompt="/analyze", recurring=true
```

### 6. Run first analysis immediately

Invoke `/analyze` once right away (don't wait for the first cron tick).

### 7. Report to user

```
## Test MOTA Started

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
- Log file: `logs/loop_run/<logfile>`
- Analysis report: `logs/loop_run/report.md`
- Cancel analysis cron: `CronDelete <cron_id>`
```

---

## Important Notes

- Always deprecate (never delete) prior memory/session data
- If the background loop finishes before a cron analysis fires, the next `/analyze` will analyze the final state
- The cron job auto-expires after 7 days
- If the user wants to stop early, they can kill the loop process and cancel the cron
