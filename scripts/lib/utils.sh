#!/usr/bin/env bash
# Shared utilities for ticket-ralph scripts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
AGENTS_DIR="$PROJECT_DIR/agents"

# --- Logging ---

log() {
  echo "[ticket-ralph] $(date '+%Y-%m-%d %H:%M:%S') $*"
}

log_error() {
  echo "[ticket-ralph] $(date '+%Y-%m-%d %H:%M:%S') ERROR: $*" >&2
}

# --- Setup ---

setup_tmp_dir() {
  local story_id="$1"
  local tmp_dir="/tmp/ticket-ralph/$story_id"
  mkdir -p "$tmp_dir"
  export TR_TMP_DIR="$tmp_dir"
  log "Tmp directory: $tmp_dir"
}

# --- Agent execution ---

run_agent() {
  local agent_name="$1"
  local prompt="$2"
  local agent_file="$AGENTS_DIR/${agent_name}.md"

  if [ ! -f "$agent_file" ]; then
    log_error "Agent file not found: $agent_file"
    log_error "Run scripts/compose.sh first to build agent files."
    exit 1
  fi

  log "--- Running agent: $agent_name ---"
  claude -p \
    --append-system-prompt "$(cat "$agent_file")" \
    "$prompt"
  local exit_code=$?

  if [ $exit_code -ne 0 ]; then
    log_error "Agent $agent_name exited with code $exit_code"
    return $exit_code
  fi

  log "--- Agent $agent_name complete ---"
}

# --- Review parsing ---

is_review_clean() {
  local review_file="$1"

  if [ ! -f "$review_file" ]; then
    log_error "Review file not found: $review_file"
    return 1
  fi

  local count
  count=$(jq 'length' "$review_file" 2>/dev/null || echo "-1")

  if [ "$count" -eq 0 ]; then
    return 0  # Clean — no issues
  else
    log "Review found $count issue(s)"
    return 1
  fi
}

# --- Validation ---

require_env() {
  local var_name="$1"
  if [ -z "${!var_name:-}" ]; then
    log_error "Required environment variable $var_name is not set"
    exit 1
  fi
}

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" &>/dev/null; then
    log_error "Required command not found: $cmd"
    exit 1
  fi
}

check_prerequisites() {
  require_command "claude"
  require_command "jq"
  require_command "curl"  # Used for Jira attachment upload/download
  require_command "git"
  require_command "jira"  # jira-cli (https://github.com/ankitpokhrel/jira-cli)
}
