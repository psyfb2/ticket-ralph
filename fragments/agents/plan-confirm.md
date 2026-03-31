---
name: tr-plan-confirm
description: Presents an implementation plan and risk classification to the user for confirmation
---

## Your Task

Present the implementation plan to the user for confirmation. This agent is invoked only when:
- The risk level is `high`, OR
- `$TR_ALWAYS_CONFIRM` is set to `true`

### Process

#### 1. Gather Context

- Read the plan from `$TR_TMP_DIR/plan.md`
- Read the risk level from `$TR_TMP_DIR/risk-level.txt`
- Read the Jira task for requirements context

#### 2. Present to User

Display:

1. **Risk classification**: `low` / `medium` / `high` — with a brief explanation of why
2. **Task summary**: What this task does
3. **Implementation plan**: The full plan from `plan.md`
4. **Test strategy**: How the implementation will be verified

Ask: "This task is classified as [RISK]. Does this plan look good? Provide feedback or confirm to proceed."

#### 3. Handle Response

**If the user confirms**: Exit successfully.

**If the user provides feedback**:
- Apply the requested changes to `$TR_TMP_DIR/plan.md`
- Update risk classification if feedback changes the scope
- Re-present the updated plan
- Repeat until confirmed

### Rules

- Show the risk level prominently — the user should understand why they're being asked to confirm
- The user's word is final
- After changes, always re-present for another round
