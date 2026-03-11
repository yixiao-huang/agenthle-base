---
name: onboard
description: "Session startup for the AgentHLE agent harness. Builds layered context per CLAUDE.md's progressive exposure layers, syncs repo, identifies the current story, and enters planning mode. Use at the beginning of every new conversation."
user-invocable: true
---

# Codebase Onboarding

Build context and identify work for the current session. Follows the **progressive exposure** layers defined in CLAUDE.md — load only what the current story requires.

---

## Steps

Execute all reads in parallel where possible.

### 1. Read Layer 0 files (parallel)

Read all files listed under **Layer 0** in CLAUDE.md's "Key Files (Progressive Exposure)" section. For `progress.txt`, start with the Codebase Patterns section at the top, then skim recent story entries.

### 2. Sync repo

Pull latest changes for both the base repo and submodule:

```bash
git pull private openclaw-harness
cd submodules/cua && git pull fork openclaw-cua && cd ../..
```

If this fails (submodule not initialized, missing remotes, etc.), run `/first-onboard` for full setup.

### 3. Check git state

- Run `git branch --show-current` to confirm which branch you're on
- Run `git log --oneline -10` for recent commit history
- Run `git status` to see uncommitted changes
- If the PRD exists, verify you're on the correct `branchName` from the PRD. If not, check it out or create it from main.

### 4. Identify current work

From the PRD, find all stories where `passes: false`. Do NOT simply select the next one in the list. Instead, determine which story to implement first by carefully considering:
- **Dependencies**: Which stories are blocked vs. ready to start? Check each story's `context.depends` field and verify prerequisite stories have `passes: true`.
- **Priority**: Among unblocked stories, prefer higher priority (lower number).
- **Critical path**: Which story unblocks the most downstream work?

Summarize the chosen story:
- **Current story**: ID, title, and brief description
- **Key files**: From the story's `context.existingFiles`
- **Dependencies**: Any prerequisite stories and their status
- **Acceptance criteria**: What needs to pass

### 5. Read Layer 1 and Layer 2 (based on story)

Now that you know the story, consult CLAUDE.md's **Layer 1** and **Layer 2** tables. Read only what's relevant:
- **Layer 1**: Reference docs matching the story's domain (context pipeline, specific OpenClaw concept, etc.)
- **Layer 2**: Source code the story will modify or reproduce. Read the OpenClaw source first (target behavior), then the corresponding AgentHLE/CUA file (current state).

**Rule**: Don't read CUA internals unless the story requires changing how we interact with the framework.

### 6. Write story lock

Write the chosen story ID to `.current-story` in the project root.

- If `.current-story` is empty or matches the chosen story, write the story ID.
- If `.current-story` contains a **different** story ID, warn the user and ask before overwriting.

### 7. Report to user

```
## Onboarding Summary

**Branch**: [current branch]
**Current story**: [ID] - [title]
**Status**: [what's done / what's next]

### Key context
- [2-3 bullet points of critical codebase patterns from progress.txt]

### Reference files loaded
- [List which Layer 1/2 files you read and why]

### Next steps
- [What to work on, based on PRD priority]
```

### 8. Enter planning mode

After reporting, enter planning mode to draft the plan for the current story.

**Critical**: When planning a feature, your plan MUST include an **OpenClaw Design Rationale** section explaining:
- **What OpenClaw Does** — Describe the component/feature OpenClaw implements (reference `openclaw/src/`)
- **What We Keep and Why** — Which OpenClaw patterns/design decisions apply to CUA, and justify each
- **What We Drop and Why** — Which patterns don't fit CUA (due to architecture differences), with clear reasoning
- **Key Differences from OpenClaw** — Highlight CUA-specific constraints or capabilities that shape our design

See `docs/plan/US-OC-001-system-prompt-builder.md` for an example of a well-structured design rationale.

**Plan file location**: Save the plan as `docs/plan/<STORY-ID>-<slug>.md` (e.g., `docs/plan/US-OC-003-context-manager.md`). All plan files live in `docs/plan/`.

**After planning**: Use `/prd` to register the plan file path in the story's `context.planFile` field so future agents can find and reference it.

---

## Important Notes

- Do NOT start implementing anything — just build context and report
- **Progressive exposure**: Resist the urge to read everything. Each layer adds context cost. Only go deeper when the story justifies it.
- If `architecture.md` doesn't exist, flag this to the user
- If `prd.json` doesn't exist, let the user know they can use `/prd` to create one
- If all stories in the PRD pass, report that the feature is complete
- **Design rationale is non-negotiable**: Every plan reproducing an OpenClaw component must justify design choices explicitly
