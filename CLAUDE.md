# AgentHLE Agent Instruction

You are a helpful coding agent working building the agent harness for AgentHLE (check the project overview).


## Your Task
### Before you start
1. Read the PRD at prd.json (in the same directory as this file)
3. Read the progress log at `progress.txt` (check Codebase Patterns section first) and recent git history to understand the progress.
4. Check you're on the correct branch from PRD `branchName`. If not, check it out or create from main.
5. Enter the planning mode to draft the plan for the story you are working on.
### During your work
1. Update progress.txt if you discover reusable patterns (see below)
2. Since the project is still in early development, feel free to propose new checks for the story you are working on. 
3. Read the SKILL.md in /skills to understand the skills that the agent can use.

### After you finish
1. Update the PRD to set passes: true for the completed story
2. Append your progress to progress.txt
3. If checks pass, commit ALL changes with message: feat: [Story ID] - [Story Title] and push to the branch.

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

Only add patterns that are **general and reusable**, not story-specific details. For story-specific details, add them to the `**Learnings for future iterations:**` section in each story entry.

Before committing, review your changes for learnings worth preserving:
- API patterns or conventions specific to a module
- Gotchas or non-obvious requirements
- Dependencies between files
- Testing approaches, configuration or environment requirements

Add these to progress.txt: **general and reusable** ones go to Codebase Patterns, **story-specific** ones go to the story's `**Learnings for future iterations:**` section.

**Do NOT duplicate patterns** across progress.txt and CLAUDE.md. CLAUDE.md is for static project structure and architecture only — progress.txt is the living knowledge base.

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





## Important

- Commit frequently
- Read the Codebase Patterns section in progress.txt before starting