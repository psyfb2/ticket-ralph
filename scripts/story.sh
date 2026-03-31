#!/usr/bin/env bash
# story.sh — Orchestrates high-level planning for a Jira story.
#
# Flow:
#   1. Git hygiene agent
#   2. High-level plan agent
#   3. Adversarial loop (max 3 iterations):
#        - High-level plan review agent
#        - High-level plan fixer agent
#   4. High-level plan user confirmation agent
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
setup_tmp_dir "$STORY_ID"

log "=== Starting high-level planning for $STORY_ID ==="

# --- Step 1: Git hygiene ---

log "Step 1/4: Git hygiene"
run_agent "tr-git-hygiene" \
  "Ensure the git working directory is clean before we start work on story $STORY_ID."

# --- Step 2: High-level plan ---

log "Step 2/4: Creating high-level plan"
run_agent "tr-high-level-plan" \
  "Create a high-level plan for Jira story $STORY_ID. Additional user context: ${USER_INPUT:-none}"

sync_story_files "$STORY_ID"

# --- Step 3: Adversarial loop (max 3 iterations) ---

log "Step 3/4: Adversarial review loop"
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

# --- Step 4: User confirmation ---

log "Step 4/4: User confirmation"
run_agent "tr-high-level-plan-confirm" \
  "Present the high-level plan for story $STORY_ID to the user for confirmation."

sync_story_files "$STORY_ID"

log "=== High-level planning complete for $STORY_ID ==="
