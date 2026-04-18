# Ticket-Ralph

Orchestrated multi-agent workflow built on Claude Code for ticket-driven software development.

## Prerequisites

### CLI Tools

| Tool | Required | Description |
|------|----------|-------------|
| [claude](https://docs.anthropic.com/en/docs/claude-code) | Yes | Claude Code CLI — the runtime for all agents |
| [git](https://git-scm.com/) | Yes | Version control |
| [uv](https://docs.astral.sh/uv/) | Yes | Python package manager — used for dependency management and running ticket-ralph |
| [jira-cli](https://github.com/ankitpokhrel/jira-cli) | If using Jira | Jira CLI — required when `TR_SYNC_PROVIDER=jira` |
| [terminal-notifier](https://github.com/julienXX/terminal-notifier) | No | macOS notifications for blocker alerts in autonomous mode |

### Claude Code Skills

Agents dynamically detect which platforms the repository uses and invoke the appropriate skills. Install the skills that match your setup:

| Category | Purpose | Example Skills |
|----------|---------|----------------|
| Ticketing platform | Read ticket details and sync attachments | `jira` |
| Git hosting | Create and manage pull requests | `bkt` |
| CI/CD pipeline | Monitor pipeline runs and retrieve logs | `azure-devops-cli` |

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TR_TICKETING_PLATFORM` | **Yes** | — | Ticketing platform name injected into agent prompts (e.g. `Jira`, `Linear`). |
| `TR_SYNC_PROVIDER` | No | `noop` | Sync provider for file upload/download. Set to `jira` to enable Jira attachment sync. Unrecognized values use a no-op provider (sync skipped with a warning). |
| `TR_AUTONOMOUS` | No | `true` | Set to `true` to run agents with `--dangerously-skip-permissions`. Overrides both `TR_PERMISSION_MODE` and  `TR_TASK_PERMISSION_MODE`. |
| `TR_PERMISSION_MODE` | No | `acceptEdits` | Permission mode for interactive agents |
| `TR_TASK_PERMISSION_MODE` | No | `acceptEdits` | Permission mode for task agents |
| `JIRA_BASE_URL` | For Jira sync | — | Jira instance URL. Auto-read from jira-cli config if not set. |
| `JIRA_USER` | For Jira sync | — | Jira user email. Auto-read from jira-cli config if not set. |
| `JIRA_API_TOKEN` | For Jira sync | — | Jira API token. Auto-read from jira-cli config if not set. |
