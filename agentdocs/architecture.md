# Architecture

## Overview

Ticket-Ralph is a three-phase orchestration system. Each phase is a bash script that shells out to Claude Code agents:

1. **`ticket.sh`** — High-level planning. Takes a Jira story/ticket ID, produces a `PRD.json`, and creates the story branch.
2. **`task.sh`** — Task execution. Takes the same Jira story ID, picks the next unfinished task from `PRD.json`, plans and implements it, then merges it back.
3. **`qa.sh`** — QA. Runs after all tasks are done; invokes the QA runner agent (code-review + testing loops) and uploads the final `qa-report.md` to Jira.

All scripts share the same library layer (`scripts/lib/`) and write all working state to `~/.ticket-ralph/tickets/<STORY_ID>/`.

---

## Agent Inventory

| Agent | Model | Role |
|-------|-------|------|
| `tr-high-level-plan` | Opus | Reads Jira ticket context, produces `PRD.json` |
| `tr-high-level-plan-review` | Sonnet | Reviews `PRD.json` for completeness and quality (sub-agent) |
| `tr-plan` | Opus | Reads `PRD.json`, picks next task, produces `plan-<N>.md` |
| `tr-plan-review` | Sonnet | Reviews `plan-<N>.md` for architectural soundness (sub-agent) |
| `tr-software-engineer` | Opus | Implements a task from its plan, commits code |
| `tr-code-review` | Sonnet | Reviews committed code for correctness and SOLID compliance (sub-agent) |
| `tr-qa-runner` | Opus | Orchestrates QA: runs code review + testing loops |
| `tr-qa-tester` | Sonnet | Manual testing and CI/CD validation (sub-agent) |

Sub-agents run in `permissionMode: plan` (read-only) and return a JSON array of issues:
```json
[{ "issue": "...", "suggestion": "...", "severity": "high|medium|low" }]
```
An empty array (`[]`) means the phase passed. Main agents resolve each issue and re-run review, up to 5 rounds.

---

## Full Flow

### Phase 1 — `ticket.sh <STORY_ID>`

```
ticket.sh
  └─ fetch_ticket_context()        # scripts/lib/fetch-ticket.sh
  |    ├─ Jira ticket → ticket-context.json
  |    └─ Parent ticket (if any) → parent-context.json
  |
  └─ run_agent "tr-high-level-plan"
  |    ├─ Reads ticket-context.json (+ parent-context.json)
  |    ├─ Writes PRD.json
  |    └─ Adversarial review via tr-high-level-plan-review (≤5 rounds)
  |
  └─ git checkout -b <STORY_ID>-<title> main
  └─ jq: PRD.json.topBranch = branch name
  └─ sync_ticket_files()           # uploads PRD.json + progress.txt to Jira
```

**Outputs**: `PRD.json`, `progress.txt` (empty), story branch on origin.

### Phase 2 — `task.sh <STORY_ID>`

```
task.sh
  └─ download_ticket_context()     # if PRD.json or progress.txt missing locally
  |
  └─ git checkout <topBranch> && git pull
  |
  └─ run_agent "tr-plan"
  |    ├─ Reads PRD.json + progress.txt
  |    ├─ Picks next non-blocked, non-done task
  |    ├─ Explores codebase (read-only)
  |    ├─ Writes plan-<N>.md
  |    ├─ Adversarial review via tr-plan-review (≤5 rounds)
  |    └─ Appends learnings to progress.txt
  |
  └─ git checkout -b <STORY_ID>-task-<N>-<title>
  |
  └─ run_agent "tr-software-engineer"
  |    ├─ Reads PRD.json, progress.txt, plan-<N>.md
  |    ├─ Implements task N, commits changes
  |    ├─ Adversarial review via tr-code-review (≤5 rounds)
  |    └─ Appends learnings to progress.txt
  |
  └─ jq: PRD.json tasks[N].done = true
  └─ git merge --no-ff task-branch → topBranch
  └─ sync_ticket_files()           # uploads PRD.json + progress.txt to Jira
```

**Outputs**: Code commits on story branch, updated `PRD.json` (task marked done), updated `progress.txt`.

Repeat `task.sh` until all tasks in `PRD.json` are done.

### Phase 3 — `qa.sh <STORY_ID>`

```
qa.sh
  └─ download_ticket_context()     # if PRD.json or progress.txt missing locally
  |
  └─ guard: all tasks must be done (done == true)
  |
  └─ git checkout <topBranch> && git pull
  |
  └─ run_agent "tr-qa-runner"
  |    ├─ Prompt includes PRD.json + progress.txt contents
  |    ├─ Calls tr-code-review sub-agent, fixes issues (≤5 rounds)
  |    └─ Calls tr-qa-tester sub-agent, fixes failures (≤5 rounds)
  |         └─ Writes qa-report.md
  |
  └─ sync_ticket_files()           # uploads PRD.json + progress.txt to Jira
  └─ sync_to_jira qa-report.md     # uploads qa-report.md to Jira
```

