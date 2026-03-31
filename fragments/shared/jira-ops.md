## Jira Operations

Use the **Jira skill** for all Jira interactions. Common operations:

- **Read story/task**: Retrieve full details including description, acceptance criteria, and attachments
- **Update status**: Move tickets between columns (TO DO -> IN PROGRESS -> IN REVIEW -> IN QA -> DONE)
- **Add attachments**: Upload files (plans, reports) to Jira tickets
- **Create tasks**: Create sub-tasks linked to the parent story, with dependencies between them
- **Add comments**: Document decisions, status updates, or blockers
- **Link branches**: Associate git branches with Jira tickets

### Jira Column Flow

```
TO DO -> IN PROGRESS -> IN REVIEW -> IN QA -> DONE
```

- A task moves to IN PROGRESS when work begins
- A task moves to IN REVIEW when a PR is created
- A task moves to IN QA when review is complete
- A task moves to DONE when merged
