---
name: onboard
description: "Familiarize yourself with the AgentHLE codebase at the start of a new session. Reads CLAUDE.md, architecture, progress, PRD, and key files to build context. Use at the beginning of every new conversation."
user-invocable: true
---

# Codebase Onboarding

Quickly build context on the AgentHLE codebase so you can start working effectively. This skill executes the "Before you start" checklist from CLAUDE.md.

---

## Steps

Execute all reads in parallel where possible.

### 1. Read core project files (parallel)

Read ALL of these files to understand the project and current state:

- `CLAUDE.md` — project instructions, workflow rules, quality requirements, and git conventions. **This is the most important file — it governs how you work in this repo.**
- `architecture.md` — system architecture, directory structure, data flow
- `progress.txt` — **start with the Codebase Patterns section at the top**, then skim recent story entries for context on what's been done
- `prd.json` — current PRD with user stories, priorities, and acceptance criteria

Also read these if relevant to the current work area:
- `docs/memory-system.md` — memory system design (for memory features)
- `docs/cua-context-management.md` — how CUA agent context works (for agent/context work)
- `docs/openclaw-context-flow.md` — OpenClaw reference: system prompt, compaction prompts, memory recall, tool loop (for memory/compaction/recall stories)

### 2. Check git state

- Run `git branch --show-current` to confirm which branch you're on
- Run `git log --oneline -10` for recent commit history
- If the PRD exists, verify you're on the correct `branchName` from the PRD. If not, check it out or create it from main.

### 3. Identify current work

From the PRD, find all stories where `passes: false`. Do NOT simply select the next one in the list. Instead, determine which story to implement first by carefully considering:
- **Dependencies**: Which stories are blocked vs. ready to start? Check each story's `context.depends` field and verify prerequisite stories have `passes: true`.
- **Priority**: Among unblocked stories, prefer higher priority (lower number).
- **Critical path**: Which story unblocks the most downstream work?

Summarize the chosen story:
- **Current story**: ID, title, and brief description
- **Key files**: From the story's `context.existingFiles`
- **Dependencies**: Any prerequisite stories and their status
- **Acceptance criteria**: What needs to pass

### 4. Report to user

Present a concise summary:

```
## Onboarding Summary

**Branch**: [current branch]
**Current story**: [ID] - [title]
**Status**: [what's done / what's next]

### Key context
- [2-3 bullet points of critical codebase patterns from progress.txt]

### Next steps
- [What to work on, based on PRD priority]
```

### 5. Enter planning mode

After reporting, enter planning mode to draft the plan for the current story.

---

## Important Notes

- Do NOT start implementing anything — just build context and report
- If `architecture.md` doesn't exist, flag this to the user
- If `prd.json` doesn't exist, let the user know they can use `/prd` to create one
- If all stories in the PRD pass, report that the feature is complete
