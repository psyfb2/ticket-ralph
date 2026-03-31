## Progress Tracking

`progress.txt` is a living document attached to the Jira story. It serves as a cross-task communication channel — information written here by one task's agents is available to all subsequent tasks.

### What to Record

- **Codebase patterns**: Naming conventions, architectural patterns, common gotchas discovered during implementation
- **Task outcomes**: What was accomplished, any deviations from the plan
- **Blockers or risks**: Issues that may affect downstream tasks
- **Technical decisions**: Key decisions made during implementation and their rationale

### Format

```
## Task: <TASK_ID> - <Task Title>
### Patterns & Gotchas
- <pattern or gotcha>

### Outcome
- <what was done>

### Notes for Subsequent Tasks
- <anything the next task should know>
```

### Rules

- **Append** to the file — never overwrite previous entries
- Keep entries concise — this is a communication tool, not documentation
- Focus on information that won't be obvious from reading the code or git history
- Read this file at the start of your work to benefit from prior learnings
