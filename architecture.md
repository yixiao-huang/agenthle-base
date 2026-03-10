<!-- Last updated: 2026-03-09 (added planner.py) -->
# AgentHLE Architecture

## Overview

AgentHLE is a benchmark framework for evaluating AI agents on computer-use tasks running on remote Windows VMs. It builds on the CUA (Computer Use Agent) framework (git submodule) and adds its own agent harness, memory system, and evaluation pipeline.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Shell Script Entry                       │
│   run_magic_tower.sh / run_helloworld.sh                    │
│   → uv run python -m cua_bench.batch.solver ./tasks/...     │
│     --agent agenthle-agent --eval --max-steps N             │
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
│  Remote VM    │  │        AgentHLE Agent                  │
│  (Windows)    │  │  submodules/cua/libs/cua-bench/        │
│               │  │  cua_bench/agents/agenthle_agent.py    │
│  computer-    │  │                                        │
│  server:5000  │  │  Tools:                                │
│               │◄─┤   - Computer (mouse/keyboard/screen)   │
│  Receives     │  │   - MilestoneTool (save screenshots)   │
│  actions,     │  │   - MemorySearchTool (recall memory)   │
│  returns      │  │                                        │
│  screenshots  │  │  Loop: async for result in agent.run() │
│               │  │   - Track token usage                  │
│               │  │   - Log steps to daily memory          │
│               │  │   - Check for DONE signal              │
│               │  │   - Respect max_steps                  │
└───────────────┘  └───────────────────────────────────────┘
```

## Directory Structure

```
agenthle-base/
├── CLAUDE.md                    # Agent coding instructions
├── prd.json                     # PRD with user stories & status
├── progress.txt                 # Living knowledge base
├── pyproject.toml               # Python config (uv workspace)
├── opencua.py                   # VM connection test utility
│
├── memory/                      # TinyClaw memory system
│   ├── __init__.py              # Exports MemoryStore, tools, call_planner
│   ├── planner.py               # call_planner() — shared LLM client for memory ops
│   ├── store.py                 # MemoryStore (MEMORY.md + daily logs)
│   └── tools.py                 # MemorySearchTool, MemoryGetTool (BaseTool)
│
├── memory_data/                 # Runtime memory storage
│   └── memory_logs/             # Daily logs (YYYY-MM-DD.md)
│
├── utils/
│   └── evaluation.py            # VLM judge, EvaluationContext, modes
│
├── tasks/
│   ├── common_config.py         # GeneralTaskConfig base class
│   ├── helloworld/main.py       # Test milestone task
│   └── game/
│       ├── mota_24/main.py
│       └── mota_24_easy/main.py # Magic Tower easy task
│
├── tests/
│   ├── test_memory_store.py     # 25 tests for MemoryStore
│   └── test_memory_tools.py     # 22 tests for MemorySearchTool + MemoryGetTool
│
├── .claude/skills/              # Claude Code skills (SKILL.md files)
│   ├── onboard/SKILL.md        # /onboard — session startup, reads key files
│   ├── prd/SKILL.md            # /prd — create/update prd.json
│   ├── judge/SKILL.md          # /judge — peer-review, VM test, golden ref audit
│   └── ship/SKILL.md           # /ship — self-review, commit, push
├── skills/                      # Legacy skills directory
│   └── prd/SKILL.md
│
├── run_helloworld.sh            # Task runners
├── run_magic_tower.sh
├── test_eval.sh
├── test_launch.sh
│
├── submodules/cua/              # CUA framework (git submodule)
│   └── libs/
│       ├── python/
│       │   ├── agent/           # ComputerAgent SDK (tools, BaseTool)
│       │   ├── computer/        # Desktop session management
│       │   ├── computer-server/ # Remote VM server
│       │   ├── core/            # Base interfaces
│       │   ├── som/             # Screen Objects Model
│       │   └── mcp-server/      # MCP integration
│       └── cua-bench/           # Benchmark orchestration
│           └── cua_bench/
│               ├── agents/agenthle_agent.py  # Our agent
│               ├── batch/solver.py           # Batch orchestrator
│               ├── computers/remote.py       # RemoteDesktopSession
│               └── decorators.py             # @cb.tasks_config, etc.
│
├── helloworld/                  # Test output traces
├── trycua/                      # Solver output directory
└── .venv/                       # Virtual environment
```

## Core Components

### 1. Agent Harness (`agenthle_agent.py`)

The `AgentHLEAgent` class (`@register_agent("agenthle-agent")`):

- **`perform_task()`** — Main async entry point
  - Creates `ComputerAgent` from CUA SDK with tools: Computer, MilestoneTool, MemorySearchTool, MemoryGetTool
  - Model: configurable, default `anthropic/claude-sonnet-4-20250514`
  - Only keeps 3 most recent images in context
  - Runs agent loop, tracking tokens and steps
  - Returns `AgentResult` with usage stats and failure mode

For details on how the CUA agent loop manages its conversation context (sliding window, truncation, what survives across turns, and why TinyClaw is needed), see [docs/cua-context-management.md](docs/cua-context-management.md). For the OpenClaw reference implementation (system prompt, compaction prompts, memory recall, tool loop), see [docs/openclaw-context-flow.md](docs/openclaw-context-flow.md).

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

### 4. Memory System (TinyClaw)

**MemoryStore** (`memory/store.py`):
- `MEMORY.md` — curated long-term memory (overwritable)
- `memory_logs/YYYY-MM-DD.md` — daily append-only logs with timestamps
- Search: case-insensitive substring matching, scored by keyword count

**MemorySearchTool** (`memory/tools.py`):
- Registered as `memory_search` via `@register_tool`
- Accepts: `keywords: list[str]`, `max_results: int`
- Returns formatted results with file, line, score, content

**MemoryGetTool** (`memory/tools.py`):
- Registered as `memory_get` via `@register_tool`
- Accepts: `path: str`, `from: int` (optional), `lines: int` (optional)
- Reads specific file content with line slicing; .md-only, rejects path traversal
- Ref: openclaw/src/agents/tools/memory-tool.ts

**call_planner** (`memory/planner.py`):
- Async function: `call_planner(system_prompt, user_prompt, model="gpt-4.1-mini") → str`
- Shared LLM client for compaction (US-MEM-CMP) and nudge summarization (US-MEM-004)
- Uses OpenAI SDK; respects OPENAI_API_KEY and OPENAI_API_BASE env vars
- Raises on API failure (caller decides fallback)
- Ref: openclaw/src/agents/compaction.ts (summarizeWithFallback)

## Data Flow

```
Task Description
      │
      ▼
Agent.perform_task()
      │
      ├─── ComputerAgent.run(instruction)
      │       │
      │       ├── Take screenshot (Computer tool)
      │       ├── Perform mouse/keyboard action
      │       ├── Save milestone screenshot (MilestoneTool)
      │       ├── Search memory (MemorySearchTool)
      │       └── Log step to daily memory
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

