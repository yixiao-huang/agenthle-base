# AgentHLE Agent Instruction

You are a helpful coding agent building the agent harness for AgentHLE.

## Project Overview

Agenthle is a benchmark framework for evaluating AI agents on computer-use tasks running on remote Windows VMs. It builds on the [CUA (Computer Use Agent)](https://cua.ai) framework, included as a git submodule. Tasks define instructions for an agent to perform actions on a remote desktop, then evaluate the agent's output (typically screenshots) against reference images using VLM-based judging. Your focus should be on the agent side instead of contributing more tasks.

## Workflow

### Starting a session
Run `/onboard` to read all key files, check git state, and identify the current story. Then enter planning mode to draft the plan for the story you're working on.

### During your work
1. Update `progress.txt` if you discover reusable patterns (see Progress Tracking below).
2. Propose new checks for the story if appropriate — the project is in early development.
3. Use `/prd` to create or update `prd.json`. Do NOT write it by hand.
4. Check `.claude/skills/` for available skills (read SKILL.md files).

### After you finish
1. Run `/judge` to audit acceptance criteria, compare against golden references, run a real VM test, and get a critical review.
2. Run `/ship` to self-review, update PRD + progress, and commit+push.

## Key Files (Progressive Exposure)

Use **progressive exposure** — load only what the current story requires. `/onboard` follows these layers automatically.

### Layer 0 — Always read (every session)

| File | Purpose |
|------|---------|
| `CLAUDE.md` | This file — workflow, quality rules, git conventions |
| `architecture.md` | System architecture, directory structure, data flow |
| `progress.txt` | Codebase Patterns (top) + per-story progress entries |
| `prd.json` | Current PRD with stories, priorities, acceptance criteria |
| `.current-story` | Story lock file — active story ID |

### Layer 1 — Read when your story needs it (reference docs)

| File | When to read |
|------|-------------|
| `docs/openclaw-context-flow.html` | Stories involving the context pipeline (open in browser) |
| `docs/openclaw-source-analysis.md` | Stories reproducing specific OpenClaw components |
| `../openclaw/docs/concepts/<topic>.md` | The specific concept your story targets — pick 1-2, not all (external sibling dir) |
| `docs/testing-feedback-loops.md` | Writing acceptance criteria (`/prd`) or reviewing (`/judge`) |

### Layer 2 — Read when modifying (source code)

| File | When to read |
|------|-------------|
| `../openclaw/src/` | The OpenClaw module your story reproduces — read first to understand target behavior (external sibling dir) |
| `submodules/cua/libs/cua-bench/cua_bench/agents/openclaw/` | Agent harness OpenClaw modules (memory, session, context, etc.) |
| `submodules/cua/libs/cua-bench/cua_bench/agents/openclaw_agent.py` | Agent harness changes |
| `submodules/cua/libs/python/agent/` | CUA SDK internals — only when changing framework interaction |

## Quality Requirements

- Do NOT commit broken code. Keep changes focused and minimal. Follow existing code patterns.
- Commit frequently.
- **Reference attribution**: When a component's design is heavily based on an external implementation, add a docstring noting the source file(s) and what was adopted (API shape, validation rules, etc.).

### Three-Level Verification

See `docs/testing-feedback-loops.md` for full details. The `/prd` skill embeds these guidelines into acceptance criteria; `/judge` enforces them.

**Key rule**: Level 2+ VM tests (at least 50 steps) are mandatory for agent/tool stories. If a VM run fails for any reason, show the error and ask the user — do NOT skip it.

## Progress Tracking

Create `progress.txt` if it doesn't exist. APPEND to it (never replace):
```
## [Date/Time] - [Story ID]
- What was implemented
- Files changed
- **Learnings for future iterations:**
  - Patterns, gotchas, useful context
---
```

### Where learnings go

- **Codebase Patterns** (top of progress.txt) — patterns that apply across multiple stories. Ask: "Would someone on an unrelated story need this?"
- **Story learnings** — details specific to one feature area.

Examples:
```
GOOD pattern:  "Use `uv sync --reinstall` if editable CUA packages fail to import" (repo-wide)
BAD pattern:   "ImageRetentionCallback removes triplets" (only matters for context management)
```

When in doubt, put it in story learnings. Do NOT duplicate patterns across `progress.txt` and `CLAUDE.md`.

### Before committing

Review changes for learnings worth preserving:
- Tooling, env setup, repo-wide conventions → **Codebase Patterns**
- Everything else (API patterns, gotchas, module internals, file dependencies) → **story learnings**

## Architecture

Read `architecture.md` for the full picture. Available architecture files:
- `architecture.md` — AgentHLE benchmark framework
- `../openclaw/architecture.md` — OpenClaw personal AI assistant (external sibling dir)

### Creating architecture.md
When a codebase lacks one, create it (<150 lines) covering:
1. **System overview** — one paragraph
2. **Architecture diagram** — ASCII diagram of components + data flow
3. **Directory structure** — tree with one-line descriptions
4. **Core components** — major modules and entry points
5. **Key configuration** — env vars, config files

architecture.md is for **stable structural knowledge** only — not workflow (CLAUDE.md) or evolving patterns (progress.txt).

### Updating architecture.md
After work that changes the architecture, update before committing:
- Added/removed major components → update directory structure + core components
- Changed data flow → update architecture diagram
- Added env vars/config → update configuration section
- Minor internal refactors → no update needed

Update the `<!-- Last updated: YYYY-MM-DD -->` comment when making changes.

## Git: CUA Submodule

The CUA framework lives at `submodules/cua/` as a git submodule tracking a **separate repo**:

- **origin** (fetch): `git@github.com:cua-verse/cua.git` (upstream, read-only)
- **origin** (push): `git@github.com:yixiao-huang/cua.git` (fork, push URL override)
- **fork**: `git@github.com:yixiao-huang/cua.git` (same fork, explicit remote)
- **Branch**: `openclaw-cua`

Key rules:
- Agent harness (`openclaw_agent.py`) lives inside the submodule at `submodules/cua/libs/cua-bench/cua_bench/agents/`
- Commit inside the submodule first, then commit the updated submodule pointer in the parent repo
- Push submodule commits before pushing the parent repo
- Push goes to the fork, not upstream
- Fresh clone init: `git submodule update --init submodules/cua`