**Outputs**: `qa-report.md` (pass/fail summary), any fix commits on story branch.

---

## File Conventions

| File | Lives in | Purpose |
|------|----------|---------|
| `PRD.json` | `$TR_TMP_DIR` + Jira | Requirements, tasks, topBranch |
| `progress.txt` | `$TR_TMP_DIR` + Jira | Accumulated learnings between tasks |
| `ticket-context.json` | `$TR_TMP_DIR` | Jira ticket data for current run (not synced) |
| `parent-context.json` | `$TR_TMP_DIR` | Parent Jira ticket data if applicable (not synced) |
| `plan-<N>.md` | `$TR_TMP_DIR` | Plan for task N (not synced) |
| `qa-report.md` | `$TR_TMP_DIR` + Jira | QA pass/fail report produced by `tr-qa-tester` |

`$TR_TMP_DIR` = `~/.ticket-ralph/tickets/<STORY_ID>/`

---

## Agent File Build System

Agent `.md` files in `agents/` are **generated** — do not edit them directly.

```
fragments/
  agents/<name>.md      — Agent frontmatter + agent-specific instructions
  shared/<name>.md      — Reusable fragment (role, principles, explore instructions, etc.)
  shared/shared/<name>.md — Sub-fragments referenced by shared fragments
```

`src/ticket_ralph/compose.py` uses Jinja2 to resolve `{{ fragment_name }}` references up to 5 levels deep and writes the final files to `agents/`. Run `make compose` (or `make tr-install`) to rebuild.

---

## Library Layer

| File | Key exports |
|------|-------------|
| `scripts/lib/utils.sh` | `run_agent`, `run_agent_autonomous`, `is_autonomous`, `check_autonomous_result`, `notify_blocker`, `log`, `log_error`, `check_prerequisites`, `resolve_jira_env`, `setup_tmp_dir`, `check_git_clean` |
| `scripts/lib/jira.sh` | `jira_get_issue`, `jira_get_subtasks`, `jira_upload_attachment`, `jira_download_attachment` |
| `scripts/lib/sync.sh` | `sync_ticket_files`, `download_ticket_context` |
| `scripts/lib/fetch-ticket.sh` | `fetch_ticket_context` |

Jira credential resolution order: env vars → `~/.config/.jira/.config.yml` (jira-cli config).

---

## Autonomous Mode

When `TR_AUTONOMOUS=true`, agents run with `--dangerously-skip-permissions` and an OS-level sandbox (`~/.ticket-ralph/settings.json` loaded via `--settings`).

### Two execution paths

| Script | Interactive mode | Autonomous mode |
|--------|-----------------|-----------------|
| `ticket.sh` | `claude --agent ... --permission-mode acceptEdits` | `claude --agent ... --dangerously-skip-permissions --settings ...` (still interactive) |
| `qa.sh` | Same as ticket.sh | Same as ticket.sh autonomous |
| `task.sh` (plan + engineer) | Same as ticket.sh | `claude -p --agent ... --dangerously-skip-permissions --output-format stream-json --json-schema ...` (non-interactive) |

### Structured output

In autonomous mode, plan and engineer agents output `{"done": boolean, "overview": string}` enforced by `--json-schema`. The stream-json format streams text deltas to stderr for real-time observability while the structured result is extracted from the final `result` event.

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Script or infrastructure error |
| `2` | Agent blocker (autonomous mode) — human intervention needed |

When `task-loop.sh` receives exit code 2, it reads `$TR_TMP_DIR/.blocker-overview`, sends a `terminal-notifier` notification, and stops.

### Sandbox

The sandbox config (`.claude/ticket-ralph-settings.json`, installed to `~/.ticket-ralph/settings.json`) restricts filesystem writes to the project directory (`.`), `/tmp`, and `~/.ticket-ralph/tickets/`. Network is unrestricted — with `--dangerously-skip-permissions`, the proxy auto-approves all domains.

---

## Branching Convention

```
main
 └─ <STORY_ID>-<short-summary>          ← story branch (topBranch)
      └─ <STORY_ID>-task-<N>-<summary>  ← task branch, merged back after each task
```

Example: story `PROJ-123` with two tasks:
```
main
 └─ PROJ-123-add-settings-page
      ├─ PROJ-123-task-1-add-api-endpoint   (merged)
      └─ PROJ-123-task-2-add-ui-components  (merged)
```
