#!/usr/bin/env bash
# task.sh — Orchestrates completion of a single Jira task within a story.
#
# Flow:
#   1. Plan agent (picks next task, creates plan, classifies risk)
#   2. Plan adversarial loop (max 3, skipped for low risk)
#   3. Plan user confirmation (only for high risk, or if TR_ALWAYS_CONFIRM=true)
#   4. Implementor agent
#   5. Implementation adversarial loop (max 3, skipped for low risk)
#   6. QA adversarial loop (max 3, always runs)
#
# Usage: ./scripts/task.sh <JIRA_STORY_ID> [extra details for the agent]
#
# Environment variables:
#   JIRA_BASE_URL      — Jira instance URL
#   JIRA_USER          — Jira username/email
#   JIRA_API_TOKEN     — Jira API token
#   TR_ALWAYS_CONFIRM  — If "true", always confirm plans regardless of risk (default: false). Orchestrator-only.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib/utils.sh"
source "$SCRIPT_DIR/lib/jira.sh"
source "$SCRIPT_DIR/lib/sync.sh"

# --- Args ---

STORY_ID="${1:?Usage: task.sh <JIRA_STORY_ID> [extra details]}"
USER_INPUT="${*:2}"

# --- Setup ---

check_prerequisites
setup_tmp_dir "$STORY_ID"

ALWAYS_CONFIRM="${TR_ALWAYS_CONFIRM:-false}"

log "=== Starting task execution for story $STORY_ID ==="

# Download story context from Jira
download_story_context "$STORY_ID"

# =====================================================================
# Step 1: Plan agent — picks next task, creates plan, classifies risk
# =====================================================================

log "Step 1/6: Planning"
run_agent "tr-plan" \
  "Pick the next task for story $STORY_ID and create a detailed plan. Additional user context: ${USER_INPUT:-none}"

# Read task ID and risk level from agent output
TASK_ID=$(cat "$TR_TMP_DIR/task-id.txt" 2>/dev/null || echo "")
RISK_LEVEL=$(cat "$TR_TMP_DIR/risk-level.txt" 2>/dev/null || echo "medium")

if [ -z "$TASK_ID" ]; then
  log "No tasks available to pick up. All tasks may be done, blocked, or in review."
  exit 0
fi

log "Selected task: $TASK_ID (risk: $RISK_LEVEL)"

sync_task_files "$TASK_ID"
sync_to_jira "$STORY_ID" "$TR_TMP_DIR/progress.txt"

# =====================================================================
# Step 2: Plan adversarial loop (skip for low risk)
# =====================================================================

if [ "$RISK_LEVEL" != "low" ]; then
  log "Step 2/6: Plan adversarial review (risk=$RISK_LEVEL)"
  for iteration in 1 2 3; do
    log "Plan adversarial iteration $iteration/3"

    run_agent "tr-plan-review" \
      "Review the plan at $TR_TMP_DIR/plan.md for task $TASK_ID (story $STORY_ID)."

    if is_review_clean "$TR_TMP_DIR/review.json"; then
      log "Plan review passed on iteration $iteration"
      break
    fi

    if [ "$iteration" -eq 3 ]; then
      log "WARNING: Plan still has issues after 3 adversarial iterations."
      break
    fi

    run_agent "tr-plan-fixer" \
      "Fix the issues in $TR_TMP_DIR/review.json for the plan at $TR_TMP_DIR/plan.md."

    sync_task_files "$TASK_ID"
  done
else
  log "Step 2/6: Plan adversarial review SKIPPED (risk=low)"
fi

# =====================================================================
# Step 3: Plan user confirmation (high risk or TR_ALWAYS_CONFIRM)
# =====================================================================

if [ "$RISK_LEVEL" = "high" ] || [ "$ALWAYS_CONFIRM" = "true" ]; then
  log "Step 3/6: Plan user confirmation (risk=$RISK_LEVEL)"
  run_agent "tr-plan-confirm" \
    "Present the plan for task $TASK_ID to the user for confirmation. Risk level: $RISK_LEVEL."

  sync_task_files "$TASK_ID"
else
  log "Step 3/6: Plan user confirmation SKIPPED (risk=$RISK_LEVEL, always_confirm=$ALWAYS_CONFIRM)"
fi

# =====================================================================
# Step 4: Implementation
# =====================================================================

log "Step 4/6: Implementation"
run_agent "tr-implementor" \
  "Implement the plan at $TR_TMP_DIR/plan.md for task $TASK_ID (story $STORY_ID)."

sync_to_jira "$STORY_ID" "$TR_TMP_DIR/progress.txt"

# =====================================================================
# Step 5: Implementation adversarial loop (skip for low risk)
# =====================================================================

if [ "$RISK_LEVEL" != "low" ]; then
  log "Step 5/6: Implementation adversarial review (risk=$RISK_LEVEL)"
  for iteration in 1 2 3; do
    log "Implementation adversarial iteration $iteration/3"

    run_agent "tr-impl-review" \
      "Review the implementation for task $TASK_ID (story $STORY_ID)."

    if is_review_clean "$TR_TMP_DIR/review.json"; then
      log "Implementation review passed on iteration $iteration"
      break
    fi

    if [ "$iteration" -eq 3 ]; then
      log "WARNING: Implementation still has issues after 3 adversarial iterations."
      break
    fi

    run_agent "tr-impl-review-fixer" \
      "Fix the issues in $TR_TMP_DIR/review.json for the implementation of task $TASK_ID."
  done
else
  log "Step 5/6: Implementation adversarial review SKIPPED (risk=low)"
fi

# =====================================================================
# Step 6: QA adversarial loop (always runs)
# =====================================================================

log "Step 6/6: QA"
QA_READY="false"

for iteration in 1 2 3; do
  log "QA iteration $iteration/3"

  run_agent "tr-qa" \
    "Perform QA on the implementation for task $TASK_ID (story $STORY_ID)."

  # Read QA status
  if [ -f "$TR_TMP_DIR/qa-status.json" ]; then
    QA_READY=$(jq -r '.readyToMerge // false' "$TR_TMP_DIR/qa-status.json")
  fi

  if [ "$QA_READY" = "true" ]; then
    log "QA passed on iteration $iteration"
    sync_task_files "$TASK_ID"
    break
  fi

  if [ "$iteration" -eq 3 ]; then
    log "WARNING: QA still failing after 3 iterations."
    sync_task_files "$TASK_ID"
    break
  fi

  run_agent "tr-qa-fixer" \
    "Fix the QA issues documented in $TR_TMP_DIR/qa-report.md for task $TASK_ID."
done

# =====================================================================
# Summary
# =====================================================================

echo ""
if [ "$QA_READY" = "true" ]; then
  log "=== Task $TASK_ID completed successfully ==="
  log "PR created, task moved to IN REVIEW."
  log "A human must review and merge the PR before dependent tasks can proceed."
else
  log "=== Task $TASK_ID has unresolved issues ==="
  log "See QA report: $TR_TMP_DIR/qa-report.md"
fi
