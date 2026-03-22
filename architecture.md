<!-- Last updated: 2026-03-22 -->
# AgentHLE Architecture

## Overview

AgentHLE is a benchmark framework for evaluating AI agents on computer-use tasks running on remote Windows VMs. It builds on the CUA (Computer Use Agent) framework (git submodule) and adds its own agent harness, memory system, and evaluation pipeline. The agent harness reproduces OpenClaw's agent-side architecture adapted for CUA's constraints.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Shell Script Entry                       │
│   run_magic_tower.sh / run_helloworld.sh                    │
│   → uv run python -m cua_bench.batch.solver ./tasks/...     │
│     --agent openclaw-agent --eval --max-steps N              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Batch Solver (CUA Framework)                    │
│   submodules/cua/libs/cua-bench/cua_bench/batch/solver.py   │
│                                                              │
│   1. Parse CLI args                                          │
│   2. Connect to remote VM (RemoteDesktopSession)             │
│   3. Load task module (tasks/<cat>/<name>/main.py)           │
│   4. Run @cb.setup_task     → environment init               │
│   5. Run agent.perform_task → agent loop                     │
│   6. Run @cb.evaluate_task  → scoring                        │
│   7. Record trajectory & results                             │
└───────┬──────────────────┬──────────────────────────────────┘
        │                  │
        ▼                  ▼
