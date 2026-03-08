---
name: ship
description: "Self-review, commit, and push changes for the current story. Runs code review checks, updates PRD and progress, handles submodule commits, then commits and pushes. Use when you're done with a story."
user-invocable: true
---

# Ship

Self-review, commit, and push the current story's changes.

---

## Steps

### 1. Self-review: audit the diff

Run `git diff` and `git diff --cached` to see all changes. Then review every changed file against this checklist:

**Correctness**
- [ ] No debug prints, `TODO`/`FIXME` left unaddressed, or commented-out code
- [ ] No test scaffolding or hardcoded values leaked into production code
- [ ] No unused imports or variables introduced
- [ ] Error handling is appropriate — no bare `except:`, no swallowed exceptions

**Scope**
- [ ] Every changed file is justified by the current story — no drive-by refactors
- [ ] No unrelated formatting changes mixed in with logic changes

**Security**
- [ ] No secrets (API keys, passwords, tokens) in staged files
- [ ] No `.env`, `credentials.json`, or similar files staged

**Consistency**
- [ ] New code follows existing patterns in the same file/module
- [ ] Naming conventions match the codebase (check neighboring code)
- [ ] No inconsistency between what the code does and what comments/docstrings say

If any check fails, fix it before proceeding. Report what you fixed.

### 2. Run Level 1 checks

Run the acceptance criteria from the current story's PRD entry. At minimum:
- `uv run ruff check .` (lint)
- Any unit tests relevant to changed files

If checks fail, fix and re-review (go back to step 1).

### 3. Update progress.txt

Append a progress entry for the story (see CLAUDE.md for format). Include:
- What was implemented
- Files changed
- Learnings for future iterations

Review if any learnings should be promoted to **Codebase Patterns** at the top.

### 4. Update PRD

Set `passes: true` for the completed story in `prd.json`.

### 5. Check for submodule changes

If any files under `submodules/cua/` were modified:
1. `cd submodules/cua && git add -A && git commit -m "feat: [Story ID] - [description]"`
2. `git push` (pushes to fork, not upstream)
3. `cd` back to project root

**This must happen before the parent repo commit**, otherwise the parent will reference a submodule commit that doesn't exist on the remote.

### 6. Update architecture.md (if needed)

If the story added/removed components, changed data flow, or added config — update `architecture.md` before committing. Skip for internal-only refactors.

### 7. Commit and push

```bash
git add -A
git commit -m "feat: [Story ID] - [Story Title]"
git push
```

### 8. Final verification

Run `git status` and `git log --oneline -3` to confirm the commit landed cleanly.

---

## Important

- Do NOT skip the self-review. It catches most bugs that slip past automated checks.
- If you find issues during review, fix them — don't just note them and commit anyway.
- If Level 1 checks fail, do not commit. Fix first.
- Always push submodule before parent repo.
