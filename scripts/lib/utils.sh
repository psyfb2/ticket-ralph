#!/usr/bin/env bash
# Shared utilities for ticket-ralph scripts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_DIR="$HOME/.claude/agents"

# --- Autonomous mode ---

TR_AUTONOMOUS_SCHEMA='{"type":"object","properties":{"done":{"type":"boolean","description":"true if the task completed successfully, false if you hit a blocker and need human intervention (e.g. missing context, ambiguous requirements, need access to a tool or service you cannot reach)"},"overview":{"type":"string","description":"If done=true: brief summary of what was accomplished. If done=false: clear explanation of what blocked you and what you need from the human to proceed"}},"required":["done","overview"]}'
TR_SETTINGS_FILE="$HOME/.ticket-ralph/settings.json"

is_autonomous() {
  [[ "${TR_AUTONOMOUS:-false}" == "true" ]]
}

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
  local permission_mode="${3:-acceptEdits}"
  local agent_file="$AGENTS_DIR/${agent_name}.md"

  if [ ! -f "$agent_file" ]; then
    log_error "Agent file not found: $agent_file"
    log_error "Run 'make tr-install' to build and install agent files."
    exit 1
  fi

  local cmd=(claude --agent "$agent_name")
  if is_autonomous; then
    cmd+=(--dangerously-skip-permissions)
    [ -f "$TR_SETTINGS_FILE" ] && cmd+=(--settings "$TR_SETTINGS_FILE")
    log "--- Running agent: $agent_name (autonomous, interactive) ---"
  else
    cmd+=(--permission-mode "$permission_mode")
    log "--- Running agent: $agent_name (permission-mode: $permission_mode) ---"
  fi
  cmd+=("$prompt")

  log "--- Prompt ---"$'\n'"$prompt"$'\n'"--- End prompt ---"
  "${cmd[@]}"
  local exit_code=$?

  if [ $exit_code -ne 0 ]; then
    log_error "Agent $agent_name exited with code $exit_code"
    return $exit_code
  fi

  log "--- Agent $agent_name complete ---"
}

# Runs an agent non-interactively with -p and stream-json for observability.
# Streams text deltas to stderr in real-time. If json_schema is provided,
# extracts structured_output from the result event and echoes it to stdout.
run_agent_autonomous() {
  local agent_name="$1"
  local prompt="$2"
  local json_schema="${3:-}"
  local agent_file="$AGENTS_DIR/${agent_name}.md"

  if [ ! -f "$agent_file" ]; then
    log_error "Agent file not found: $agent_file"
    log_error "Run 'make tr-install' to build and install agent files."
    exit 1
  fi

  log "--- Running agent (autonomous, non-interactive): $agent_name ---"
  log "--- Prompt ---"$'\n'"$prompt"$'\n'"--- End prompt ---"

  local tmp_stream
  tmp_stream=$(mktemp)

  local cmd=(claude -p --agent "$agent_name" --dangerously-skip-permissions
    --output-format stream-json --verbose --include-partial-messages)
  [ -f "$TR_SETTINGS_FILE" ] && cmd+=(--settings "$TR_SETTINGS_FILE")
  [ -n "$json_schema" ] && cmd+=(--json-schema "$json_schema")
  cmd+=("$prompt")

  # Stream text deltas to stderr for observability, save full stream to temp file.
  # || true prevents set -e from exiting on claude failure; PIPESTATUS[0] still
  # holds the real exit code so we can handle it explicitly below.
  "${cmd[@]}" | tee "$tmp_stream" \
    | jq -rj 'select(.type == "stream_event" and .event.delta.type? == "text_delta") | .event.delta.text' >&2 \
    || true

  local exit_code=${PIPESTATUS[0]}

  # Extract structured output from result event → stdout
  if [ -n "$json_schema" ]; then
    jq -c 'select(.type == "result") | .structured_output' "$tmp_stream"
  fi
  rm -f "$tmp_stream"

  if [ $exit_code -ne 0 ]; then
    log_error "Agent $agent_name exited with code $exit_code"
    return $exit_code
  fi

  log "--- Agent $agent_name (autonomous) complete ---"
}

# Parses the structured JSON result from run_agent_autonomous and exits with
# code 2 if the agent reported a blocker (done=false). Writes the overview to
# $TR_TMP_DIR/.blocker-overview for task-loop.sh to read.
check_autonomous_result() {
  local result="$1"
  local agent_name="$2"
  local done overview

  if [ -z "$result" ] || [ "$result" = "null" ]; then
    log_error "Agent $agent_name produced no structured output — cannot determine completion status"
    exit 1
  fi

  done=$(echo "$result" | jq -r '.done')
  overview=$(echo "$result" | jq -r '.overview')
  if [ "$done" = "false" ]; then
    log_error "Agent $agent_name reported blocker: $overview"
    echo "$overview" > "$TR_TMP_DIR/.blocker-overview"
    exit 2
  fi
  log "Agent $agent_name completed: $overview"
}

# Sends a macOS notification via terminal-notifier when an agent hits a blocker.
notify_blocker() {
  local ticket_id="$1"
  local message="$2"
  if command -v terminal-notifier &>/dev/null; then
    terminal-notifier \
      -title "ticket-ralph: Blocker ($ticket_id)" \
      -message "$message" \
      -sound default
  else
    log "WARNING: terminal-notifier not installed, skipping notification"
  fi
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
