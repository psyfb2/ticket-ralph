# Architecture

## Overview

Ticket-Ralph is a Python CLI (`ticket-ralph`, entry point `src/ticket_ralph/cli.py`) that
orchestrates Claude Code agents through the phases of ticket-driven development. Each
subcommand is a module under `src/ticket_ralph/commands/`:

0. **`boost`** *(optional)* — Requirements refinement. Reads a ticket, challenges its
   requirements and design decisions with the user, and writes a sharpened spec back to the
   ticket. Run before `ticket`; nothing downstream requires it.
1. **`ticket`** — High-level planning. Takes a story/ticket ID, produces a `PRD.json`, and
   creates the story branch.
2. **`task`** — Task execution. Picks the next unfinished task from `PRD.json`, plans and
   implements it, then merges it back. **`task-loop`** repeats this until no tasks remain.
3. **`qa`** — QA. Runs after all tasks are done; invokes the QA runner agent (code review,
   functional QA and CI/CD loops) and uploads the final `qa-report.md` to the ticket.

Commands share a service layer (`src/ticket_ralph/services/`) and write all working state to
`~/.ticket-ralph/tickets/<STORY_ID>/`, exposed to agents as `$TR_TMP_DIR`.

---

## Agent Inventory

| Agent | Model | Role |
|-------|-------|------|
| `tr-boost` | Opus | Challenges and sharpens a ticket's requirements with the user, writes them back to the ticket (optional, runs before planning) |
| `tr-high-level-plan` | Opus | Reads ticket context via the platform CLI, produces `PRD.json` |
| `tr-high-level-plan-review` | Sonnet | Reviews `PRD.json` for completeness and quality (sub-agent) |
| `tr-plan` | Opus | Reads `PRD.json`, picks next task, produces `plan-<N>.md` |
| `tr-plan-review` | Sonnet | Reviews `plan-<N>.md` for architectural soundness (sub-agent) |
| `tr-software-engineer` | Opus | Implements a task from its plan, commits code |
| `tr-code-review` | Sonnet | Reviews committed code for correctness and SOLID compliance (sub-agent) |
| `tr-qa-runner` | Opus | Orchestrates QA: three sequential loops (code review → functional QA → CI/CD) |
| `tr-qa-tester` | Opus | Manual testing of requirements, writes `qa-report.md` (sub-agent) |
| `tr-qa-ci-cd` | Sonnet | Pushes branch, creates PR, monitors CI/CD pipeline, outputs JSON issues (sub-agent) |

Most sub-agents run in `permissionMode: plan` (read-only) and return a JSON array of issues:
```json
[{ "issue": "...", "suggestion": "...", "severity": "high|medium|low" }]
```
An empty array (`[]`) means the phase passed. `tr-qa-ci-cd` is an exception — it returns a JSON object:
```json
{ "pr_url": "...", "pipeline_run_urls": ["..."], "issues": [{ "step": "...", "error_logs": "...", "issue": "...", "suggestion": "..." }] }
```
Main agents resolve each issue and re-run review. The round cap is per agent, set in its
fragment: `tr-high-level-plan` 3, `tr-plan` and `tr-software-engineer` 1, `tr-qa-runner` 5 per
loop.

---

## Full Flow

### Phase 0 (optional) — `ticket-ralph boost <STORY_ID>`

```
run_boost()                        # src/ticket_ralph/commands/boost.py
  └─ guard: sync provider must declare a CLI (NoOpProvider has none)
  |
  └─ run_agent "tr-boost"          # interactive; no git, no branch, no attachment sync
       ├─ Reads the ticket (+ parent, + attachments) via the platform CLI
       ├─ Snapshots title/description verbatim → original-ticket.md
       ├─ Challenges the requirements against the requester's underlying goal
       ├─ Interviews the user until every gap and edge case is closed
       ├─ Applies the same scrutiny to design decisions, if the ticket states any
       ├─ Writes boost.md, then loops with the user until they approve it
       └─ On approval: comments the original description, then replaces
          the ticket description with boost.md
```

**Outputs**: `boost.md`, `original-ticket.md`, and a rewritten ticket. Nothing downstream
depends on this phase having run; `ticket` simply receives a sharper ticket when it has.

### Phase 1 — `ticket-ralph ticket <STORY_ID> [--base-branch <branch>]`

