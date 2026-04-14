# Ticket-Ralph

Orchestrated multi-agent workflow built on Claude Code for Jira-driven software development. Stories and tasks live in Jira; agents plan, implement, and review the work.

## Quick Start

```bash
# 1. Install dependencies
make install

# 2. Build agents and install to ~/.claude/
make tr-install

# 3. Configure jira-cli (if not already done)
jira init

# 4. Plan a ticket (creates PRD.json + story branch)
make ticket TR_TICKET=PROJ-123 TR_EXTRA="optional extra context"

# 5. Implement the next task from the PRD
make task TR_TICKET=PROJ-123 TR_EXTRA="optional extra context"
# Repeat step 5 until all tasks are done

# 6. Run QA (after all tasks are done)
make qa TR_TICKET=PROJ-123 TR_EXTRA="optional extra context"
```

## Structure

```
src/
  ticket_ralph/
    compose.py        — Builds agent .md files from fragments via Jinja2 templating

scripts/
  ticket.sh           — High-level planning: fetches Jira ticket, runs plan agent, creates story branch
  task.sh             — Task execution: plans next task, implements it, merges it back
  qa.sh               — QA: runs code-review + testing loops after all tasks are done
  lib/utils.sh        — Shared utilities (logging, agent runner)
  lib/jira.sh         — Jira REST API helpers for bash-level operations
  lib/sync.sh         — File sync between local tmp dir and Jira attachments
  lib/fetch-ticket.sh — Fetches Jira ticket data to ticket-context.json
  hooks/              — Claude Code hook scripts

fragments/
  shared/             — Reusable fragments (roles, principles, conventions)
  shared/shared/      — Sub-shared fragments (referenced by shared fragments)
  agents/             — Agent-specific fragments (each has frontmatter + instructions)

agents/               — OUTPUT: composed agent .md files (built by make compose)

Makefile              — Common commands (install, compose, ticket, task, qa, tr-install)
```

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Install dependencies via `uv sync` |
| `make compose` | Build agent .md files from fragments |
| `make ticket TR_TICKET=ID` | Run ticket.sh for a Jira ticket (optional `TR_EXTRA='context'`) |
| `make task TR_TICKET=ID` | Run task.sh to implement the next PRD task (optional `TR_EXTRA='context'`) |
| `make qa TR_TICKET=ID` | Run qa.sh after all tasks are done (optional `TR_EXTRA='context'`) |
| `make ticket-auto TR_TICKET=ID` | Run ticket.sh in autonomous mode (interactive, no permission prompts) |
| `make task-auto TR_TICKET=ID` | Run task.sh in autonomous mode (non-interactive `-p`) |
| `make task-loop-auto TR_TICKET=ID` | Run task-loop.sh in autonomous mode |
| `make qa-auto TR_TICKET=ID` | Run qa.sh in autonomous mode (interactive, no permission prompts) |
| `make tr-install` | Compose agents + copy agents, hooks, and settings to `~/.claude/` and `~/.ticket-ralph/` |

## Key Concepts

- **Fragments**: Reusable markdown pieces. Shared fragments provide common context (roles, SOLID, Jira ops). Agent fragments contain agent-specific instructions + frontmatter. Edit fragments, not agents.
- **Compose**: `compose.py` uses Jinja2 to resolve `{{ variable }}` references in fragments and produce complete agent files in `agents/`.
- **Adversarial loops**: Review sub-agents return a JSON array of issues; the main agent resolves each one. Up to 5 rounds per phase.
- **Progress tracking**: `progress.txt` stored on the Jira story carries learnings between tasks — the only shared state across fresh agent contexts.
- **Branching**: Story branch (`<STORY_ID>-<short-summary>`) from `main`; task branches (`<STORY_ID>-task-<N>-<short-summary>`) from the story branch.
- **File storage**: `~/.ticket-ralph/tickets/<STORY_ID>/` locally, synced to Jira attachments after each script run.

## Prerequisites

- **uv**: Python package manager — `brew install uv` or see [docs](https://docs.astral.sh/uv/)
- **jira-cli**: `brew install ankitpokhrel/jira-cli/jira-cli` — configure with `jira init`
- **claude**: Claude Code CLI
- **jq**: JSON processor
- **curl**: For Jira attachment sync (`JIRA_BASE_URL`, `JIRA_USER`, `JIRA_API_TOKEN` env vars, or auto-read from jira-cli config)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `JIRA_BASE_URL` | For attachments | Jira instance URL (auto-read from jira-cli config if not set) |
| `JIRA_USER` | For attachments | Jira user email (auto-read from jira-cli config if not set) |
| `JIRA_API_TOKEN` | For attachments | Jira API token (auto-read from jira-cli config if not set) |
| `TR_AUTONOMOUS` | No | Set to `true` to enable autonomous mode (default: `false`) |

## Autonomous Mode

Set `TR_AUTONOMOUS=true` to run agents with `--dangerously-skip-permissions` and an OS-level sandbox for safety.

```bash
# Single task, autonomous
make task-auto TR_TICKET=PROJ-123

# Full loop, autonomous
make task-loop-auto TR_TICKET=PROJ-123

# ticket/qa: interactive but with sandbox + skip-permissions
make ticket-auto TR_TICKET=PROJ-123
make qa-auto TR_TICKET=PROJ-123
```

Behaviour:
- **All scripts**: `--dangerously-skip-permissions` + sandbox settings (`~/.ticket-ralph/settings.json`) — no permission prompts
- **ticket.sh / qa.sh**: remain interactive (user sees agent work in terminal)
- **task.sh / task-loop.sh**: run agents with `-p` (non-interactive) + `--output-format stream-json` for real-time observability
- **Structured output**: plan and engineer agents output `{"done": boolean, "overview": string}` via `--json-schema`
- **Blocker detection**: if `done: false`, task-loop stops and sends a `terminal-notifier` notification

Exit code convention for task.sh:
- `0` — success
- `1` — script/infrastructure error
- `2` — agent blocker (autonomous mode), human intervention needed

Sandbox config (`.claude/ticket-ralph-settings.json`, installed to `~/.ticket-ralph/settings.json`):
- Filesystem: write access restricted to project dir (`.`), `/tmp`, `~/.ticket-ralph/tickets/`
- Network: unrestricted (with `--dangerously-skip-permissions`, the proxy auto-approves all domains)

## Docs

See `agentdocs/architecture.md` for the full agent flow, orchestration design, and file conventions.
