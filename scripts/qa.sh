#!/usr/bin/env bash
# qa.sh — Runs QA after all PRD tasks are complete.
#
# Checks that every task in PRD.json is done, then invokes the tr-qa-runner
# agent (which orchestrates code-review + QA-tester sub-agents in a loop).
# Uploads PRD.json, progress.txt, and qa-report.md back to Jira when done.
#
# Usage: ./scripts/qa.sh <JIRA_TICKET_ID> [extra details for the agent]
#
# Environment variables:
#   JIRA_BASE_URL   — Jira instance URL (e.g. https://your-org.atlassian.net)
#   JIRA_USER       — Jira username/email
#   JIRA_API_TOKEN  — Jira API token

set -euo pipefail

QA_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$QA_SCRIPT_DIR/lib/utils.sh"
source "$QA_SCRIPT_DIR/lib/jira.sh"
source "$QA_SCRIPT_DIR/lib/sync.sh"

# --- Args ---

TICKET_ID="${1:?Usage: qa.sh <JIRA_TICKET_ID> [extra details]}"
USER_INPUT="${*:2}"

# --- Setup ---

check_prerequisites
resolve_jira_env
setup_tmp_dir "$TICKET_ID"

log "=== Starting QA for $TICKET_ID ==="

check_git_clean

# --- Step 1: Ensure PRD.json and progress.txt are available ---

log "Step 1/5: Ensuring PRD.json and progress.txt are available"

if [ ! -f "$TR_TMP_DIR/PRD.json" ] || [ ! -f "$TR_TMP_DIR/progress.txt" ]; then
  log "Downloading ticket files from Jira $TICKET_ID..."
  download_ticket_context "$TICKET_ID"
fi

if [ ! -f "$TR_TMP_DIR/PRD.json" ]; then
  log_error "PRD.json not found in $TR_TMP_DIR. Run ticket.sh first to generate the PRD."
  exit 1
fi

touch "$TR_TMP_DIR/progress.txt"

# --- Step 2: Confirm all tasks are done ---

log "Step 2/5: Confirming all tasks are complete"

top_branch=$(jq -r '.topBranch' "$TR_TMP_DIR/PRD.json")
if [ -z "$top_branch" ] || [ "$top_branch" = "null" ]; then
  log_error "topBranch not set in PRD.json. Run ticket.sh first to generate the PRD."
  exit 1
fi

remaining=$(jq '[.tasks[] | select(.done == false)] | length' "$TR_TMP_DIR/PRD.json")
if [ "$remaining" -gt 0 ]; then
  log_error "$remaining task(s) are not yet done. Complete all tasks with task.sh before running QA."
  jq -r '.tasks[] | select(.done == false) | "  - Task \(.taskNumber): \(.title)"' "$TR_TMP_DIR/PRD.json" >&2
  exit 1
fi

log "All tasks are done. Top branch: $top_branch"

# --- Step 3: Checkout topBranch ---

log "Step 3/5: Checking out top branch"

git fetch origin
git checkout "$top_branch"
git pull origin "$top_branch"

# --- Step 4: Run tr-qa-runner agent ---

log "Step 4/5: Running QA agent"

default_branch=$(git remote show origin 2>/dev/null | grep 'HEAD branch' | awk '{print $NF}')
if [ -z "$default_branch" ]; then
  default_branch="main"
  log "WARNING: Could not determine default branch from remote; falling back to 'main'"
fi

qa_prompt="PRD: $TR_TMP_DIR/PRD.json
Progress: $TR_TMP_DIR/progress.txt
parent branch: $default_branch

Read the PRD, it contains user requirements, high-level design and a set of tasks to achieve the user requirements.
Also, read the progress.txt file, it contains learnings and useful information specific to this PRD from previously done tasks.
The most important field is the requirements field of the PRD, the rest is there to give you more context but the source of truth is the requirements.

The changes on this branch implement the requirements listed in the PRD.
"

if [ -n "$USER_INPUT" ]; then
  qa_prompt+="

Additional context: $USER_INPUT"
fi

run_agent "tr-qa-runner" "$qa_prompt"

# --- Step 5: Upload artefacts to Jira ---

log "Step 5/5: Uploading artefacts to Jira"

sync_ticket_files "$TICKET_ID"

if [ ! -f "$TR_TMP_DIR/qa-report.md" ]; then
  log_error "QA agent did not produce qa-report.md in $TR_TMP_DIR"
  exit 1
fi
sync_to_jira "$TICKET_ID" "$TR_TMP_DIR/qa-report.md"

log "=== QA complete for $TICKET_ID ==="
