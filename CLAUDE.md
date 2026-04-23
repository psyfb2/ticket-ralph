# Ticket-Ralph

Orchestrated multi-agent workflow built on Claude Code for ticket-driven software development. Stories and tasks live in a ticketing platform (Jira by default, extensible to Linear, GitHub Issues, etc.); agents plan, implement, and review the work.

## Quick Start

```bash
# 1. Install dependencies
make install

# 2. Build agents and install CLI + agents to system
make tr-install

# 3. Configure your ticketing CLI (e.g. jira-cli for Jira)
jira init

# 4. Plan a ticket (creates PRD.json + story branch)
ticket-ralph ticket PROJ-123 "optional extra context"

# 5. Implement the next task from the PRD
ticket-ralph task PROJ-123 "optional extra context"
# Repeat step 5 until all tasks are done

# 6. Run QA (after all tasks are done)
ticket-ralph qa PROJ-123 "optional extra context"
```

## Structure

```
src/
  ticket_ralph/
    cli.py              — Click CLI entry point (ticket-ralph command)
    config.py           — Configuration resolution, env vars
    exceptions.py       — Custom exceptions with exit codes
    compose.py          — Builds agent .md files from fragments via Jinja2 templating
    utils.py            — Branch name generation, PRD parsing, review helpers
    commands/
      ticket.py         — High-level planning: runs plan agent, creates branch
      task.py           — Task execution: plans next task, implements it, merges it back
      task_loop.py      — Loops task.py until all PRD tasks are done
      qa.py             — QA: runs code-review and QA agents after all tasks are done
    ticketing/
      base.py           — TicketingProvider ABC (platform-agnostic interface)
      jira.py           — Jira sync implementation (httpx for attachments)
      noop.py           — No-op provider for unsupported platforms
    services/
      agent.py          — Claude agent execution (interactive + autonomous modes)
      git.py            — Git operation wrappers
      sync.py           — File sync between local tmp dir and ticketing platform

scripts/
  hooks/                — Claude Code hook scripts (bash, required by hook system)

fragments/
  shared/               — Reusable fragments (roles, principles, conventions)
  shared/shared/        — Sub-shared fragments (referenced by shared fragments)
  agents/               — Agent-specific fragments (each has frontmatter + instructions)

agents/                 — OUTPUT: composed agent .md files (built by make compose)

tests/                  — Unit tests (pytest)

Makefile                — Common commands (install, compose, ticket, task, qa, tr-install, test, lint)
```

## CLI Usage

After `make tr-install`, the `ticket-ralph` CLI is available system-wide:

```bash
ticket-ralph ticket PROJ-123 [extra context] [--base-branch <branch>]
ticket-ralph task PROJ-123 [extra context]
ticket-ralph task-loop PROJ-123 [extra context]
ticket-ralph qa PROJ-123 [extra context] [--base-branch <branch>]
```

`--base-branch` on `ticket` sets the branch the story branch is created from (defaults to remote default branch, e.g. `main`). The value is persisted as `baseBranch` in PRD.json. `--base-branch` on `qa` overrides the parent branch used for the QA diff (fallback chain: CLI arg > PRD `baseBranch` > remote default branch).

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Install dependencies via `uv sync --group dev` |
| `make compose` | Build agent .md files from fragments |
| `make ticket TR_TICKET=ID` | Plan a ticket (optional `TR_EXTRA='context'`) |
| `make task TR_TICKET=ID` | Implement the next PRD task (optional `TR_EXTRA='context'`) |
| `make task-loop TR_TICKET=ID` | Loop tasks until all done (optional `TR_EXTRA='context'`) |
| `make qa TR_TICKET=ID` | Run QA after all tasks done (optional `TR_EXTRA='context'`) |
| `make ticket-auto TR_TICKET=ID` | ticket in autonomous mode |
| `make task-auto TR_TICKET=ID` | task in autonomous mode |
| `make task-loop-auto TR_TICKET=ID` | task-loop in autonomous mode |
| `make qa-auto TR_TICKET=ID` | qa in autonomous mode |
| `make tr-install` | Compose agents + install CLI, agents, hooks, and settings |
| `make format` | Format code with ruff |
| `make lint` | Lint code with ruff |
| `make test` | Run unit tests |
| `make coverage` | Run tests with coverage + diff-cover |

