# AgentHLE Agent Instruction

You are a helpful coding agent working building the agent harness for AgentHLE (check the project overview).


## Your Task
1. Read the PRD at prd.json (in the same directory as this file)
2. Read the SKILL.md in /skills to understand the skills that the agent can use.
3. Read the progress log at `progress.txt` (check Codebase Patterns section first)
4. Check you're on the correct branch from PRD `branchName`. If not, check it out or create from main.
5. Update CLAUDE.md files if you discover reusable patterns (see below)
6. If checks pass, commit ALL changes with message: feat: [Story ID] - [Story Title]
7. Since the project is still in early development, feel free to propose new checks for the story you are working on.
8. Update the PRD to set passes: true for the completed story
9. Append your progress to progress.txt

## Project Overview

Agenthle is a benchmark framework for evaluating AI agents on computer-use tasks running on remote Windows VMs. It builds on the [CUA (Computer Use Agent)](https://cua.ai) framework, included as a git submodule. Tasks define instructions for an agent to perform actions on a remote desktop, then evaluate the agent's output (typically screenshots) against reference images using VLM-based judging. Your focus should be on the agent side instead of contributing more tasks.


## Progress Report Format
Create one if there is no progress.txt file. APPEND to progress.txt (never replace, always append):
```
## [Date/Time] - [Story ID]
- What was implemented
- Files changed
- **Learnings for future iterations:**
  - Patterns discovered (e.g., "this codebase uses X for Y")
  - Gotchas encountered (e.g., "don't forget to update Z when changing W")
  - Useful context (e.g., "the evaluation panel is in component X")
---
```

The learnings section is critical - it helps future iterations avoid repeating mistakes and understand the codebase better.

## Consolidate Patterns

If you discover a **reusable pattern** that future iterations should know, add it to the `## Codebase Patterns` section at the TOP of progress.txt (create it if it doesn't exist). This section should consolidate the most important learnings:

```
## Codebase Patterns
- Example: Use `sql<number>` template for aggregations
- Example: Always use `IF NOT EXISTS` for migrations
- Example: Export types from actions.ts for UI components
```

Only add patterns that are **general and reusable**, not story-specific details.
## Update CLAUDE.md Files

Before committing, check if any edited files have learnings worth preserving in nearby CLAUDE.md files:

1. **Identify directories with edited files** - Look at which directories you modified
2. **Check for existing CLAUDE.md** - Look for CLAUDE.md in those directories or parent directories
3. **Add valuable learnings** - If you discovered something future developers/agents should know:
   - API patterns or conventions specific to that module
   - Gotchas or non-obvious requirements
   - Dependencies between files
   - Testing approaches for that area
   - Configuration or environment requirements

**Examples of good CLAUDE.md additions:**
- "When modifying X, also update Y to keep them in sync"
- "This module uses pattern Z for all API calls"
- "Tests require the dev server running on PORT 3000"
- "Field names must match the template exactly"

**Do NOT add:**
- Story-specific implementation details
- Temporary debugging notes
- Information already in progress.txt

Only update CLAUDE.md if you have **genuinely reusable knowledge** that would help future work in that directory.

## Quality Requirements

- Do NOT commit broken code
- Keep changes focused and minimal
- Follow existing code patterns

## Architecture

### Agent Harness (primary focus)
The agent harness is the core system that drives AI agents to perform computer-use tasks. It is built on top of the CUA framework:

- **CUA Submodule** (`submodules/cua/`) — Contains all CUA framework packages installed as editable dependencies: `cua-core`, `cua-computer`, `cua-agent`, `cua-computer-server`, `cua-som`, `cua-mcp-server`, `cua-bench`
- **Agent entry point** — Tasks are run via shell scripts (see `run_helloworld.sh` and `run_magic_tower.sh` as examples), which invoke `uv run python -m cua_bench.batch.solver ./tasks/<task_dir>` with `--agent agenthle-agent`
- **Remote interaction** — The agent connects to a Windows VM running `computer-server` on port 5000 via `cua_bench.computers.remote.RemoteDesktopSession`, sending mouse/keyboard actions and receiving screenshots
- **Agent capabilities** — The agent can take screenshots, perform mouse/keyboard actions, and call special functions like `save_milestone_screenshot()` to record progress

### Evaluation System (`utils/evaluation.py`)
- **`llm_vision_judge`** — Core VLM evaluation: sends images to OpenAI vision API, supports single-image and comparison modes, returns YES/NO binary scores
- **`EvaluationContext`** — Context manager that tracks scores, logs individual evaluations, and auto-saves JSON results
- **`evaluate_milestone_mode`** — Compares agent-saved milestone screenshots against reference images
- **`evaluate_deliverable_mode`** — Replays agent trajectory, takes screenshots at specified action points, compares with references

### Task Structure (for reference)
Each task lives in `tasks/<category>/<task_name>/main.py` and defines three `cua_bench`-decorated functions:
1. **`@cb.tasks_config(split="train")`** — returns `cb.Task` objects with description, metadata, and computer config
2. **`@cb.setup_task(split="train")`** — async setup of the remote environment
3. **`@cb.evaluate_task(split="train")`** — async scoring, returns `list[float]`

Tasks inherit from `GeneralTaskConfig` (`tasks/common_config.py`) for standard Windows path conventions (`C:\Users\User\Desktop\<category>\<task_tag>`).

### Key Environment Variables
- `VM_IP` / `CUA_ENV_API_URL` — Remote Windows VM address (computer-server on port 5000)
- `OPENAI_API_KEY` — For the agent and VLM evaluation judge
- `OPENAI_API_BASE` — Optional, for LiteLLM proxy
- `CUA_ENV_TYPE` — OS type, typically `"windows"`
- `REMOTE_OUTPUT_DIR` — Output directory name on remote machine (default: `"output"`)
- `EVALUATION_OUTPUT_DIR` — Local directory for evaluation JSON results




## Learnings

- **`uv sync` doesn't rebuild editable CUA packages**: The editable CUA submodule packages (installed via `.pth` files) can become stale after submodule updates or venv changes. A plain `uv sync` sees them as already installed and skips rebuilding, causing `ModuleNotFoundError: No module named 'cua_bench'`. Fix with `uv sync --reinstall` to force a full rebuild of all packages.
- **`direnv` doesn't auto-load in Bash tool sessions**: The Bash tool spawns non-interactive shells, so `direnv hook bash` from `.bashrc`/`.zshrc` doesn't run. Env vars from `.envrc` (like `VM_IP`) won't be set automatically. Use `eval "$(direnv export bash)"` before commands that depend on `.envrc` variables. The `.envrc` file lives in the parent `AgentHLE/` directory, not in `agenthle-base/`.


## Important

- Commit frequently
- Read the Codebase Patterns section in progress.txt before starting