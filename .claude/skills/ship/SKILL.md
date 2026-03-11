---
name: ship
description: "Self-review, commit, and push changes for the current story. Delegates all work to a Haiku subagent to minimize cost in bloated contexts. Use when you're done with a story."
user-invocable: true
---

# Ship

Self-review, commit, and push the current story's changes.

**Cost optimization**: This skill delegates ALL work to a Haiku subagent with a fresh context window, so it costs ~$0.10 instead of ~$1+ in a large conversation.

---

## Execution

Launch a **single general-purpose Agent** with `model: haiku` and pass it the full instructions below. Do NOT do any of the work yourself — just spawn the agent and relay its result.

```
prompt: |
  You are shipping code for the AgentHLE project. Follow these steps exactly.

  ## Context
  - Working directory: /media/volume/MOL-System/agenthle-base
  - Read `.current-story` to get the active story ID
  - Read `CLAUDE.md` for commit conventions and progress.txt format
  - Read `prd.json` to find the story title and acceptance criteria

  ## Steps

  ### 1. Self-review: audit the diff

  Run `git diff` and `git diff --cached` to see all changes. Review every changed file against this checklist:

  **Correctness**
  - No debug prints, TODO/FIXME left unaddressed, or commented-out code
  - No test scaffolding or hardcoded values in production code
  - No unused imports or variables
  - Error handling is appropriate

  **Scope**
  - Every changed file is justified by the current story
  - No unrelated formatting changes mixed with logic changes

  **Security**
  - No secrets (API keys, passwords, tokens) in staged files
  - No .env or credentials files staged

  **Consistency**
  - New code follows existing patterns in the same file/module
  - Naming conventions match the codebase

  If any check fails, fix it before proceeding. Report what you fixed.

  ### 2. Run Level 1 checks (lint + unit tests only)

  - `uv run ruff check .` (lint)
  - `uv run pytest` for any unit tests relevant to changed files

  Do NOT re-run VM tests. If checks fail, fix and re-review.

  ### 3. Update progress.txt

  Append a progress entry for the story using this format:
  ```
  ## [Date/Time] - [Story ID]
  - What was implemented
  - Files changed
  - **Learnings for future iterations:**
    - Patterns, gotchas, useful context
  ---
  ```
  Review if any learnings should be promoted to Codebase Patterns at the top.

  ### 4. Update PRD

  Set `passes: true` for the completed story in `prd.json`.

  ### 5. Check for submodule changes

  If any files under `submodules/cua/` were modified:
  1. `cd submodules/cua && git add -A && git commit -m "feat: [Story ID] - [description]"`
  2. `git push` (pushes to fork, not upstream)
  3. `cd` back to project root

  This must happen BEFORE the parent repo commit.

  ### 6. Update architecture.md (if needed)

  If the story added/removed components, changed data flow, or added config — update architecture.md. Skip for internal-only refactors.

  ### 7. Commit and push

  ```bash
  git add -A
  git commit -m "feat: [Story ID] - [Story Title]"
  git push
  ```

  ### 8. Clear story lock

  Write an empty string to `.current-story`.

  ### 9. Final verification

  Run `git status` and `git log --oneline -3` to confirm the commit landed cleanly.

  ## Important

  - Do NOT skip the self-review.
  - If you find issues during review, fix them before committing.
  - If Level 1 checks fail, do not commit. Fix first.
  - Always push submodule before parent repo.
  - Report back: what was committed, any issues found and fixed, final git status.
```

## How to execute

Use the Agent tool with these parameters:
- `subagent_type`: `general-purpose`
- `model`: `haiku`
- `description`: `Ship current story`
- `prompt`: The full prompt text above (fill in any dynamic values like story ID if already known)

Then relay the agent's result back to the user.
