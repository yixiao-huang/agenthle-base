---
name: agenthle
description: "Convert PRDs to prd.json format for the AgentHLE autonomous agent system. Use when you have an existing PRD and need to convert it to AgentHLE's JSON format. Triggers on: convert this prd, turn this into agenthle format, create prd.json from this, agenthle json."
user-invocable: true
---

# AgentHLE PRD Converter

Converts existing PRDs to the prd.json format that AgentHLE uses for autonomous execution.

---

## The Job

Take a PRD (markdown file or text) and convert it to `prd.json` in the project root.

---

## Output Format

```json
{
  "project": "AgentHLE",
  "branchName": "[feature-name-kebab-case]",
  "description": "[Feature description from PRD title/intro]",
  "userStories": [
    {
      "id": "US-001",
      "title": "[Story title]",
      "description": "As a [user], I want [feature] so that [benefit]",
      "acceptanceCriteria": [
        "Criterion 1",
        "Criterion 2",
        "Lint passes (uv run ruff check .)"
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

Each iteration spawns a fresh instance with no memory of previous work. If a story is too big, the LLM runs out of context before finishing and produces broken code.

### Right-sized stories:
- Add a new evaluation mode to `utils/evaluation.py`
- Add a configuration option to `tasks/common_config.py`
- Create a new task definition in `tasks/<category>/<task_name>/main.py`
- Update agent capabilities in the CUA harness
- Add a new shell script for running a task

### Too big (split these):
- "Build the entire evaluation pipeline" — Split into: VLM judge, evaluation context, milestone mode, deliverable mode
- "Add a new agent type" — Split into: agent config, action handling, session management
- "Refactor the task system" — Split into one story per component

**Rule of thumb:** If you cannot describe the change in 2-3 sentences, it is too big.

---

## Story Ordering: Dependencies First

Stories execute in priority order. Earlier stories must not depend on later ones.

**Correct order:**
1. Configuration / data model changes
2. Core logic (evaluation, agent harness)
3. Task definitions that use the core logic
4. Shell scripts and integration

**Wrong order:**
1. Task that uses an evaluation mode (depends on evaluation mode that doesn't exist yet)
2. Evaluation mode implementation

---

## Acceptance Criteria: Must Be Verifiable

Each criterion must be something that Claude can check (e.g., run a command, grep a file, read output), not something vague.

### Good criteria (verifiable):
- "New evaluation mode returns a list[float] score"
- "Shell script runs without errors: `bash run_task.sh`"
- "Task config includes `TASK_TAG` and `TASK_CATEGORY` fields"
- "Lint passes (`uv run ruff check .`)"
- "`uv run python -c 'import module'` succeeds"

### Bad criteria (vague):
- "Works correctly"
- "Agent performs well"
- "Good evaluation results"
- "Handles edge cases"

### Always include as final criterion:
```
"Lint passes (uv run ruff check .)"
```

For stories with testable logic, also include:
```
"Tests pass (uv run pytest)"
```

---

## Conversion Rules

1. **Each user story becomes one JSON entry**
2. **IDs**: Sequential (US-001, US-002, etc.)
3. **Priority**: Based on dependency order, then document order
4. **All stories**: `passes: false` and empty `notes`
5. **branchName**: Derive from feature name, kebab-case
6. **Always add**: "Lint passes (`uv run ruff check .`)" to every story's acceptance criteria

---

## Splitting Large PRDs

If a PRD has big features, split them:

**Original:**
> "Add a new game task with evaluation"

**Split into:**
1. US-001: Add TaskConfig and task description in `tasks/game/<task_name>/main.py`
2. US-002: Implement setup function to initialize remote environment
3. US-003: Add comparison function for VLM-based screenshot evaluation
4. US-004: Implement evaluate function with milestone mode
5. US-005: Create shell script to run the task

Each is one focused change that can be completed and verified independently.

---

## Example

**Input PRD:**
```markdown
# Trajectory Replay Evaluation

Add ability to replay agent trajectories and evaluate at specific checkpoints.

## Requirements
- Load trajectory from JSON files
- Replay actions on remote VM
- Take screenshots at specified action indices
- Compare screenshots with reference images using VLM
```

**Output prd.json:**
```json
{
  "project": "AgentHLE",
  "branchName": "trajectory-replay-eval",
  "description": "Trajectory Replay Evaluation - Replay agent trajectories and evaluate at checkpoints",
  "userStories": [
    {
      "id": "US-001",
      "title": "Load and parse trajectory files",
      "description": "As a developer, I need to load agent trajectory JSON and extract executable actions.",
      "acceptanceCriteria": [
        "Function loads *_agent_response.json files from trajectory directory",
        "Extracts action list excluding screenshot actions",
        "Handles missing or malformed files with clear error messages",
        "Lint passes (uv run ruff check .)"
      ],
      "priority": 1,
      "passes": false,
      "notes": ""
    },
    {
      "id": "US-002",
      "title": "Replay actions and capture screenshots",
      "description": "As a developer, I need to replay actions on the remote VM and take screenshots at specified points.",
      "acceptanceCriteria": [
        "Actions replayed in order via RemoteDesktopSession",
        "Screenshots captured at specified action indices",
        "Screenshots mapped to reference file identifiers",
        "Lint passes (uv run ruff check .)"
      ],
      "priority": 2,
      "passes": false,
      "notes": ""
    },
    {
      "id": "US-003",
      "title": "Compare replay screenshots with references",
      "description": "As a developer, I need to compare captured screenshots against reference images using VLM evaluation.",
      "acceptanceCriteria": [
        "Each screenshot compared with corresponding reference via llm_vision_judge",
        "Scores aggregated and normalized",
        "Results saved to evaluation JSON",
        "Lint passes (uv run ruff check .)"
      ],
      "priority": 3,
      "passes": false,
      "notes": ""
    }
  ]
}
```

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

- [ ] **Previous run archived** (if prd.json exists with different branchName, archive it first)
- [ ] Each story is completable in one iteration (small enough)
- [ ] Stories are ordered by dependency (config → core logic → tasks → scripts)
- [ ] Every story has "Lint passes (`uv run ruff check .`)" as criterion
- [ ] Acceptance criteria are verifiable (not vague)
- [ ] No story depends on a later story
