#!/usr/bin/env bash
# task.sh — Implements a single task from a PRD.
#
# Picks the next available task from PRD.json, plans it, implements it,
# marks it done, and merges it back into the story branch.
#
# Flow:
#   1. Pull PRD.json and progress.txt from Jira if not present in TR_TMP_DIR
#   2. Plan agent (tr-plan) — picks next task, creates plan-<N>.md
#   3. Create task branch from topBranch
#   4. Software engineer agent (tr-software-engineer) — implements the task
#   5. Mark task done in PRD.json, push, merge into topBranch, upload to Jira
#
# Usage: ./scripts/task.sh <JIRA_TICKET_ID> [extra details for the agent]
#
# Environment variables:
#   JIRA_BASE_URL   — Jira instance URL (e.g. https://your-org.atlassian.net)
#   JIRA_USER       — Jira username/email
#   JIRA_API_TOKEN  — Jira API token

set -euo pipefail

TASK_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$TASK_SCRIPT_DIR/lib/utils.sh"
source "$TASK_SCRIPT_DIR/lib/jira.sh"
source "$TASK_SCRIPT_DIR/lib/sync.sh"

# --- Args ---

TICKET_ID="${1:?Usage: task.sh <JIRA_TICKET_ID> [extra details]}"
USER_INPUT="${*:2}"

# --- Setup ---

check_prerequisites
resolve_jira_env
setup_tmp_dir "$TICKET_ID"

log "=== Starting task implementation for $TICKET_ID ==="

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

# Create empty progress.txt if Jira had none (first task run)
touch "$TR_TMP_DIR/progress.txt"

top_branch=$(jq -r '.topBranch' "$TR_TMP_DIR/PRD.json")
if [ -z "$top_branch" ] || [ "$top_branch" = "null" ]; then
  log_error "topBranch not set in PRD.json. Run ticket.sh first to generate the PRD."
  exit 1
fi

remaining=$(jq '[.tasks[] | select(.done == false)] | length' "$TR_TMP_DIR/PRD.json")
if [ "$remaining" -eq 0 ]; then
  log "All tasks in PRD.json are already done. Nothing to implement."
  exit 0
fi

log "Found $remaining undone task(s). Top branch: $top_branch"

# --- Step 2: Checkout topBranch and run tr-plan agent ---

log "Step 2/5: Running planning agent"

git fetch origin
git checkout "$top_branch"
git pull origin "$top_branch"

plan_prompt="Plan the next task for the PRD at $TR_TMP_DIR/PRD.json (progress: $TR_TMP_DIR/progress.txt)."

if [ -n "$USER_INPUT" ]; then
  plan_prompt+="

Additional context: $USER_INPUT"
fi

plan_agent_start=$(date +%s)
run_agent "tr-plan" "$plan_prompt"

# --- Step 3: Determine chosen task number from newest plan file ---

log "Step 3/5: Determining chosen task from plan file"

plan_file=$(ls -t "$TR_TMP_DIR"/plan-*.md 2>/dev/null | head -1 || true)
if [ -z "$plan_file" ]; then
  log_error "No plan file found in $TR_TMP_DIR after running tr-plan agent"
  exit 1
fi

# Verify the plan file was written by this agent run, not a leftover from a previous task
file_mtime=$(stat -f %m "$plan_file" 2>/dev/null || stat -c %Y "$plan_file" 2>/dev/null || echo 0)
if [ "$file_mtime" -lt "$plan_agent_start" ]; then
  log_error "Plan file $(basename "$plan_file") predates this agent run — the tr-plan agent may have failed to write a new plan."
  exit 1
fi

task_number=$(basename "$plan_file" | sed 's/plan-\([0-9]*\)\.md/\1/')
if ! [[ "$task_number" =~ ^[0-9]+$ ]]; then
  log_error "Could not extract a valid task number from plan file: $(basename "$plan_file")"
  exit 1
fi
log "Planning agent chose task $task_number (plan: $(basename "$plan_file"))"

task_title=$(jq -r --argjson n "$task_number" '.tasks[] | select(.taskNumber == $n) | .title' "$TR_TMP_DIR/PRD.json")
if [ -z "$task_title" ] || [ "$task_title" = "null" ]; then
  log_error "Task $task_number not found in PRD.json"
  exit 1
fi

task_done=$(jq -r --argjson n "$task_number" '.tasks[] | select(.taskNumber == $n) | .done' "$TR_TMP_DIR/PRD.json")
if [ "$task_done" = "true" ]; then
  log_error "Task $task_number is already marked as done in PRD.json"
  exit 1
fi

# --- Step 4: Create task branch and run tr-software-engineer agent ---

log "Step 4/5: Creating task branch and running software engineer agent"

branch_suffix=$(echo "$task_title" \
  | tr '[:upper:]' '[:lower:]' \
  | tr -cs '[:alnum:] ' ' ' \
  | awk '{for(i=1;i<=5&&i<=NF;i++) printf "%s%s",$i,(i<5&&i<NF?"-":""); print ""}' \
  | sed 's/-$//')
if [ -z "$branch_suffix" ]; then
  branch_suffix="work"
fi
branch_name="${TICKET_ID}-task-${task_number}-${branch_suffix}"

if git show-ref --verify --quiet "refs/heads/$branch_name"; then
  log "Branch $branch_name already exists locally, checking it out"
  git checkout "$branch_name"
  git pull origin "$branch_name"
else
  git checkout -b "$branch_name" "$top_branch"
fi
git push -u origin "$branch_name"
log "Created and pushed task branch: $branch_name"

engineer_prompt="Implement task $task_number from the PRD.

PRD: $TR_TMP_DIR/PRD.json
Progress: $TR_TMP_DIR/progress.txt
Plan: $TR_TMP_DIR/plan-${task_number}.md
Implement taskNumber: $task_number"

if [ -n "$USER_INPUT" ]; then
  engineer_prompt+="

Additional context: $USER_INPUT"
fi

run_agent "tr-software-engineer" "$engineer_prompt"

# --- Step 5: Mark done, push, merge, and upload ---

log "Step 5/5: Finalizing task $task_number"

# Mark the task done in PRD.json
jq --argjson n "$task_number" \
  '.tasks |= map(if .taskNumber == $n then .done = true else . end)' \
  "$TR_TMP_DIR/PRD.json" > "$TR_TMP_DIR/PRD.json.tmp" \
  && mv "$TR_TMP_DIR/PRD.json.tmp" "$TR_TMP_DIR/PRD.json"
log "Marked task $task_number as done in PRD.json"

# Commit any changes not yet committed by the engineer agent
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -m "chore: finalize task $task_number"
fi

git push origin "$branch_name"
log "Pushed task branch: $branch_name"

# Merge task branch into topBranch
git checkout "$top_branch"
git pull origin "$top_branch"
if ! git merge --no-ff "$branch_name" -m "feat: complete task $task_number - $task_title"; then
  log_error "Merge of $branch_name into $top_branch failed. Resolve the conflict, complete the merge, then re-run to upload artifacts."
  exit 1
fi
git push origin "$top_branch"
log "Merged $branch_name into $top_branch"

# Upload updated PRD.json and progress.txt to Jira
sync_ticket_files "$TICKET_ID"

log "=== Task $task_number implementation complete for $TICKET_ID ==="
