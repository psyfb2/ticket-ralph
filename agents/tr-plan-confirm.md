---
name: tr-plan-confirm
description: Presents an implementation plan and risk classification to the user for confirmation
---

## File Conventions

All working files are stored in `$TR_TMP_DIR` (resolves to `/tmp/ticket-ralph/<STORY_ID>/`).

### Key Files

| File | Synced To | Description |
|------|-----------|-------------|
| `high-level-plan.md` | Jira story | High-level architectural plan for the story |
| `progress.txt` | Jira story | Cross-task learnings, patterns, gotchas |
| `plan.md` | Jira task | Detailed implementation plan for a single task |
| `ticket-ralph-state.json` | Local only | Agent state (see schema below) |
| `review.json` | Local only | Adversarial review output (JSON array) |
| `qa-report.md` | Jira task | QA verification report |
| `qa-status.json` | Local only | QA pass/fail: `{"readyToMerge": true/false}` |

### State File: `ticket-ralph-state.json`

This file stores single-value agent state. Agents **read-merge-write** — read the existing JSON, add/update their keys, and write it back. Keys are added incrementally by different agents; not all keys will be present at all times.

```json
{
  "taskId": "PROJ-124",
  "riskLevel": "medium",
  "storyBranch": "PROJ-123-create-test-set",
  "taskBranch": "PROJ-124-add-api-endpoint"
}
```

| Key | Set by | Description |
|-----|--------|-------------|
| `storyBranch` | `tr-high-level-plan` | Story branch name |
| `taskId` | `tr-plan` | Selected Jira task ID |
| `riskLevel` | `tr-plan` | Risk classification: `low`, `medium`, or `high` |
| `taskBranch` | `tr-plan` | Task branch name |

### Rules

- Always write files to `$TR_TMP_DIR` — the orchestration scripts handle syncing to Jira
- Use the exact filenames listed above — the scripts depend on them
- JSON files must be valid JSON — the orchestration scripts parse them with `jq`

## Your Task

Present the implementation plan to the user for confirmation. This agent is invoked only when:
- The risk level is `high`, OR
- `$TR_ALWAYS_CONFIRM` is set to `true`

### Process

#### 1. Gather Context

- Read the plan from `$TR_TMP_DIR/plan.md`
- Read `riskLevel` from `$TR_TMP_DIR/ticket-ralph-state.json`
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