```
run_ticket()                       # src/ticket_ralph/commands/ticket.py
  └─ git.check_clean()
  |
  └─ executor.run "tr-high-level-plan"
  |    ├─ Fetches the ticket (+ parent, + attachments) via the platform CLI
  |    ├─ Writes PRD.json
  |    ├─ Adversarial review via tr-high-level-plan-review (≤3 rounds)
  |    └─ Confirms the plan with the user
  |
  └─ git checkout -b <STORY_ID>-<summary> origin/<baseBranch>   # --base-branch, else remote default
  └─ PRD.json: topBranch = branch name, baseBranch = resolved base   # utils.atomic_write_json
  └─ sync.sync_ticket_files()      # uploads PRD.json + progress.txt as attachments
```

**Outputs**: `PRD.json`, `progress.txt` (empty), story branch on origin.

### Phase 2 — `ticket-ralph task <STORY_ID>`

```
run_task()                         # src/ticket_ralph/commands/task.py
  └─ git.check_clean()
  └─ sync.download_ticket_context()   # if PRD.json or progress.txt missing locally
  |
  └─ git fetch && git checkout <topBranch> && git pull
  |
  └─ executor.run "tr-plan"        # run_autonomous + AUTONOMOUS_SCHEMA when autonomous
  |    ├─ Reads PRD.json + progress.txt
  |    ├─ Picks next non-blocked, non-done task
  |    ├─ Explores codebase (read-only)
  |    ├─ Writes plan-<N>.md
  |    ├─ Adversarial review via tr-plan-review (≤1 round)
  |    └─ Appends learnings to progress.txt
  |
  └─ git checkout -b <STORY_ID>-task-<N>-<summary>   # reuses the branch if it already exists
  └─ git push -u
  |
  └─ executor.run "tr-software-engineer"   # run_autonomous + AUTONOMOUS_SCHEMA when autonomous
  |    ├─ Reads PRD.json, progress.txt, plan-<N>.md
  |    ├─ Implements task N, commits changes
  |    ├─ Adversarial review via tr-code-review (≤1 round)
  |    └─ Appends learnings to progress.txt
  |
  └─ utils.mark_task_done(PRD.json, N)
  └─ git commit -am "chore: finalize task N" && git push
  └─ git checkout <topBranch> && git merge --no-ff <task branch> && git push
  └─ sync.sync_ticket_files()      # uploads PRD.json + progress.txt
```

**Outputs**: Code commits on the story branch, updated `PRD.json` (task marked done), updated
`progress.txt`.

`--continue-plan <N>` / `--continue-impl <N>` build a `ResumeDirective` (`ResumePhase.PLAN` /
`ResumePhase.IMPL`) that pins the task number and, for `IMPL`, skips planning and reuses the
existing local `plan-<N>.md`.

### Phase 2b — `ticket-ralph task-loop <STORY_ID>`

```
run_task_loop()                    # src/ticket_ralph/commands/task_loop.py
  └─ loop:
       ├─ run_task(...)            # resume directive applies to the first iteration only
       ├─ on AutonomousBlocker  → utils.notify_blocker(), stop with exit code 2
       └─ utils.count_remaining_tasks(PRD) == 0 → stop
```

### Phase 3 — `ticket-ralph qa <STORY_ID> [--base-branch <branch>]`

```
run_qa()                           # src/ticket_ralph/commands/qa.py
  └─ git.check_clean()
  └─ sync.download_ticket_context()   # if PRD.json or progress.txt missing locally
  |
  └─ guard: every task must be done (no-PRD mode skips this — see below)
  |
  └─ git fetch && git checkout <topBranch> && git pull
  └─ parent branch = --base-branch > PRD baseBranch > remote default branch
  |
  └─ executor.run "tr-qa-runner"
  |    ├─ Prompt carries the PRD + progress paths and the parent branch
  |    ├─ Loop 1: Calls tr-code-review sub-agent, fixes issues (≤5 rounds)
  |    ├─ Loop 2: Calls tr-qa-tester sub-agent, fixes failures (≤5 rounds)
  |    |    └─ Writes qa-report.md
  |    └─ Loop 3: Calls tr-qa-ci-cd sub-agent, fixes failures (≤5 rounds)
  |         └─ Pushes branch, creates PR, monitors CI/CD pipeline
  |
  └─ sync.sync_ticket_files()      # uploads PRD.json + progress.txt
  └─ sync.sync_to_ticketing(qa-report.md)
```

