---
name: prd
description: "Generate a Product Requirements Document (PRD) for an AgentHLE feature. Use when planning a feature, starting a new task, or when asked to create a PRD. Triggers on: create a prd, write prd for, plan this feature, requirements for, spec out."
user-invocable: true
---

# PRD Generator

Create detailed Product Requirements Documents that are clear, actionable, and suitable for implementation in the AgentHLE agent harness.

---

## The Job

1. Receive a feature description from the user
2. Ask 3-5 essential clarifying questions (with lettered options)
3. Generate a structured PRD based on answers
4. Save to `tasks/prd-[feature-name].md`

**Important:** Do NOT start implementing. Just create the PRD.

---

## Step 1: Clarifying Questions

Ask only critical questions where the initial prompt is ambiguous. Focus on:

- **Problem/Goal:** What problem does this solve for the agent harness?
- **Core Functionality:** What are the key actions or capabilities?
- **Scope/Boundaries:** What should it NOT do?
- **Success Criteria:** How do we know it's done?

### Format Questions Like This:

```
1. What is the primary goal of this feature?
   A. Improve agent evaluation accuracy
   B. Add new agent capabilities
   C. Improve task setup/configuration
   D. Other: [please specify]

2. What component does this affect?
   A. Agent harness (CUA framework integration)
   B. Evaluation system (utils/evaluation.py)
   C. Task definitions (tasks/)
   D. Infrastructure (shell scripts, config)

3. What is the scope?
   A. Minimal viable version
   B. Full-featured implementation
   C. Just the core logic
   D. Core logic + integration with existing tasks
```

This lets users respond with "1A, 2C, 3B" for quick iteration. Remember to indent the options.

---

## Step 2: PRD Structure

Generate the PRD with these sections:

### 1. Introduction/Overview
Brief description of the feature and the problem it solves in the context of agent evaluation.

### 2. Goals
Specific, measurable objectives (bullet list).

### 3. User Stories
Each story needs:
- **Title:** Short descriptive name
- **Description:** "As a [user], I want [feature] so that [benefit]"
- **Acceptance Criteria:** Verifiable checklist of what "done" means

Each story should be small enough to implement in one focused session (one context window).

**Format:**
```markdown
### US-001: [Title]
**Description:** As a [user], I want [feature] so that [benefit].

**Acceptance Criteria:**
- [ ] Specific verifiable criterion
- [ ] Another criterion
- [ ] Lint passes (uv run ruff check .)
```

**Important:**
- Acceptance criteria must be something Claude can check (e.g., run a command, grep a file, read output), not something vague. "Works correctly" is bad. "grep -c 'def evaluate' utils/evaluation.py returns at least 1" is good.

### 4. Functional Requirements
Numbered list of specific functionalities:
- "FR-1: The system must allow agents to..."
- "FR-2: When evaluation runs, the system must..."

Be explicit and unambiguous.

### 5. Non-Goals (Out of Scope)
What this feature will NOT include. Critical for managing scope.

### 6. Technical Considerations (Optional)
- Known constraints or dependencies on CUA framework
- Integration points with existing evaluation or task systems
- Remote VM requirements
- Environment variable dependencies

### 7. Success Metrics
How will success be measured?
- "Agent successfully completes helloworld task end-to-end"
- "Evaluation scores match expected reference within tolerance"

### 8. Open Questions
Remaining questions or areas needing clarification.

---

## Writing for Implementation

The PRD reader may be an AI agent working autonomously. Therefore:

- Be explicit and unambiguous
- Reference specific files and functions when relevant (e.g., "extends `GeneralTaskConfig` in `tasks/common_config.py`")
- Provide enough detail to understand purpose and core logic
- Number requirements for easy reference
- Use concrete examples from the AgentHLE codebase where helpful

---

## Output

- **Format:** Markdown (`.md`)
- **Location:** `tasks/`
- **Filename:** `prd-[feature-name].md` (kebab-case)

---

## Example PRD

```markdown
# PRD: Milestone Evaluation Enhancement

## Introduction

Enhance the milestone evaluation mode to support weighted scoring per milestone and configurable VLM prompts. Currently all milestones are weighted equally, but some tasks have milestones of varying difficulty that should contribute differently to the final score.

## Goals

- Allow per-milestone weight configuration in task metadata
- Support custom VLM prompts per milestone instead of a single comparison prompt
- Maintain backward compatibility with existing tasks that use uniform weights

## User Stories

### US-001: Add weight configuration to milestone evaluation
**Description:** As a task author, I want to assign different weights to milestones so that harder milestones contribute more to the score.

**Acceptance Criteria:**
- [ ] `evaluate_milestone_mode` accepts optional `weights` dict mapping filename to weight
- [ ] Weights default to uniform (1/N) when not provided
- [ ] Existing tasks continue to work without changes
- [ ] Lint passes (uv run ruff check .)

### US-002: Support custom VLM prompts per milestone
**Description:** As a task author, I want to use different comparison prompts for different milestones so that evaluation is more accurate.

**Acceptance Criteria:**
- [ ] `comparison_fn` can receive milestone-specific context from task metadata
- [ ] TaskConfig can define per-milestone prompt overrides
- [ ] Default prompt used when no override specified
- [ ] Lint passes (uv run ruff check .)

## Functional Requirements

- FR-1: `evaluate_milestone_mode` must accept an optional `weights` parameter
- FR-2: Weights must be normalized so they sum to 1.0
- FR-3: Task metadata `to_metadata()` must support a `milestone_weights` field
- FR-4: Custom prompts passed via `comparison_fn` kwargs

## Non-Goals

- No changes to the deliverable evaluation mode
- No automatic weight inference from task difficulty
- No UI for configuring weights

## Technical Considerations

- Changes primarily in `utils/evaluation.py` and `tasks/common_config.py`
- Must maintain backward compatibility with `tasks/game/mota_24_easy/main.py` and `tasks/helloworld/main.py`
- VLM judge calls go through `llm_vision_judge` which uses OPENAI_API_KEY

## Success Metrics

- Existing tasks pass evaluation with unchanged scores
- New weighted tasks produce scores reflecting milestone importance

## Open Questions

- Should weights be specified as absolute values or relative ratios?
- Should we validate that weight keys match actual reference filenames?
```

---

## Checklist

Before saving the PRD:

- [ ] Asked clarifying questions with lettered options
- [ ] Incorporated user's answers
- [ ] User stories are small and specific (completable in one context window)
- [ ] Functional requirements are numbered and unambiguous
- [ ] Non-goals section defines clear boundaries
- [ ] References specific AgentHLE files/functions where relevant
- [ ] Saved to `tasks/prd-[feature-name].md`
