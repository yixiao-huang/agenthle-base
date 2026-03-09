---
name: prd
description: "Create or update prd.json for the AgentHLE autonomous agent system. Use when planning a feature, adding stories, or converting a PRD to JSON. Triggers on: create a prd, write prd for, plan this feature, requirements for, spec out, convert this prd, agenthle json, add story."
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

**MANDATORY**: Read `docs/testing-feedback-loops.md` before writing acceptance criteria. Structure criteria using the three-level model:

### Level 1 — Mechanical (required for ALL stories)
Automated checks that verify the code runs without errors.

```
"Level 1: Lint passes (uv run ruff check .)"
"Level 1: Unit tests pass (uv run pytest tests/test_*.py)"
"Level 1: Smoke test run_magic_tower.sh --max-steps 5 doesn't crash"
```

The smoke test requires a remote VM. **If you cannot run it**, you MUST explain why and ask the user to decide the next step — do NOT silently skip it or declare it impractical on your own.

### Level 2 — Behavioral (required for agent/tool stories)
After a real run (step count at the implementing agent's discretion), verify the agent actually uses the feature.

```
"Level 2: Trajectory logs show agent invoked [tool] at least once"
"Level 2: Memory files contain task-relevant content (not just step counters)"
"Level 2: Agent reasoning references retrieved content after tool calls"
```

Include practical verification commands where possible:
```
"grep -r '\"memory_search\"' trajectories/"
```

### Level 3 — Outcome (only for cross-session stories)
Multi-session runs show knowledge transfer. Only required when the story's value proposition is cross-session improvement.

```
"Level 3: Session 2's TASK_MEMORY.md contains compacted learnings from session 1"
"Level 3: Agent in session 2 does not repeat session 1's identified dead ends"
```

### Anti-patterns to avoid in criteria:
- "Works correctly" (vague)
- "Agent performs well" (unmeasurable)
- "Handles edge cases" (which ones?)
- Treating "doesn't crash" as sufficient for tool/agent stories

### Always include:
- `"Level 1: Lint passes (uv run ruff check .)"` in every story
- `"Level 1: Unit tests pass"` for stories with testable logic
- `"Level 1: Smoke test run_magic_tower.sh --max-steps 5 doesn't crash"` in every story

---

## Context Field

Each story should include a `context` object to help the implementing agent:

- **existingFiles**: Files to read before starting, with brief description of what they contain
- **depends**: Which stories must be done first and why
- **designDoc**: Relevant design docs with section references
- **pattern**: Existing code patterns to follow (e.g., "Follow MemorySearchTool pattern in same file")
- **reference**: Golden reference — a mature, working implementation of similar functionality that sets the quality bar. Can be code in the codebase, an upstream module, or a design doc section. The implementing agent should read it to understand expected behavior and edge cases. The `/judge` skill uses it to critique acceptance criteria and compare implementations.

**Golden references** are the single most useful piece of context you can give to both the implementer and the evaluator. A good reference answers "what does good look like?" without being a rigid spec.

Examples:
- `"memory/tools.py:MemorySearchTool (same file, follow this pattern for new tools)"`
- `"docs/memory-system.md § OpenClaw Memory System (reference design for TinyClaw)"`
- `"submodules/cua/.../base.py:BaseTool (upstream pattern for all tool classes)"`
- `"tests/test_memory_store.py (test structure and coverage level to match)"`

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

The PRD reader is an AI agent working autonomously. Therefore:

- Be explicit and unambiguous
- Reference specific files and functions (e.g., "extends `BaseTool` in `agent/tools/base.py`")
- Include enough detail to understand purpose and core logic
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
