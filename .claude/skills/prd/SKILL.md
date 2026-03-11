---
name: prd
description: "Create or update prd.json for the AgentHLE agent harness — focused on reproducing OpenClaw's agent-side architecture for CUA. Use when planning a feature, adding stories, or converting a PRD to JSON. Triggers on: create a prd, write prd for, plan this feature, requirements for, spec out, convert this prd, agenthle json, add story."
user-invocable: true
---

# PRD Generator

Create `prd.json` — the single file that drives AgentHLE's autonomous implementation pipeline.

---

## The Job

1. Receive a feature description (or existing markdown PRD) from the user
2. If the request is ambiguous, ask 3-5 clarifying questions (with lettered options for quick "1A, 2C" replies)
3. Read `docs/testing-feedback-loops.md` for verification guidelines
4. Generate `prd.json` in the project root

**Important:** Do NOT start implementing. Just create the PRD.

---

## Clarifying Questions (When Needed)

Skip if the user's intent is already clear. Focus on:

- **Problem/Goal:** What problem does this solve?
- **Core Functionality:** What are the key actions or capabilities?
- **Scope/Boundaries:** What should it NOT do?
- **Success Criteria:** How do we know it's done?

Format with lettered options so users can respond quickly ("1A, 2C, 3B").

---

## Output Format

```json
{
  "project": "AgentHLE",
  "branchName": "[feature-name-kebab-case]",
  "description": "[Feature description]",
  "userStories": [
    {
      "id": "US-001",
      "title": "[Story title]",
      "description": "As a [user], I want [feature] so that [benefit]",
      "context": {
        "existingFiles": ["relevant/file.py (what it contains)"],
        "depends": "US-000 must be done first (reason)",
        "designDoc": "docs/relevant-doc.md (section name)",
        "reference": "path/to/reference.py:ClassName (golden reference — what good looks like)"
      },
      "acceptanceCriteria": [
        "Level 1: Lint passes (uv run ruff check .)",
        "Level 1: Unit tests pass (uv run pytest tests/test_*.py)",
        "Level 2: After a real run, trajectory logs show agent invoked the tool",
        "Level 2: Memory files contain task-relevant content (not boilerplate)"
      ],
      "priority": 1,
      "passes": false,
      "notes": ""
    }
  ]
}
```

---

## Story Size: The Number One Rule

**Each story must be completable in ONE iteration (one context window).**

Each iteration spawns a fresh agent with no memory of previous work. If a story is too big, the agent runs out of context before finishing and produces broken code.

**Rule of thumb:** If you cannot describe the change in 2-3 sentences, it is too big.

### Right-sized:
- Add a new tool class following an existing pattern
- Extend a store class with new methods + tests
- Wire tools into the agent and update instructions
- Add a callback that hooks into an existing lifecycle

### Too big (split these):
- "Build the entire memory system" → Split into: store, tools, agent wiring, callback, compaction
- "Add a new agent type" → Split into: config, action handling, session management

---

## Story Ordering: Dependencies First

Stories execute in priority order. Earlier stories must not depend on later ones.

**Correct:** config/data model → core logic → integration → scripts
**Wrong:** integration story before the core logic it depends on

---

## Acceptance Criteria: Three-Level Verification

**MANDATORY**: Read `docs/testing-feedback-loops.md` before writing acceptance criteria. Structure criteria using the three-level model. The primary focus is Level 2+ — real VM runs that prove the feature works end-to-end.

### Level 1 — Mechanical (baseline, every story)
Quick automated checks. Necessary but never sufficient on their own.

```
"Level 1: Lint passes (uv run ruff check .)"
"Level 1: Unit tests pass (uv run pytest tests/test_*.py)"
```

### Level 2 — Behavioral (the real test, required for agent/tool stories)
Run the agent on a real VM for **at least 50 steps** (`run_magic_tower.sh 50`), then verify the feature was actually used and produced meaningful results.

**VM test rule**: VM runs are mandatory, not optional. You MUST run the command and observe output. If the run fails for any reason (connection error, import error, timeout, etc.), show the full error output and ask the user for next steps — do NOT silently skip, declare it impractical, or mark the story as passing.

Check these after the run:
1. **Tool invocation** — trajectory logs show the agent called the feature's tool(s)
2. **Content quality** — memory/output files contain task-relevant observations (not step counters or boilerplate)
3. **Agent reasoning** — the agent's reasoning after tool calls references retrieved content
4. **Nudge/periodic features** — if applicable, check that periodic behaviors fired at expected intervals over 50+ steps

```
"Level 2: run_magic_tower.sh 50 — trajectory logs show agent invoked [tool] at least once"
"Level 2: Memory files contain task-specific observations (e.g., game state, strategies)"
"Level 2: Agent reasoning after [tool] calls references the retrieved content"
```

Include practical verification commands:
```
"grep -r '\"memory_search\"' trycua/cua-bench/mota_24_easy/task_0_agent_logs/trajectories/"
```

