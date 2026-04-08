#!/usr/bin/env bash
# ticket.sh — Orchestrates high-level planning for a Jira ticket.
#
# Supports any ticket type (story, task, etc.). If the ticket has a parent,
# both contexts are fetched and passed to the agent.
#
# Flow:
#   1. Fetch Jira ticket data (+ parent if applicable)
#   2. High-level plan agent (produces PRD.json)
#   3. Create ticket branch
#   4. Upload PRD.json and progress.txt to Jira
#
# Usage: ./scripts/ticket.sh <JIRA_TICKET_ID> [extra details for the agent]
#
# Environment variables:
#   JIRA_BASE_URL   — Jira instance URL (e.g. https://your-org.atlassian.net)
#   JIRA_USER       — Jira username/email
#   JIRA_API_TOKEN  — Jira API token

set -euo pipefail

TICKET_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$TICKET_SCRIPT_DIR/lib/utils.sh"
source "$TICKET_SCRIPT_DIR/lib/jira.sh"
source "$TICKET_SCRIPT_DIR/lib/sync.sh"
source "$TICKET_SCRIPT_DIR/lib/fetch-ticket.sh"

# --- Args ---

TICKET_ID="${1:?Usage: ticket.sh <JIRA_TICKET_ID> [extra details]}"
USER_INPUT="${*:2}"

# --- Setup ---

check_prerequisites
resolve_jira_env
setup_tmp_dir "$TICKET_ID"

log "=== Starting high-level planning for $TICKET_ID ==="

check_git_clean

# --- Guard: ticket must have no existing child tasks ---

existing_tasks=$(jira_get_subtasks "$TICKET_ID")
task_count=$(echo "$existing_tasks" | jq 'length')

if [ "$task_count" -gt 0 ]; then
  log_error "Ticket $TICKET_ID already has $task_count child task(s). High-level planning requires a ticket with no existing child tasks."
  log_error "Existing tasks:"
  echo "$existing_tasks" | jq -r '.[] | "  - \(.key): \(.fields.summary)"' >&2
  exit 1
fi

# --- Step 1: Fetch Jira ticket data ---

log "Step 1/4: Fetching Jira ticket data"
fetch_ticket_context "$TICKET_ID"

# --- Step 2: High-level plan agent ---

log "Step 2/4: Creating high-level plan"

# Extract only what bash needs — agent fetches its own readable ticket data
issue_type=$(jq -r '.issueType' "$TR_TMP_DIR/ticket-context.json")
parent_story_key=$(jq -r '.parentStoryKey // empty' "$TR_TMP_DIR/ticket-context.json")
attachments=$(jq -r '.attachments[]? | .localPath // empty' "$TR_TMP_DIR/ticket-context.json" 2>/dev/null || true)

agent_prompt="Create a high-level plan for Jira $issue_type $TICKET_ID.

First, fetch the ticket details by running: jira issue view $TICKET_ID"

if [ -n "$parent_story_key" ]; then
  parent_type=$(jq -r '.issueType' "$TR_TMP_DIR/parent-context.json")
  agent_prompt+="

This ticket has a parent $parent_type. Also fetch the parent for additional context by running: jira issue view $parent_story_key"
fi

if [ -n "$attachments" ]; then
  agent_prompt+="

The following attachments were downloaded from the ticket — read them to understand their contents:
$attachments"
fi

if [ -n "$USER_INPUT" ]; then
  agent_prompt+="

Additional context: $USER_INPUT"
fi

run_agent "tr-high-level-plan" "$agent_prompt"

if [ ! -f "$TR_TMP_DIR/PRD.json" ]; then
  log_error "Planning agent did not produce PRD.json in $TR_TMP_DIR"
  exit 1
fi

# --- Step 3: Create jira ticket branch ---

log "Step 3/4: Creating jira ticket branch"

ticket_summary=$(jq -r '.summary' "$TR_TMP_DIR/ticket-context.json")
# Take first 5 words, lowercase, replace spaces/special chars with hyphens
branch_suffix=$(echo "$ticket_summary" \
  | tr '[:upper:]' '[:lower:]' \
  | tr -cs '[:alnum:] ' ' ' \
  | awk '{for(i=1;i<=5&&i<=NF;i++) printf "%s%s",$i,(i<5&&i<NF?"-":""); print ""}' \
  | sed 's/-$//')
if [ -z "$branch_suffix" ]; then
  branch_suffix="work"
fi
branch_name="${TICKET_ID}-${branch_suffix}"

git fetch origin
if git show-ref --verify --quiet "refs/heads/$branch_name"; then
  log "Branch $branch_name already exists locally, checking it out"
  git checkout "$branch_name"
  git pull origin "$branch_name"
else
  git checkout -b "$branch_name" origin/main
fi
git push -u origin "$branch_name"
log "Created and pushed branch: $branch_name"

jq --arg branch "$branch_name" '.topBranch = $branch' "$TR_TMP_DIR/PRD.json" > "$TR_TMP_DIR/PRD.json.tmp" \
  && mv "$TR_TMP_DIR/PRD.json.tmp" "$TR_TMP_DIR/PRD.json"
log "Set topBranch in PRD.json to: $branch_name"

# --- Step 4: Upload PRD.json and progress.txt to Jira ---

log "Step 4/4: Uploading artifacts to Jira"
touch "$TR_TMP_DIR/progress.txt"
sync_ticket_files "$TICKET_ID"

log "=== High-level planning complete for $TICKET_ID ==="
