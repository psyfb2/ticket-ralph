# Ticket-Ralph

Orchestrated multi-agent workflow built on Claude Code for Jira-driven software development. Stories and tasks live in Jira; agents plan, implement, review, and QA the work.

## Quick Start

```bash
# 1. Install dependencies
make install

# 2. Build agents and install to ~/.claude/
make tr-install

# 3. Configure jira-cli (if not already done)
jira init

# 4. Plan a ticket (creates PRD.json + ticket branch)
make ticket TR_TICKET=PROJ-123 TR_EXTRA="optional extra context"
```

## Structure

```
src/
  ticket_ralph/
    compose.py       — Builds agent .md files from fragments via Jinja2 templating

scripts/
  ticket.sh          — Orchestrates high-level planning for a Jira ticket
  lib/utils.sh       — Shared utilities (logging, agent runner, review parser)
  lib/jira.sh        — Jira REST API helpers for bash-level operations
  lib/sync.sh        — File sync between local tmp dir and Jira attachments
  lib/fetch-ticket.sh — Fetches Jira ticket data to ticket-context.json
  hooks/             — Claude Code hook scripts

fragments/
  shared/            — Reusable fragments (roles, principles, conventions)
  shared/shared/     — Sub-shared fragments (referenced by shared fragments)
  agents/            — Agent-specific fragments (each has frontmatter + instructions)

agents/              — OUTPUT: composed agent .md files (built by make compose)

Makefile             — Common commands (install, compose, ticket, tr-install)
```

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Install dependencies via `uv sync` |
| `make compose` | Build agent .md files from fragments |
| `make ticket TR_TICKET=ID` | Run ticket.sh for a Jira ticket (optional `TR_EXTRA='context'`) |
| `make tr-install` | Compose agents + copy agents and hooks to `~/.claude/` |

## Key Concepts

- **Fragments**: Reusable markdown pieces. Shared fragments provide common context (roles, SOLID, Jira ops). Agent fragments contain agent-specific instructions + frontmatter.
- **Compose**: `compose.py` uses Jinja2 to resolve `{{ variable }}` references in fragments and produce complete agent files. Edit fragments, not agents.
- **Adversarial loops**: Review agents output `review.json`; fixer agents resolve issues. Max 3 iterations.
- **Risk gating**: Plan agent classifies tasks as low/medium/high. Adversarial loops for plan and implementation are skipped for low-risk tasks. QA loops always run.
- **Progress tracking**: `progress.txt` on the Jira story carries learnings between tasks.
- **Branching**: Story branch (`<STORY_ID>-<short-summary>`, e.g. `PROJ-40015-add-settings-page`) from main; task branches (`<TASK_ID>-<short-summary>`, e.g. `PROJ-40016-add-api-endpoint`) from story branch. Jira ID is always the branch name prefix. Branch names and other agent state are stored in `ticket-ralph-state.json` in the tmp dir.
- **File storage**: `/tmp/ticket-ralph/<STORY_ID>/` locally, synced to Jira attachments after each agent.

## Prerequisites

- **uv**: Python package manager — `brew install uv` or see [docs](https://docs.astral.sh/uv/)
- **jira-cli**: `brew install ankitpokhrel/jira-cli/jira-cli` — configure with `jira init`
- **claude**: Claude Code CLI
- **jq**: JSON processor
- For attachment sync: `JIRA_BASE_URL`, `JIRA_USER`, `JIRA_API_TOKEN` env vars (or jira-cli config is auto-read)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TR_ALWAYS_CONFIRM` | No | If `true`, always confirm plans regardless of risk (default: `false`) |
| `JIRA_BASE_URL` | For attachments | Jira instance URL (auto-read from jira-cli config if not set) |
| `JIRA_USER` | For attachments | Jira user email (auto-read from jira-cli config if not set) |
| `JIRA_API_TOKEN` | For attachments | Jira API token (auto-read from jira-cli config if not set) |

## Docs

See `docs/architecture.md` for the full agent flow, orchestration design, and design decisions.