## Key Concepts

- **Fragments**: Reusable markdown pieces. Shared fragments provide common context (roles, SOLID). Agent fragments contain agent-specific instructions + frontmatter. Edit fragments, not agents.
- **Compose**: `compose.py` uses Jinja2 to resolve `{{ variable }}` references in fragments and produce complete agent files in `agents/`.
- **TicketingProvider**: ABC-based abstraction (`ticketing/base.py`) for platform-agnostic file sync. Jira is the current implementation (`jira.py`); other platforms can be added by subclassing `TicketingProvider`. Unrecognized platforms get a `NoOpProvider` (sync skipped with a warning).
- **Adversarial loops**: Review sub-agents return a JSON array of issues; the main agent resolves each one. Up to 5 rounds per phase.
- **Progress tracking**: `progress.txt` stored on the ticket carries learnings between tasks — the only shared state across fresh agent contexts.
- **Branching**: Story branch (`<STORY_ID>-<short-summary>`) from a configurable base branch (defaults to remote default branch, e.g. `main`); task branches (`<STORY_ID>-task-<N>-<short-summary>`) from the story branch. The base branch is stored as `baseBranch` in PRD.json.
- **File storage**: `~/.ticket-ralph/tickets/<STORY_ID>/` locally, synced to ticketing platform attachments after each command run.

## Prerequisites

- **uv**: Python package manager — `brew install uv` or see [docs](https://docs.astral.sh/uv/)
- **claude**: Claude Code CLI
- **git**: Version control
- **jira-cli** (if using Jira): `brew install ankitpokhrel/jira-cli/jira-cli` — configure with `jira init`

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TR_TICKETING_PLATFORM` | **Yes** | Ticketing platform name injected into agent prompts (e.g. `Jira`, `Linear`). |
| `TR_SYNC_PROVIDER` | No | Sync provider for file upload/download (default: `noop`). Set to `jira` for Jira attachment sync. |
| `TR_AUTONOMOUS` | No | Set to `true` to enable autonomous mode (default: `true`) |
| `JIRA_BASE_URL` | For Jira sync | Jira instance URL (auto-read from jira-cli config if not set) |
| `JIRA_USER` | For Jira sync | Jira user email (auto-read from jira-cli config if not set) |
| `JIRA_API_TOKEN` | For Jira sync | Jira API token (auto-read from jira-cli config if not set) |

## Autonomous Mode

Set `TR_AUTONOMOUS=true` to run agents with `--dangerously-skip-permissions` (no sandbox).

```bash
# Single task, autonomous
make task-auto TR_TICKET=PROJ-123

# Full loop, autonomous
make task-loop-auto TR_TICKET=PROJ-123

# ticket/qa: interactive but with skip-permissions
make ticket-auto TR_TICKET=PROJ-123
make qa-auto TR_TICKET=PROJ-123
```

Behaviour:
- **All commands**: `--dangerously-skip-permissions` — no permission prompts
- **Safety warning**: a one-time warning is logged at CLI startup advising to run on a VM with scoped CLI token privileges
- **ticket / qa**: remain interactive (user sees agent work in terminal)
- **task / task-loop**: run agents with `-p` (non-interactive) + `--output-format stream-json` for real-time observability
- **Structured output**: plan and engineer agents output `{"done": boolean, "overview": string}` via `--json-schema`
- **Blocker detection**: if `done: false`, task-loop stops and sends a desktop notification (osascript on macOS, terminal bell on Linux)

Exit code convention:
- `0` — success
- `1` — script/infrastructure error
- `2` — agent blocker (autonomous mode), human intervention needed

## Docs

See `agentdocs/architecture.md` for the full agent flow, orchestration design, and file conventions.