**Outputs**: `qa-report.md` (pass/fail summary), any fix commits on the story branch.

**No-PRD mode**: when `PRD.json` is absent (the ticket was implemented outside ticket-ralph),
`qa` runs against the current branch, tells the agent to fetch the requirements from the ticket
itself, skips the all-tasks-done guard, and skips `sync_ticket_files` — only `qa-report.md` is
uploaded.

---

## File Conventions

| File | Lives in | Purpose |
|------|----------|---------|
| `boost.md` | `$TR_TMP_DIR` | Refined requirements produced by `tr-boost`; becomes the new ticket description (not synced as an attachment) |
| `original-ticket.md` | `$TR_TMP_DIR` | Verbatim pre-boost snapshot of the ticket title + description (not synced) |
| `PRD.json` | `$TR_TMP_DIR` + ticket | Requirements, tasks, topBranch, baseBranch |
| `progress.txt` | `$TR_TMP_DIR` + ticket | Accumulated learnings between tasks |
| `plan-<N>.md` | `$TR_TMP_DIR` | Plan for task N (not synced) |
| `qa-report.md` | `$TR_TMP_DIR` + ticket | QA pass/fail report produced by `tr-qa-tester` |
| `.blocker-overview` | `$TR_TMP_DIR` | Last autonomous blocker explanation; read by `task-loop` for the notification |

`$TR_TMP_DIR` = `~/.ticket-ralph/tickets/<STORY_ID>/`, injected into every agent subprocess by
`AgentExecutor._subprocess_env`. "+ ticket" means the file is also uploaded as an attachment by
`SyncService`; `sync_ticket_files` covers `PRD.json` and `progress.txt`, and `qa` uploads
`qa-report.md` with a direct `sync_to_ticketing` call.

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

| Module | Key exports |
|--------|-------------|
| `cli.py` | Click group + the `boost` / `ticket` / `task` / `task-loop` / `qa` subcommands, `main()` (maps `TicketRalphError.exit_code` to the process exit code) |
| `config.py` | `TicketRalphConfig` (per-run config; `from_env` + `tmp_dir` creation), `check_prerequisites`, `AGENTS_DIR`, `TICKETS_DIR`, `AUTONOMOUS_SCHEMA`, `SYNC_PROVIDER_CLI_COMMANDS` |
| `settings.py` | `AppSettings` / `JiraSettings` / `LinearSettings` (pydantic-settings), `app_settings`, `load_app_settings` — the single boundary where env vars enter |
| `exceptions.py` | `TicketRalphError` (exit 1), `AgentError`, `MergeConflictError`, `AutonomousBlocker` (exit 2) |
| `services/agent.py` | `AgentExecutor.run` (interactive), `AgentExecutor.run_autonomous` (`-p` + stream-json), `AgentResult`, `check_autonomous_result` |
| `services/git.py` | `check_clean`, `fetch`, `pull`, `push`, `checkout`, `branch_exists`, `current_branch`, `default_branch`, `merge_no_ff`, `add_all_and_commit` |
| `services/sync.py` | `SyncService.sync_ticket_files`, `download_ticket_context`, `sync_to_ticketing`, `sync_from_ticketing` |
| `utils.py` | `generate_branch_name`, `read_prd`, `atomic_write_json`, `mark_task_done`, `count_remaining_tasks`, `get_task_info`, `is_review_clean`, `extract_task_number_from_plan`, `find_latest_plan_file`, `notify_blocker` |
| `compose.py` | Fragment → agent build (see *Agent File Build System*) |

Jira credential resolution order: `JIRA_*` env vars → `~/.config/.jira/.config.yml` (jira-cli
config). Linear uses `LINEAR_API_KEY` / `LINEAR_API_URL`.

The only shell script left in the repo is `scripts/hooks/tr-file-write-guard.sh`, a `PreToolUse`
hook that confines `Edit`/`Write` to `$TR_TMP_DIR`. It is wired per-agent in frontmatter
(`agentMetadata.hooks`) by `tr-boost`, `tr-high-level-plan` and `tr-plan`, and installed to
`~/.claude/hooks/` by `make tr-install`. It requires `jq`.

### Ticketing providers (file sync)

