#!/usr/bin/env bash
# task-loop.sh — Runs task.sh in a loop until all PRD tasks are complete.
#
# Calls task.sh repeatedly until every task in PRD.json is marked done.
# Max iterations = 2 × original task count to accommodate rare mid-run task additions.
# Exits non-zero if the safeguard is reached before all tasks complete.
#
# Usage: ./scripts/task-loop.sh <JIRA_TICKET_ID> [extra details for the agent]
#
# Environment variables: same as task.sh (JIRA_BASE_URL, JIRA_USER, JIRA_API_TOKEN)

set -euo pipefail

LOOP_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$LOOP_SCRIPT_DIR/lib/utils.sh"

TICKET_ID="${1:?Usage: task-loop.sh <JIRA_TICKET_ID> [extra details]}"

setup_tmp_dir "$TICKET_ID"
PRD_FILE="$TR_TMP_DIR/PRD.json"

iteration=0
max_iterations=0

log "=== Starting task loop for $TICKET_ID ==="

while true; do
  iteration=$((iteration + 1))
  log "--- Task loop iteration $iteration ---"

  task_exit=0
  "$LOOP_SCRIPT_DIR/task.sh" "$@" || task_exit=$?

  if [ "$task_exit" -eq 2 ] && is_autonomous; then
    overview=$(cat "$TR_TMP_DIR/.blocker-overview" 2>/dev/null || echo "Unknown blocker")
    log_error "AUTONOMOUS: Agent hit a blocker on iteration $iteration"
    log_error "Overview: $overview"
    notify_blocker "$TICKET_ID" "$overview"
    exit 2
  elif [ "$task_exit" -ne 0 ]; then
    log_error "task.sh failed on iteration $iteration (exit code: $task_exit)"
    exit 1
  fi

  # After the first successful call PRD.json is guaranteed to exist locally.
  # Read total task count once to establish the iteration safeguard.
  if [ "$iteration" -eq 1 ]; then
    if [ ! -f "$PRD_FILE" ]; then
      log_error "PRD.json not found at $PRD_FILE after task.sh completed successfully"
      exit 1
    fi
    initial_tasks=$(jq '.tasks | length' "$PRD_FILE")
    # Double iterations as tasks could (rarely) be added mid-implementation
    max_iterations=$((initial_tasks * 2))
    log "Initial task count: $initial_tasks — max iterations set to $max_iterations"
  fi

  remaining=$(jq '[.tasks[] | select(.done == false)] | length' "$PRD_FILE")

  if [ "$remaining" -eq 0 ]; then
    log "=== All tasks complete after $iteration iteration(s) for $TICKET_ID ==="
    exit 0
  fi

  log "$remaining task(s) remaining after iteration $iteration."

  if [ "$iteration" -ge "$max_iterations" ]; then
    log_error "Reached max iterations ($max_iterations) with $remaining task(s) still incomplete. Aborting."
    exit 1
  fi
done
