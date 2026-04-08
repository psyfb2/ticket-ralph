# Architecture

## Overview

Ticket-Ralph is a bash-orchestrated multi-agent system. Bash scripts control the flow (sequencing, loops, gating), and Claude Code agents do the cognitive work (planning, coding, reviewing). Jira is the source of truth for stories and tasks.

## Agent Inventory

| Agent | Role | Key Input | Key Output |
|-------|------|-----------|------------|
| `tr-high-level-plan` | Architect story plan | `story-context.json` | `PRD.json` |
| `tr-high-level-plan-review` | Adversarial review of plan | `PRD.json` | `review.json` |
| `tr-plan` | Plan next task | Jira tasks, `progress.txt` | `plan.md`, `ticket-ralph-state.json`, task branch |
| `tr-plan-review` | Adversarial review of task plan | `plan.md` | `review.json` |
| `tr-plan-fixer` | Fix plan review issues | `review.json` | Updated `plan.md` |
| `tr-plan-confirm` | User confirmation of task plan | `plan.md`, `ticket-ralph-state.json` | User-approved plan |
| `tr-implementor` | Implement the plan | `plan.md`, `progress.txt` | Code changes, updated `progress.txt` |
| `tr-impl-review` | Adversarial code review | git diff | `review.json` |
| `tr-impl-review-fixer` | Fix code review issues | `review.json` | Fixed code |
| `tr-qa` | QA verification | Code, Jira requirements | `qa-report.md`, `qa-status.json`, PR |
| `tr-qa-fixer` | Fix QA failures | `qa-report.md` | Fixed code |

## Orchestration Flows

### story.sh (High-Level Planning)

```
[git clean check] -> Fetch Story Data -> High-Level Plan Agent -> Create Story Branch -> Upload to Jira
                      (script)           (PRD.json + internal      (script)               (script)
                                          adversarial review +
                                          user confirmation)
```

### task.sh (Task Execution)

```
Plan -> [Plan Adversarial x3]* -> [Plan Confirm]** -> Implement -> [Impl Adversarial x3]* -> [QA Loop x3]
          |              |                                            |              |          |         |
          v              v                                            v              v          v         v
        Review -> Fixer (if issues)                                 Review -> Fixer          QA -> Fixer

 * Skipped for low-risk tasks
** Only for high-risk tasks or TR_ALWAYS_CONFIRM=true
```

## Design Decisions

### Risk Classification

The plan agent classifies each task as low/medium/high risk. This determines:
- **low**: Plan and implementation adversarial loops are skipped. QA still runs.
- **medium**: All adversarial loops run. User confirmation is skipped (unless `TR_ALWAYS_CONFIRM=true`).
- **high**: All adversarial loops run. User confirmation required.

Risk is determined by the plan agent BEFORE adversarial loops run, so it can gate them.

### Branching Strategy

```
main
  └── PROJ-123-create-test-set        (story branch)
        ├── PROJ-124-add-api-endpoint  (task branch, PR -> story branch)
        ├── PROJ-125-write-tests
        └── PROJ-126-update-docs
```

Task PRs target the story branch. A human reviews and merges each task PR. The story branch is merged to main when all tasks are done.

A task in IN REVIEW blocks any dependent tasks — they stay in TO DO until the blocking task reaches DONE.

### Fragment Composition

Agents are assembled from fragments to avoid duplication. `compose.py` uses Jinja2 to resolve `{{ variable }}` references:
1. Shared fragments in `fragments/shared/shared/` are loaded as base variables (leaf nodes)
2. Shared fragments in `fragments/shared/` are rendered against base variables (resolves nested references)
3. Each agent fragment's body is rendered against the resolved shared variables
4. Frontmatter is preserved verbatim

Variable names are derived from filenames: hyphens become underscores (e.g., `prd-progress-input.md` → `{{ prd_progress_input }}`).

Edit fragments in `fragments/`, then run `make compose` to rebuild agents.

### File Sync

Working files live locally in `/tmp/ticket-ralph/<STORY_ID>/`. After each agent completes, the orchestration script syncs relevant files to Jira as attachments. This ensures:
- Jira is the durable store (survives tmp cleanup)
- Agents read from local files (fast)
- Humans can access plans and reports from Jira

### Cross-Task Communication

`progress.txt` is the mechanism for agents to communicate across tasks. The implementor agent appends learnings (codebase patterns, gotchas, decisions) that help subsequent task agents start from an informed position despite fresh context windows.
