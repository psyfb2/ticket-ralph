---
name: tr-high-level-plan
description: Creates a high-level architectural plan for a Jira story and breaks it into Jira tasks with dependencies
---

## Your Task

Create a high-level architectural plan for Jira story `$TR_STORY_ID` and break it into discrete Jira tasks.

### Process

#### 1. Understand the Story

- Use the Jira skill to read the full story: description, acceptance criteria, comments, attachments
- If `$TR_USER_INPUT` is set, incorporate the additional context provided by the user
- Identify all explicit and implicit requirements
- **Push back on ambiguity** — if the story is unclear, add a comment on the Jira story listing questions before proceeding. If the ambiguity is minor, document your assumption.

#### 2. Feasibility Assessment

- Explore the codebase to understand the current architecture (read-only — do not modify files)
- Identify which repos, services, and modules are affected
- Assess feasibility — are there any blockers, missing infrastructure, or unrealistic requirements?
- If something is infeasible, document why and suggest alternatives

#### 3. Create the High-Level Plan

Write `$TR_TMP_DIR/high-level-plan.md` with:

```markdown
# High-Level Plan: <STORY_ID>

## Story Summary
<1-2 sentence summary of the story>

## Requirements
<Numbered list of all requirements extracted from the story>

## Architecture & Approach
<High-level description of the approach — which services/modules change and why>
<Key architectural decisions and their rationale>

## Tasks
<Numbered list of tasks — title, brief description, which repo, estimated complexity>
<Dependencies between tasks noted>

## Risks & Assumptions
<List of risks, assumptions, and open questions>
```

Keep it **high-level** — this is an architectural plan, not implementation details. Each task description should be 1-3 sentences.

#### 4. Create Jira Tasks

For each task in the plan:
- Create a Jira sub-task under the story
- Title should be clear and self-contained
- Description should reference the relevant section of the high-level plan
- Set dependencies between tasks (which tasks block which) using Jira issue links
- Each task must be a small, self-contained piece of work that touches only ONE repo

#### 5. Create Story Branch

- Derive a short kebab-case slug (3-5 words) from the Jira story title (e.g., "Create Test Set" → `create-test-set`)
- Create branch `$TR_STORY_ID-<slug>` from the default branch (main/master) — e.g., `PROJ-40015-create-test-set`
- Link the branch to the Jira story
- Read-merge-write `storyBranch` into `$TR_TMP_DIR/ticket-ralph-state.json`

#### 6. Initialize Progress Tracking

Create `$TR_TMP_DIR/progress.txt` with:

```
# Progress: <STORY_ID>
## Story: <Story Title>
Created: <date>
```

### Quality Gates

- Every requirement in the story is addressed by at least one task
- No task touches more than one repo
- Task dependencies form a valid DAG (no cycles)
- The plan is high-level — no implementation details, no code snippets
- SOLID principles are respected in the architectural approach
