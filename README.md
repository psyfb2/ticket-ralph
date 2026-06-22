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
| [linear-cli](https://github.com/schpet/linear-cli) | If using Linear | Linear CLI (`brew install schpet/tap/linear`) — required when `TR_SYNC_PROVIDER=linear` (used by agents to read tickets). Authenticate with `linear auth login` or `LINEAR_API_KEY`. File sync itself uses the Linear GraphQL API and only needs `LINEAR_API_KEY`. |
| | | Blocker notifications: osascript on macOS, terminal bell on Linux (works in headless VMs) |

### Claude Code Skills

Agents dynamically detect which platforms the repository uses and invoke the appropriate skills. Install the skills that match your setup:

| Category | Purpose | Example Skills |
|----------|---------|----------------|
| Ticketing platform | Read ticket details and sync attachments | `jira`, `linear` |
| Git hosting | Create and manage pull requests | `bkt` |
| CI/CD pipeline | Monitor pipeline runs and retrieve logs | `azure-devops-cli` |

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TR_TICKETING_PLATFORM` | **Yes** | — | Ticketing platform name injected into agent prompts (e.g. `Jira`, `Linear`). |
| `TR_SYNC_PROVIDER` | No | `noop` | Sync provider for file upload/download. Set to `jira` for Jira attachment sync or `linear` for Linear attachment sync. Unrecognized values use a no-op provider (sync skipped with a warning). |
| `TR_AUTONOMOUS` | No | `true` | Set to `true` to run agents with `--dangerously-skip-permissions`. Overrides both `TR_PERMISSION_MODE` and  `TR_TASK_PERMISSION_MODE`. |
| `TR_PERMISSION_MODE` | No | `acceptEdits` | Permission mode for interactive agents |
| `TR_TASK_PERMISSION_MODE` | No | `acceptEdits` | Permission mode for task agents |
| `TR_REVIEWER_LONG_CONTEXT` | No | `false` | Compose-time toggle. Set to `true` to emit the `[1m]` suffix on the four Sonnet reviewer agents (`tr-code-review`, `tr-plan-review`, `tr-high-level-plan-review`, `tr-qa-ci-cd`). Default produces the 200K-context variant, which avoids requiring Claude Code "extra usage" on Pro/Max plans. Read by `make compose` / `make tr-install`; takes effect after re-composing agents. |
| `JIRA_BASE_URL` | For Jira sync | — | Jira instance URL. Auto-read from jira-cli config if not set. |
| `JIRA_USER` | For Jira sync | — | Jira user email. Auto-read from jira-cli config if not set. |
| `JIRA_API_TOKEN` | For Jira sync | — | Jira API token. Auto-read from jira-cli config if not set. |
| `LINEAR_API_KEY` | For Linear sync | — | Linear personal API key used by the GraphQL sync layer (upload/download attachments). |
| `LINEAR_API_URL` | No | `https://api.linear.app/graphql` | Linear GraphQL endpoint. Override only for self-hosted/proxied setups. |