### Level 3 — Outcome (cross-session stories only)
Multiple sequential VM runs (each 50+ steps) show knowledge transfer across sessions.

```
"Level 3: Session 2's TASK_MEMORY.md contains compacted learnings from session 1"
"Level 3: Agent in session 2 avoids session 1's identified dead ends"
"Level 3: Floor reached in session 2 >= session 1"
```

### Anti-patterns to avoid in criteria:
- "Works correctly" (vague)
- "Agent performs well" (unmeasurable)
- "Handles edge cases" (which ones?)
- Treating "doesn't crash" or a 5-step smoke test as sufficient for tool/agent stories
- Step counts under 50 for Level 2 — too few steps to observe meaningful agent behavior

### Always include:
- `"Level 1: Lint passes (uv run ruff check .)"` in every story
- `"Level 1: Unit tests pass"` for stories with testable logic
- At least one `"Level 2: run_magic_tower.sh 50 — ..."` criterion for any agent/tool story

---

## Context Field

Each story should include a `context` object to help the implementing agent:

- **existingFiles**: Files to read before starting, with brief description of what they contain
- **depends**: Which stories must be done first and why
- **designDoc**: Relevant design docs with section references (e.g., `openclaw/docs/concepts/memory.md`)
- **pattern**: Existing code patterns to follow (e.g., "Follow MemorySearchTool pattern in same file")
- **reference**: Golden reference — the OpenClaw source file(s) whose behavior this story reproduces, or a mature working implementation of similar functionality. The implementing agent reads it to understand target behavior; `/judge` uses it to critique the implementation. Prefer `openclaw/src/` paths for reproduction stories.

**Golden references** are the single most useful piece of context you can give to both the implementer and the evaluator. A good reference answers "what does good look like?" without being a rigid spec.

### Reference brevity: pointers, not inventories

Each story is implemented by a fresh agent that can explore the codebase on its own. Give **directory pointers with entry points**, not exhaustive file lists. The implementing agent will `Glob`, `Grep`, and `Read` to discover what it needs.

**Good** — concise pointer with a starting point:
- `"openclaw/src/agents/pi-embedded-runner/ (start from run.ts for the main loop; explore compact.ts for compaction)"`
- `"openclaw/src/memory/ (start from manager.ts, explore hybrid.ts for search logic)"`
- `"submodules/cua/libs/python/agent/agent/callbacks/ (explore all built-in callbacks)"`

**Bad** — exhaustive inventory the agent could find itself:
- `"openclaw/src/agents/pi-embedded-runner/run.ts (main loop), compact.ts (compaction), extensions.ts (pruning), history.ts (loading), model.ts (resolution), types.ts (types), tool-result-truncation.ts (truncation), tool-result-context-guard.ts (guard), system-prompt.ts (prompt), thinking.ts (thinking)"`

Apply the same principle to `existingFiles` and `notes` — keep them concise. If a directory has 10+ relevant files, point to the directory and name 1-2 entry points.

Only include fields that are relevant. Omit the entire `context` object for simple stories.

---

## Conversion Rules

1. **Each user story becomes one JSON entry**
2. **IDs**: Use meaningful prefixes (US-MEM-001, US-EVL-001) for feature groups, or sequential US-001 for standalone features
3. **Priority**: Based on dependency order, then document order
4. **All new stories**: `passes: false` and empty `notes`
5. **branchName**: Derive from feature name, kebab-case

---

## Writing for Implementation

The PRD reader is an AI agent working autonomously with a fresh context window. It can explore the codebase on its own. Therefore:

- Be explicit and unambiguous
- Reference specific files and functions (e.g., "extends `BaseTool` in `agent/tools/base.py`")
- Include enough detail to understand purpose and core logic, but **don't over-specify** — give directory pointers and entry points, not exhaustive file lists (see "Reference brevity" above)
- Use `notes` for critical design insights the implementing agent must know
- Use concrete examples from the codebase where helpful

---

## Archiving Previous Runs

**Before writing a new prd.json, check if there is an existing one from a different feature:**

1. Read the current `prd.json` if it exists
2. Check if `branchName` differs from the new feature's branch name
3. If different AND `progress.txt` has content beyond the header:
   - Create archive folder: `archive/YYYY-MM-DD-feature-name/`
   - Copy current `prd.json` and `progress.txt` to archive
   - Reset `progress.txt` with fresh header

---

## Checklist Before Saving

Before writing prd.json, verify:

- [ ] **Read `docs/testing-feedback-loops.md`** for verification guidelines
- [ ] **Previous run archived** (if prd.json exists with different branchName)
- [ ] Each story is completable in one iteration (small enough)
- [ ] Stories are ordered by dependency (no story depends on a later one)
- [ ] Acceptance criteria use three-level verification (Level 1/2/3 as applicable)
- [ ] Every story has "Level 1: Lint passes" as criterion
- [ ] Criteria are verifiable (not vague)
- [ ] `context` fields reference relevant files and design docs
- [ ] Stories with non-trivial logic include a `reference` (golden reference) in `context` — the evaluator will use it to critique criteria
