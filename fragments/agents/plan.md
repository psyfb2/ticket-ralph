---
name: tr-plan
description: Picks the next Jira task for a story and creates a detailed implementation plan with risk classification
---

## Your Task

Pick the next most important Jira task for story `$TR_STORY_ID` and create a detailed implementation plan.

### Process

#### 1. Read Context

- Read `$TR_TMP_DIR/progress.txt` for learnings from previous tasks
- Read `$TR_TMP_DIR/high-level-plan.md` for the overall architectural approach
- Use the Jira skill to list all sub-tasks of `$TR_STORY_ID` — read **titles and statuses only** (do not read descriptions to avoid overloading context)

#### 2. Pick the Next Task

Select the next task based on:
- Status must be `TO DO`
- All blocking tasks (dependencies) must be `DONE` (not just `IN REVIEW` — a human must merge it first)
- If multiple tasks are eligible, pick the most important one (critical path first)

If no tasks are eligible (all blocked or none in TO DO), report this and exit.

Write the selected task ID to `$TR_TMP_DIR/task-id.txt`.

#### 3. Understand the Task

Now read the full task description from Jira (title + description).

#### 4. Explore the Codebase

Follow the planning methodology to explore the codebase:
- Understand the current architecture in the area the task touches
- Identify files that will need changes
- Note existing patterns and conventions
- Check for prior art

#### 5. Create the Plan

Write `$TR_TMP_DIR/plan.md`:

```markdown
# Plan: <TASK_ID> - <Task Title>

## Context
<What this task does and why, in the context of the story>

## Critical Files
<3-5 files central to this implementation, with brief notes on why>

## Implementation Steps
1. <Step 1 — concrete, actionable, testable>
2. <Step 2>
...

## Test Strategy
<How each step will be tested — unit tests, integration tests, etc.>

## Risks
<Anything that could go wrong>
```

The plan must be **detailed enough to implement deterministically** — a competent engineer should be able to follow it without making judgment calls.

#### 6. Classify Risk

Evaluate the task and classify it as:
- **low**: Simple, isolated change. Low blast radius. Well-understood pattern.
- **medium**: Moderate complexity. Touches multiple files or has integration points. Some edge cases.
- **high**: Complex. Touches critical paths, shared infrastructure, or has high blast radius. Novel patterns or significant architectural changes.

Write the risk level to `$TR_TMP_DIR/risk-level.txt` (just the word: `low`, `medium`, or `high`).

#### 7. Create Task Branch

- Read the story branch name from `$TR_TMP_DIR/branch-story.txt`
- Derive a short kebab-case slug (3-5 words) from the Jira task title (e.g., "Add API Endpoint" → `add-api-endpoint`)
- Create branch `$TR_TASK_ID-<slug>` from the story branch — e.g., `PROJ-40016-add-api-endpoint`
- Link the branch to the Jira task
- Write the task branch name to `$TR_TMP_DIR/branch-task.txt`

#### 8. Move Task to In Progress

Transition the Jira task from `TO DO` to `IN PROGRESS`.

#### 9. Update Progress

If this task reveals anything useful for subsequent tasks, append to `$TR_TMP_DIR/progress.txt`.
