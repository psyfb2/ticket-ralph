---
name: tr-high-level-plan-confirm
description: Presents the high-level plan and Jira tasks to the user for confirmation
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
