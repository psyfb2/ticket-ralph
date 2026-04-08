#!/usr/bin/env bash
# Shared utilities for ticket-ralph scripts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_DIR="$HOME/.claude/agents"

# --- Logging ---

log() {
  echo "[ticket-ralph] $(date '+%Y-%m-%d %H:%M:%S') $*"
}

log_error() {
  echo "[ticket-ralph] $(date '+%Y-%m-%d %H:%M:%S') ERROR: $*" >&2
}

# --- Jira env resolution ---

resolve_jira_env() {
  # If all three vars are already set, skip resolution.
  if [ -n "${JIRA_BASE_URL:-}" ] && [ -n "${JIRA_USER:-}" ] && [ -n "${JIRA_API_TOKEN:-}" ]; then
    return 0
  fi

  local config_file="${JIRA_CONFIG_FILE:-$HOME/.config/.jira/.config.yml}"
  if [ ! -f "$config_file" ]; then
    log "WARNING: JIRA env vars not set and jira-cli config not found at $config_file"
    return 0
  fi

  local server login api_token
  server=$(grep 'server:' "$config_file" | head -1 | awk '{print $2}' || true)
  login=$(grep 'login:' "$config_file" | head -1 | awk '{print $2}' || true)
  api_token=$(grep 'api_token:' "$config_file" | head -1 | awk '{print $2}' || true)

  if [ -z "${JIRA_BASE_URL:-}" ] && [ -n "$server" ];    then export JIRA_BASE_URL="$server"; fi
  if [ -z "${JIRA_USER:-}" ]     && [ -n "$login" ];     then export JIRA_USER="$login"; fi
  if [ -z "${JIRA_API_TOKEN:-}" ] && [ -n "$api_token" ]; then export JIRA_API_TOKEN="$api_token"; fi
}

# --- Setup ---

setup_tmp_dir() {
  local ticket_id="$1"
  local tmp_dir="$HOME/.ticket-ralph/tickets/$ticket_id"
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
    log_error "Run 'make tr-install' to build and install agent files."
    exit 1
  fi

  log "--- Running agent: $agent_name ---"
  log "--- Prompt ---"$'\n'"$prompt"$'\n'"--- End prompt ---"
  claude -p \
    --agent "$agent_name" \
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

check_git_clean() {
  if [ -n "$(git status --porcelain)" ]; then
    log_error "Git working directory is not clean. Please commit, stash, or discard changes before proceeding."
    git status --short >&2
    exit 1
  fi
}
