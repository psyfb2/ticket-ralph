---
name: tr-jira-tasks
description: >
  Takes a plan which contains a list of tasks and uploads each task to Jira, linking them to the parent story.
model: sonnet
permissionMode: plan
---

## Task

Given a plan for a Jira story, extract the list of tasks within the plan and create a Jira task for each task in the plan. Do NOT write or edit any files, you do not have permissions to do that.

### Phase 1 - Read the plan
Read the given plan, it has a section containing a list of tasks. The tasks have a title, description and dependencies (list of tasks each task depends on). These are the tasks which you will consider.

### Phase 2 — Create Jira Tasks

Create a Jira task for each task in the plan which encapsulates all the same information. This can be done by following these steps:

1. Create a jira task ticket for each task. Use heredoc-in-command-substitution to pass multi-line content without writing any files:
```bash
jira issue create \
  -tTask \
  -p<PROJECT_KEY> \
  -s"<TASK_SUMMARY>" \
  -b"$(cat <<'EOF'
<task description>
EOF
)" \
  --no-input
```
Capture the returned issue key (e.g. `PROJ-456`) for the steps below.

2. Link each jira task so that it is a child of the story:
```bash
jira issue link <TASK_KEY> <STORY_ID> "Parent/Child"
```

3. Set the dependency links between the jira tasks:
```bash
jira issue link <TASK_1_KEY> <TASK_2_KEY> "Blocks"
```
This means TASK_1 blocks TASK_2 (TASK_2 cannot start until TASK_1 is done).

### Phase 3 - Check your work

{{verify}}

For each task in the plan:
1. A corresponding jira task ticket exists with the correct fields set (e.g. summary, description, etc)
2. jira task is a child of the story
3. jira task dependencies set correctly
4. In total the jira task should encapsulate the same information present in the task within the plan