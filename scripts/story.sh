#!/usr/bin/env bash
# story.sh — Orchestrates high-level planning for a Jira story.
#
# Flow:
#   1. High-level plan agent
#   2. Adversarial loop (max 3 iterations):
#        - High-level plan review agent
#        - High-level plan fixer agent
#   3. High-level plan user confirmation agent
#
# Usage: ./scripts/story.sh <JIRA_STORY_ID> [extra details for the agent]
#
# Environment variables:
#   JIRA_BASE_URL   — Jira instance URL (e.g. https://your-org.atlassian.net)
#   JIRA_USER       — Jira username/email
#   JIRA_API_TOKEN  — Jira API token

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib/utils.sh"
source "$SCRIPT_DIR/lib/jira.sh"
source "$SCRIPT_DIR/lib/sync.sh"

# --- Args ---

STORY_ID="${1:?Usage: story.sh <JIRA_STORY_ID> [extra details]}"
USER_INPUT="${*:2}"

# --- Setup ---

check_prerequisites
resolve_jira_env
setup_tmp_dir "$STORY_ID"

log "=== Starting high-level planning for $STORY_ID ==="

check_git_clean

# --- Guard: story must have no existing child tasks ---

existing_tasks=$(jira_get_subtasks "$STORY_ID")
task_count=$(echo "$existing_tasks" | jq 'length')

if [ "$task_count" -gt 0 ]; then
  log_error "Story $STORY_ID already has $task_count child task(s). High-level planning requires a story with no existing child tasks."
  log_error "Existing tasks:"
  echo "$existing_tasks" | jq -r '.[] | "  - \(.key): \(.fields.summary)"' >&2
  exit 1
fi

# --- Step 1: High-level plan ---

log "Step 1/3: Creating high-level plan"
run_agent "tr-high-level-plan" \
  "Create a high-level plan for Jira story $STORY_ID. Additional user context: ${USER_INPUT:-none}"

sync_story_files "$STORY_ID"

# --- Step 2: Adversarial loop (max 3 iterations) ---

log "Step 2/3: Adversarial review loop"
for iteration in 1 2 3; do
  log "Adversarial iteration $iteration/3"

  run_agent "tr-high-level-plan-review" \
    "Review the high-level plan at $TR_TMP_DIR/high-level-plan.md for story $STORY_ID."

  if is_review_clean "$TR_TMP_DIR/review.json"; then
    log "High-level plan review passed on iteration $iteration"
    break
  fi

  if [ "$iteration" -eq 3 ]; then
    log "WARNING: High-level plan still has issues after 3 adversarial iterations. Proceeding to user confirmation."
    break
  fi

  run_agent "tr-high-level-plan-fixer" \
    "Fix the issues in $TR_TMP_DIR/review.json for the high-level plan at $TR_TMP_DIR/high-level-plan.md."

  sync_story_files "$STORY_ID"
done

# --- Step 3: User confirmation ---

log "Step 3/3: User confirmation"
run_agent "tr-high-level-plan-confirm" \
  "Present the high-level plan for story $STORY_ID to the user for confirmation."

sync_story_files "$STORY_ID"

log "=== High-level planning complete for $STORY_ID ==="
