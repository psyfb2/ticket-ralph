---
name: tr-high-level-plan-confirm
description: Presents the high-level plan and Jira tasks to the user for confirmation
---

## Your Task

Present the high-level plan to the user for confirmation and handle their feedback.

### Process

#### 1. Gather Context

- Read the high-level plan from `$TR_TMP_DIR/high-level-plan.md`
- Use the Jira skill to read the story and list all sub-tasks with their dependencies
- Read the original story requirements for reference

#### 2. Present to User

Display to the user in a clear format:

1. **Story summary** — what the story is about
2. **High-level plan** — the architectural approach
3. **Jira tasks** — list all tasks with titles, dependencies, and which repo each touches
4. **Risks & assumptions** — anything flagged during planning

Ask the user: "Does this plan look good? Provide feedback or confirm to proceed."

#### 3. Handle Response

**If the user confirms**: Exit successfully.

**If the user provides feedback**:
- Parse the feedback into concrete changes needed
- Update the high-level plan in `$TR_TMP_DIR/high-level-plan.md`
- Update Jira tasks if needed (add, remove, modify, change dependencies)
- Re-present the updated plan to the user
- Repeat until the user confirms

### Rules

- Always present the FULL plan — don't summarize or truncate
- Show task dependencies clearly (e.g., "Task 3 is blocked by Task 1 and Task 2")
- The user's word is final — if they want changes, make them regardless of your opinion
- After making changes, always re-present for another confirmation round
