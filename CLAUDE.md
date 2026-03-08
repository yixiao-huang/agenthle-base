# AgentHLE Agent Instruction

You are a helpful coding agent working building the agent harness for AgentHLE (check the project overview).


## Your Task
### Before you start
1. Read the PRD at prd.json (in the same directory as this file)
2. If there is an `architecture.md` in the project root, read it first to understand the system architecture, data flow, directory structure, and key patterns. Always do this when entering a new codebase.
3. Read the progress log at `progress.txt` (check Codebase Patterns section first) and recent git history to understand the progress.
4. Check you're on the correct branch from PRD `branchName`. If not, check it out or create from main.
5. Enter the planning mode to draft the plan for the story you are working on.
### Creating or updating the PRD
Use `/prd` to create a new `prd.json` or add stories to an existing one. The skill handles clarifying questions, story sizing, dependency ordering, and three-level acceptance criteria (see `docs/testing-feedback-loops.md`). Do NOT write `prd.json` by hand — always use the skill.
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

### Where to put learnings

**Codebase Patterns** (top of progress.txt) — ONLY for patterns that apply **across multiple stories**. Ask: "Would someone working on an unrelated story need this?" If yes, it's a pattern. If it only matters for one feature area, it's story-specific.

```
## Codebase Patterns
- GOOD: Use `uv sync --reinstall` if editable CUA packages fail to import
- GOOD: `function_call_output` items are ephemeral — agent must act immediately
- BAD:  Artifact counter in trajectory files is per-turn (only matters for trajectory parsing)
- BAD:  ImageRetentionCallback removes triplets (only matters for context management work)
```

**Story learnings** (`**Learnings for future iterations:**` in each story entry) — for details specific to one feature area. These help someone continuing or debugging that specific work.

### Distinguishing the two

| Goes in Codebase Patterns | Goes in story learnings |
|---------------------------|------------------------|
| Applies to any story in this repo | Only matters for one feature/story area |
| About tooling, env, build, or repo-wide conventions | About a specific module's internals |
| You'd tell a new contributor on day 1 | You'd tell someone picking up your PR |

When in doubt, put it in story learnings. It's easy to promote a learning to a pattern later; it's harder to notice a pattern section is bloated with story-specific noise.

### Before committing

Review your changes for learnings worth preserving:
- API patterns or conventions specific to a module → **story learnings**
- Gotchas or non-obvious requirements → **story learnings** (unless repo-wide)
- Dependencies between files → **story learnings**
- Tooling, env setup, or repo-wide conventions → **Codebase Patterns**

**Do NOT duplicate patterns** across progress.txt and CLAUDE.md. CLAUDE.md is for static project structure and architecture only — progress.txt is the living knowledge base.

## Quality Requirements

- Do NOT commit broken code
- Keep changes focused and minimal
- Follow existing code patterns

### Testing: Three-Level Verification

Every memory-related story must be verified at all applicable levels. See `docs/testing-feedback-loops.md` for the full guideline.

- **Level 1 (Mechanical)**: Unit tests pass, lint passes, smoke test (`run_magic_tower.sh --max-steps 5`) doesn't crash. Automated, required for all stories.
- **Level 2 (Behavioral)**: After a real run (step count at your discretion), verify the agent actually invokes the new tool, memory content is task-relevant (not boilerplate), and agent reasoning references retrieved memory. Required for all memory tool stories.
- **Level 3 (Outcome)**: Multi-session runs show knowledge transfer — session 2 avoids session 1's dead ends, compacted TASK_MEMORY.md contains corrected/deduplicated learnings. Required for US-MEM-004, US-MEM-TSK, US-MEM-006.

Anti-patterns to avoid: logging step counters as "memory", embedding test scaffolding in production code, treating "doesn't crash" as sufficient.

## Architecture

For detailed architecture, read `architecture.md` in the project root. That file is the single source of truth for system architecture, data flow diagrams, directory structure, component descriptions, and key patterns.

### Available architecture.md files
- `agenthle-base/architecture.md` — AgentHLE benchmark framework architecture
- `openclaw/architecture.md` — OpenClaw personal AI assistant architecture

### Key design docs
- `docs/cua-context-management.md` — How CUA agent context works (sliding window, truncation, what survives). Critical for any story that injects content into the agent's context.
- `docs/memory-system.md` — TinyClaw memory system design (storage, tools, nudge, compaction)

### How to create architecture.md
When a codebase lacks an `architecture.md`, create one. Keep it under 150 lines and include:
1. **System overview** — One paragraph on what the project does
2. **Architecture diagram** — ASCII diagram showing how components connect and data flows
3. **Directory structure** — Tree with one-line descriptions per directory/file
4. **Core components** — Brief description of each major module and its entry points
5. **Key configuration** — Environment variables, config files, and their purpose

Do NOT duplicate content that belongs in CLAUDE.md (workflow instructions) or progress.txt (evolving patterns). architecture.md is for **stable structural knowledge** only.

### Post-development: updating architecture.md
After completing work that changes the architecture, update `architecture.md` before committing:
- **Added/removed a major component?** — Update the directory structure and core components sections
- **Changed data flow or integration points?** — Update the architecture diagram
- **Added new environment variables or config?** — Update the configuration section
- **Minor internal refactors?** — No update needed; architecture.md tracks high-level structure, not implementation details

Update the `<!-- Last updated: YYYY-MM-DD -->` comment at the top of the file when making changes.





## Git: CUA Submodule

The CUA framework lives at `submodules/cua/` as a git submodule tracking a **separate repo** with its own remotes:

- **origin** (fetch): `git@github.com:cua-verse/cua.git` (upstream, read-only)
- **origin** (push): `git@github.com:yixiao-huang/cua.git` (fork, push URL override)
- **fork**: `git@github.com:yixiao-huang/cua.git` (same fork, explicit remote)
- **Branch**: `tinyclaw-memory`

Key rules:
- The agent code (`agenthle_agent.py`) lives inside the submodule at `libs/cua-bench/cua_bench/agents/`
- When you modify files in `submodules/cua/`, you must **commit inside the submodule first**, then commit the updated submodule pointer in the parent repo
- **Push submodule commits** before pushing the parent repo — otherwise the parent will reference a commit that doesn't exist on the remote
- Push goes to the fork (`yixiao-huang/cua.git`), not upstream (`cua-verse/cua.git`)
- To init the submodule after a fresh clone: `git submodule update --init submodules/cua`

## Important

- Commit frequently
- Read the Codebase Patterns section in progress.txt before starting