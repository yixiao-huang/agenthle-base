---
name: review-judge
description: "Review the two most recent /judge reports for a story (or overall), diff what changed, and produce a prioritized action plan. Use after /judge has run at least once."
user-invocable: true
context: fork
---

# Judge Review

Read the two most recent `/judge` audit reports (for the target story if specified, or the two most recent overall), compare them, and produce a prioritized action plan for the current session.

Target: $ARGUMENTS (if empty, read `.current-story` — if it contains a story ID, use that to filter reports for that story; if `.current-story` is also empty, reviews the two most recent reports regardless of story).

---

## Steps

### 1. Find judge reports

```bash
ls -t docs/judges/judge_*.md 2>/dev/null
```

- If **0 reports**: stop and tell the user to run `/judge` first.
- If a **story ID** was given as target: first look for reports with the story ID in the filename (e.g., `judge_*_US-MEM-003.md`), then fall back to scanning report contents ("Target" or "PRD Story Audit" section). Use the two most recent that cover it.
- If **no story ID** given: use the two most recent reports.
- If only **1 report** matches: skip the diff section, just triage that report.

### 2. Read the reports and current state

Read the report(s) using the Read tool. Also read in parallel:
- `progress.txt` — to see what's been done since the last report (especially recent story entries)
- `prd.json` — to check current story statuses and dependency chain

### 3. Diff: What changed between reports?

If two reports are available, compare them across every dimension:

**Score changes** (using /judge rubric axes):

| Axis | Previous | Current | Delta |
|------|----------|---------|-------|
| Implementation Progress | [/100] | [/100] | [+/-] |
| Code Quality | [/100] | [/100] | [+/-] |
| Design Soundness | [/100] | [/100] | [+/-] |
| Real-World Behavior | [/100] | [/100] | [+/-] |
| **Overall** | **[/100]** | **[/100]** | **[+/-]** |

**Improvements** — issues from the previous report that have been addressed:
- [What was done, with evidence (stories completed, code fixes, design gaps closed)]

**Regressions** — things that got worse or new issues introduced:
- [New problems the latest judge flagged that weren't in the previous report]

**Still open** — issues flagged in both reports that haven't been addressed:
- [Persistent gaps, ranked by how many consecutive reports have flagged them]

**Resolved vs new ratio**: [X resolved / Y new / Z persistent] — is the project trending in the right direction?

### 4. Triage: Prioritize actions for this session

From the latest judge report's findings and suggestions, produce a ranked action plan considering:

1. **Impact on rubric score** — which actions would move the needle most?
2. **Story dependencies** — what must be done before other things can start? Check `prd.json` dependency chain.
3. **Effort** — prefer quick wins early to build momentum
4. **Persistent issues** — items flagged in both reports get priority bumped
5. **Verification level** — prefer Level 2/3 behavioral fixes over Level 1-only improvements (see `docs/testing-feedback-loops.md`)

Produce a concrete session plan:

```markdown
### Session Action Plan

**Current story**: [ID] - [title] (from PRD, highest priority with passes:false and deps met)

| Priority | Action | Rubric axis | Effort | Files to touch |
|----------|--------|-------------|--------|----------------|
| 1 | [specific action] | [axis] | [~Xm] | [file paths] |
| 2 | ... | ... | ... | ... |

**Quick wins** (< 5 min each, do first):
1. [action — e.g., "fix lint error in store.py:45"]
2. [action]

**Core work** (main session effort):
1. [action with details — what to implement, which acceptance criteria it addresses]
2. [action]

**If time permits**:
1. [stretch goal — usually next story in dependency chain]
```

### 5. Write the review to `docs/review-judges/`

Save as a timestamped file. If a story ID was targeted, include it in the filename:
```
docs/review-judges/review_YYYY-MM-DD_HHMM[_STORYID].md
```

The file must contain the diff (if two reports) and triage from steps 3-4.

After writing, print a summary to the console:
```
Review written to docs/review-judges/review_YYYY-MM-DD_HHMM[_STORYID].md
Score trend: [prev] -> [current] ([+/-] overall)  (or "Single report: [score] overall" if only one)
Top 3 actions: 1) [action] 2) [action] 3) [action]
```

### 6. Enter planning mode

After writing the review, enter planning mode using the EnterPlanMode tool to draft a concrete implementation plan based on the session action plan from Step 4.

In planning mode:
1. Present the prioritized action plan to the user
2. For each action, specify: which files to modify, what changes to make, what commands to run, and expected outcomes
3. Cross-reference with acceptance criteria from the target story in `prd.json`
4. Ask the user to confirm, adjust, or reprioritize before exiting planning mode
5. Only exit planning mode (via ExitPlanMode) once the user approves the plan

---

## Important

- **Only write to `docs/review-judges/`.** Do not modify code, architecture.md, progress.txt, or prd.json.
- **Be concrete about actions.** "Improve memory system" is useless. "Add `init_session()` method to MemoryStore that scans `session-NNN.md` files and returns next session path — addresses US-MEM-TSK-S criterion #2" is useful.
- **Track persistent issues.** If the same issue appears in both reports, explicitly call it out — it's being ignored and needs attention.
- **Be honest about score deltas.** Don't inflate improvements. If the score didn't change, say so.
- **Respect session time.** Don't propose 10 hours of work. Prioritize ruthlessly for what can realistically be done now.
- **Use the right rubric.** Score changes must use the four axes from `/judge`: Implementation Progress, Code Quality, Design Soundness, Real-World Behavior. Do NOT use axes from other projects.
- **Reference story IDs.** Every action should map to a PRD story or acceptance criterion where possible.
