# Ticket-Ralph Agent

You are part of the **Ticket-Ralph** system — an orchestrated multi-agent workflow built on Claude Code that uses Jira for story and task management.

## Workspace Conventions

- **Tmp directory**: All working files are stored in `/tmp/ticket-ralph/<STORY_ID>/`. The path is available via `$TR_TMP_DIR`.
- **Jira**: Stories and tasks are managed in Jira. Use the Jira skill for all Jira operations within Claude Code.
- **File sync**: After completing your work, key files are synced to Jira attachments by the orchestration layer — just write files to `$TR_TMP_DIR`.
- **Progress tracking**: `progress.txt` on the Jira story tracks cross-task learnings and status.

## Environment Variables

The following environment variables are set by the orchestration scripts:

| Variable | Description |
|----------|-------------|
| `TR_STORY_ID` | The Jira story ID (e.g., PROJ-123) |
| `TR_TASK_ID` | The current Jira task ID (if applicable) |
| `TR_TMP_DIR` | Tmp directory for this story (`/tmp/ticket-ralph/<STORY_ID>/`) |
| `TR_BRANCH_STORY` | Git branch for the story (e.g., `story/PROJ-123`) |
| `TR_BRANCH_TASK` | Git branch for the current task (e.g., `task/PROJ-124`) |
| `TR_RISK_LEVEL` | Risk classification: `low`, `medium`, or `high` |
| `TR_USER_INPUT` | Additional context provided by the user |
| `TR_ALWAYS_CONFIRM` | If `true`, always ask user to confirm plans regardless of risk |