┌───────────────┐  ┌───────────────────────────────────────┐
│  Remote VM    │  │        OpenClaw Agent                  │
│  (Windows)    │  │  submodules/cua/libs/cua-bench/        │
│               │  │  cua_bench/agents/openclaw_agent.py    │
│  computer-    │  │                                        │
│  server:5000  │  │  Tools:                                │
│               │◄─┤   - Computer (mouse/keyboard/screen)   │
│  Receives     │  │   - MilestoneTool (save screenshots)   │
│  actions,     │  │                                        │
│  returns      │  │  Loop: async for result in agent.run() │
│  screenshots  │  │   - Track token usage                  │
│               │  │   - Check for DONE signal              │
│               │  │   - Respect max_steps                  │
└───────────────┘  └───────────────────────────────────────┘
```

## Directory Structure

```
agenthle-base/
├── CLAUDE.md                    # Agent instructions + progressive exposure layers
├── architecture.md              # This file — system architecture
├── prd.json                     # Current PRD with user stories & status
├── progress.txt                 # Codebase patterns + per-story progress
├── pyproject.toml               # Python config (uv workspace)
├── .current-story               # Story lock file (active story ID)
│
├── utils/
│   └── evaluation.py            # VLM judge, EvaluationContext, scoring modes
│
├── tasks/
│   ├── common_config.py         # GeneralTaskConfig base class
│   ├── helloworld/main.py       # Test milestone task
│   └── game/
│       ├── mota_24/main.py
│       └── mota_24_easy/main.py # Magic Tower easy task
│
├── docs/                        # Reference docs & audit reports
│   ├── openclaw-context-flow.html    # Interactive OpenClaw pipeline visual
│   ├── openclaw-source-analysis.md   # OpenClaw TypeScript source analysis
│   ├── testing-feedback-loops.md     # Three-level verification guidelines
│   ├── judges/                       # /judge audit reports (timestamped)
│   └── review-judges/                # /review-judge action plans (timestamped)
│
├── logs/                        # Raw audit logs from /judge runs
│
│   # External reference (NOT in this repo — sibling directory)
│   # ../openclaw/                 # OpenClaw source (TypeScript reference implementation)
│   #   ├── src/agents/            # Agent loop, tools, compaction, system prompt
│   #   ├── src/memory/            # Memory system (SQLite + embeddings)
│   #   ├── src/sessions/          # Session persistence
│   #   └── docs/concepts/         # Component-level docs (memory, compaction, etc.)
│
├── .claude/skills/              # Claude Code skills
│   ├── onboard/SKILL.md        # /onboard — session startup
│   ├── first-onboard/SKILL.md  # /first-onboard — one-time setup
│   ├── prd/SKILL.md            # /prd — create/update prd.json
│   ├── judge/SKILL.md          # /judge — peer-review, VM test, audit
│   ├── review-judge/SKILL.md   # /review-judge — diff reports, action plan
│   └── ship/SKILL.md           # /ship — self-review, commit, push
│
├── run_magic_tower.sh           # Main task runner (openclaw-agent)
├── run_helloworld.sh            # Hello world task runner
├── opencua.py                   # VM connection test utility
│
├── submodules/cua/              # CUA framework (git submodule)
│   └── libs/
│       ├── python/
│       │   ├── agent/           # ComputerAgent SDK (tools, BaseTool)
│       │   ├── computer/        # Desktop session management
│       │   ├── computer-server/ # Remote VM server
│       │   ├── core/            # Base interfaces
│       │   └── som/             # Screen Objects Model
│       └── cua-bench/           # Benchmark orchestration
│           └── cua_bench/
│               ├── agents/openclaw_agent.py  # Our agent harness (OpenClawAgent)
│               │           openclaw/          # OpenClaw modules
│               │           ├── agent_loop.py # OpenClawComputerAgent — custom run() with in-place compaction (US-OC-017)
│               ├── batch/solver.py           # Batch orchestrator
│               ├── computers/remote.py       # RemoteDesktopSession
│               └── decorators.py             # @cb.tasks_config, etc.
│
├── trycua/                      # Solver output directory (trajectories)
└── helloworld/                  # Hello world output traces
```

## Core Components

### 1. Agent Harness (`openclaw_agent.py`)

`OpenClawAgent` class (`@register_agent("openclaw-agent")`):

- **`perform_task()`** — Main async entry point
  - Builds structured system prompt via `PromptBuilder` (US-OC-001):
    - Identity, Tools (derived from registered tools), Memory Recall (conditional), Project Context (AGENTS.md + task.md)
    - Injects context files as bootstrap (never truncated from context via `instructions=` parameter)
  - Creates `OpenClawComputerAgent` (US-OC-017) — `ComputerAgent` subclass with mutable items list and in-place compaction
  - Memory tools (MemorySearchTool, MemoryGetTool, MemoryWriteTool) are implemented but not yet wired in
  - Model: configurable, default `anthropic/claude-sonnet-4-20250514`
  - Only keeps 3 most recent images in context
  - Runs agent loop, tracking tokens and steps
  - Returns `AgentResult` with usage stats and failure mode

For the OpenClaw reference implementation, see [docs/openclaw-context-flow.html](docs/openclaw-context-flow.html) and [docs/openclaw-source-analysis.md](docs/openclaw-source-analysis.md).

### 2. Task System

Each task is a Python module at `tasks/<category>/<task_name>/main.py` with three decorated functions:

```python
@cb.tasks_config(split="train")      # Returns list[cb.Task]
@cb.setup_task(split="train")        # Async env setup
@cb.evaluate_task(split="train")     # Async scoring → list[float]
```

Tasks extend `GeneralTaskConfig` (`tasks/common_config.py`) which provides:
- Standard Windows paths: `C:\Users\User\Desktop\<category>\<task_tag>`
- Properties: `task_dir`, `software_dir`, `remote_output_dir`, `reference_dir`

### 3. Evaluation System (`utils/evaluation.py`)

- **`llm_vision_judge()`** — Sends images to OpenAI Vision API, returns YES/NO binary scores
- **`compare_screenshots_game()`** — Game-specific VLM comparison with criteria
- **`EvaluationContext`** — Context manager tracking scores, auto-saves JSON
- **`evaluate_milestone_mode()`** — Compares agent milestone screenshots vs. references
- **`evaluate_deliverable_mode()`** — Replays trajectory, screenshots at action points

### 4. Memory System (`openclaw/memory.py` + `memory_flush.py`)

Lives in the CUA submodule at `submodules/cua/libs/cua-bench/cua_bench/agents/openclaw/`:

- **`memory.py`** — `MemoryStore` with per-task workspace storage (`<base_dir>/tasks/<task_id>/`), plus `MemorySearchTool`, `MemoryGetTool`, `MemoryWriteTool` (BaseTool subclasses)
- **`memory_flush.py`** — Pre-compaction memory persistence (standalone module following OpenClaw's `agent-runner-memory.ts` pattern)

OpenClaw reference source: `../openclaw/src/memory/`, `../openclaw/src/auto-reply/reply/agent-runner-memory.ts`

## Data Flow

```
Task Description
      │
      ▼
Agent.perform_task()
      │
      ├─── OpenClawComputerAgent.run(instruction)  ← mutable items + in-place compaction
      │       │
      │       ├── Take screenshot (Computer tool)
      │       ├── Perform mouse/keyboard action
      │       ├── Save milestone screenshot (MilestoneTool)
      │       └── On overflow: _compact_in_place() rewrites items, loop continues
      │
      ▼
AgentResult (tokens, steps, failure_mode)
      │
      ▼
@cb.evaluate_task()
      │
      ├── evaluate_milestone_mode()
      │     └── compare agent screenshots vs references
      │           └── llm_vision_judge() → YES/NO
      │
      └── Returns list[float] scores
```
