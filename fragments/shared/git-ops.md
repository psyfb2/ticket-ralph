## Git Operations

### Branching Strategy

- **Story branch**: `<STORY_ID>-<short-summary>` (e.g., `PROJ-40015-add-settings-page`) — branched from the default branch (main/master). The Jira story ID **must** be the branch name prefix.
- **Task branch**: `<TASK_ID>-<short-summary>` (e.g., `PROJ-40016-add-api-endpoint`) — branched from the story branch. The Jira task ID **must** be the branch name prefix.

The short summary is a lowercase kebab-case slug (3-5 words max) derived from the Jira ticket title.

All task branches branch off the story branch. When a task is complete, its PR targets the story branch. When all tasks for a story are done, the story branch is merged to the default branch.

### Link created branches to Jira

Link branches to their Jira tickets using `jira issue link`

### Branch Name Files

Agents write branch names to files so downstream agents can reference them:
- `$TR_TMP_DIR/branch-story.txt` — the story branch name
- `$TR_TMP_DIR/branch-task.txt` — the current task branch name
