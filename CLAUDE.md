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
4. Check `skills/` for available skills (read SKILL.md files).

### After you finish
1. Run `/judge` to audit acceptance criteria, compare against golden references, run a real VM test, and get a critical review.
2. Run `/ship` to self-review, update PRD + progress, and commit+push.

## Key Files

| File | Purpose |
|------|---------|
| `architecture.md` | System architecture, directory structure, data flow (single source of truth) |
| `prd.json` | Current PRD with stories, priorities, acceptance criteria |
| `progress.txt` | Codebase Patterns (top) + per-story progress entries |
| `docs/cua-context-management.md` | How CUA agent context works (sliding window, truncation) |
| `docs/memory-system.md` | TinyClaw memory system design |
| `docs/openclaw-context-flow.md` | OpenClaw context management reference (prompts, compaction, tools) |
| `docs/testing-feedback-loops.md` | Three-level verification guidelines |
| `.current-story` | Story lock file — contains the active story ID (e.g., `US-MEM-003`). Written by `/onboard`, read by `/judge` and `/review-judge`, cleared by `/ship`. Agents must check it before starting — if non-empty with a different story, ask the user before overwriting. |

## Quality Requirements

- Do NOT commit broken code. Keep changes focused and minimal. Follow existing code patterns.
- Commit frequently.
- **Reference attribution**: When a component's design is heavily based on an external implementation, add a docstring noting the source file(s) and what was adopted (API shape, validation rules, etc.).

### Three-Level Verification

See `docs/testing-feedback-loops.md` for full details.

- **Level 1 (Mechanical)**: Lint passes, unit tests pass, smoke test (`run_magic_tower.sh 5`) doesn't crash. Required for all stories.
- **Level 2 (Behavioral)**: Agent actually invokes the feature, content is task-relevant, reasoning references retrieved memory. Required for agent/tool stories.
- **Level 3 (Outcome)**: Multi-session knowledge transfer. Required only for cross-session stories.

**VM test rule**: Any verification step that requires a remote VM (smoke test, real runs, trajectory analysis) is mandatory. If you cannot run it (e.g., no VM connection), you MUST explain why and ask the user to decide the next step — do NOT silently skip it or declare it impractical.

Anti-patterns: logging step counters as "memory", test scaffolding in production code, "doesn't crash" as sufficient for tool stories.

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
- `openclaw/architecture.md` — OpenClaw personal AI assistant

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
- **Branch**: `tinyclaw-memory`

Key rules:
- Agent code (`agenthle_agent.py`) lives inside the submodule at `libs/cua-bench/cua_bench/agents/`
- Commit inside the submodule first, then commit the updated submodule pointer in the parent repo
- Push submodule commits before pushing the parent repo
- Push goes to the fork, not upstream
- Fresh clone init: `git submodule update --init submodules/cua`