File sync is platform-agnostic via the `TicketingProvider` ABC
(`src/ticket_ralph/ticketing/base.py`), selected by `TR_SYNC_PROVIDER` through
`create_provider` (`ticketing/__init__.py`). `create_provider` and
`SYNC_PROVIDER_CLI_COMMANDS` both match the provider id exactly, so `AppSettings`
lowercases and trims `TR_SYNC_PROVIDER` on the way in — otherwise a value like
`Linear` would silently resolve to `NoOpProvider` and skip sync entirely.

- **Jira** (`jira.py`) — REST API over httpx; Basic auth from `JIRA_*` env vars
  or jira-cli config; uploads/downloads attachments by filename.
- **Linear** (`linear.py`) — GraphQL API over httpx; `LINEAR_API_KEY` auth.
  Uploading is a three-step flow (`fileUpload` mutation → PUT bytes to the
  presigned URL → `attachmentCreate` linking the asset URL); the human
  identifier (e.g. `ENG-123`) is resolved to the issue UUID first, and
  attachments are matched/replaced by title.
- **NoOp** (`noop.py`) — fallback for unrecognized platforms; sync skipped
  with a warning.

Agents read ticket content via the platform CLI (`jira` / `linear`), declared in
`SYNC_PROVIDER_CLI_COMMANDS` (`config.py`) and verified by `check_prerequisites`.
Add a platform by subclassing `TicketingProvider`, registering it in
`create_provider`, and adding its CLI to `SYNC_PROVIDER_CLI_COMMANDS`.

Ticket **writes** sit on the same side of that boundary. `tr-boost` updates the
ticket description and adds its snapshot comment through the platform CLI, so no
provider method exists (or is needed) for it — the ABC stays scoped to attachment
sync, and the agent fragments stay platform-agnostic by discovering the CLI's
flags with `--help` rather than hardcoding them. `run_boost` refuses to start when
`create_provider(...).cli_commands` is empty, since a `NoOpProvider` platform gives
the agent no way to read or update the ticket.

---

## Autonomous Mode

When `TR_AUTONOMOUS=true`, agents run with `--dangerously-skip-permissions` (no sandbox). A one-time safety warning is logged at CLI startup.

### Two execution paths

| Command | Interactive mode | Autonomous mode |
|---------|-----------------|-----------------|
| `boost` | `claude --agent ... --permission-mode acceptEdits` | `claude --agent ... --dangerously-skip-permissions` (still interactive) |
| `ticket` | Same as boost | Same as boost autonomous |
| `qa` | Same as boost | Same as boost autonomous |
| `task` / `task-loop` (plan + engineer) | Same as boost | `claude -p --agent ... --dangerously-skip-permissions --output-format stream-json --json-schema ...` (non-interactive) |

`boost` has no non-interactive path at all: its value is the Q&A with the user, so autonomous
mode only relaxes permissions.

### Structured output

In autonomous mode, plan and engineer agents output `{"done": boolean, "overview": string}` enforced by `--json-schema`. The stream-json format streams text deltas to stderr for real-time observability while the structured result is extracted from the final `result` event.

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Script or infrastructure error (`TicketRalphError`) |
| `2` | Agent blocker (autonomous mode) — human intervention needed (`AutonomousBlocker`) |

`check_autonomous_result` writes the blocker explanation to `$TR_TMP_DIR/.blocker-overview` and
raises `AutonomousBlocker`. `run_task_loop` catches it, sends a desktop notification via
`utils.notify_blocker` (osascript on macOS, terminal bell on Linux), and stops.

### Safety Warning

When autonomous mode is active, a one-time warning is logged at CLI startup advising the user to:
- Run autonomous mode only on a VM
- Ensure all CLIs have scoped token privileges that prevent catastrophic actions (e.g. force-push to main, rewrite git history, change repo settings, delete production infrastructure)

---

## Branching Convention

```
<baseBranch> (default: main, configurable via --base-branch)
 └─ <STORY_ID>-<short-summary>          ← story branch (topBranch)
      └─ <STORY_ID>-task-<N>-<summary>  ← task branch, merged back after each task
```

Example: story `PROJ-123` with two tasks, branched from `develop`:
```
develop
 └─ PROJ-123-add-settings-page
      ├─ PROJ-123-task-1-add-api-endpoint   (merged)
      └─ PROJ-123-task-2-add-ui-components  (merged)
```

The base branch is stored as `baseBranch` in `PRD.json` and used by `qa` to determine the parent branch for diffs. The `qa` command's `--base-branch` flag can override this (e.g. when the original base branch was temporary).
