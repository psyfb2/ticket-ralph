#!/usr/bin/env bash
# Jira CLI helpers for ticket-ralph orchestration scripts.
# Uses jira-cli (https://github.com/ankitpokhrel/jira-cli).
# Attachment upload/download uses curl since jira-cli doesn't support attachments.

# --- Read operations ---

jira_get_issue() {
  local issue_id="$1"
  jira issue view "$issue_id" --raw
}

jira_get_issue_status() {
  local issue_id="$1"
  jira issue view "$issue_id" --raw | jq -r '.fields.status.name'
}

jira_get_issue_type() {
  local issue_id="$1"
  jira issue view "$issue_id" --raw | jq -r '.fields.issuetype.name'
}

jira_get_parent_story_key() {
  # Returns the parent Story key via "Parent/Child" issuelinks, or empty if none.
  # Only matches links where the inward issue is a Story (not Epic, Task, etc.).
  local issue_json="$1"
  echo "$issue_json" | jq -r '
    [.fields.issuelinks // []
     | .[]
     | select(.type.inward == "Child of")
     | .inwardIssue
     | select(.fields.issuetype.name == "Story")
     | .key
    ] | first // empty'
}

jira_get_subtasks() {
  local parent_id="$1"
  local project="${parent_id%%-*}"
  local raw
  raw=$(jira issue list -p "$project" -P "$parent_id" --raw 2>/dev/null) || true
  echo "${raw:-"{}"}" | jq '.issues // []'
}

jira_get_todo_tasks() {
  local parent_id="$1"
  local project="${parent_id%%-*}"
  local raw
  raw=$(jira issue list -p "$project" -P "$parent_id" -s "To Do" --raw 2>/dev/null) || true
  echo "${raw:-"{}"}" | jq '.issues // []'
}

# --- Write operations ---

jira_transition_issue() {
  local issue_id="$1"
  local status="$2"
  jira issue move "$issue_id" "$status"
  log "Transitioned $issue_id to '$status'"
}

jira_create_subtask() {
  local parent_id="$1"
  local summary="$2"
  local description="${3:-}"
  local project
  project=$(echo "$parent_id" | cut -d'-' -f1)

  local args=(
    jira issue create
    --raw
    --no-input
    -p "$project"
    -t "Sub-task"
    -P "$parent_id"
    -s "$summary"
  )

  if [ -n "$description" ]; then
    args+=(-b "$description")
  fi

  "${args[@]}"
}

jira_link_issues() {
  # Links two issues. e.g., jira_link_issues PROJ-2 PROJ-1 "Blocks"
  # means PROJ-2 blocks PROJ-1
  local inward_key="$1"
  local outward_key="$2"
  local link_type="${3:-Blocks}"
  jira issue link "$inward_key" "$outward_key" "$link_type"
  log "Linked $inward_key -> $outward_key ($link_type)"
}

jira_add_comment() {
  local issue_id="$1"
  local comment="$2"
  jira issue comment add "$issue_id" "$comment"
}

# --- Attachment operations (uses curl — jira-cli doesn't support attachments) ---

_jira_attachment_auth() {
  # Resolves each credential independently: env var first, then jira-cli config
  local user="${JIRA_USER:-}"
  local token="${JIRA_API_TOKEN:-}"

  if [ -z "$user" ] || [ -z "$token" ]; then
    local config_file="${JIRA_CONFIG_FILE:-$HOME/.config/.jira/.config.yml}"
    if [ -f "$config_file" ]; then
      [ -z "$user" ]  && user=$(grep 'login:'     "$config_file" | head -1 | awk '{print $2}')
      [ -z "$token" ] && token=$(grep 'api_token:' "$config_file" | head -1 | awk '{print $2}')
    fi
  fi

  if [ -n "$user" ] && [ -n "$token" ]; then
    echo "Basic $(echo -n "${user}:${token}" | base64)"
  fi
}

_jira_base_url() {
  if [ -n "${JIRA_BASE_URL:-}" ]; then
    echo "$JIRA_BASE_URL"
  else
    local config_file="${JIRA_CONFIG_FILE:-$HOME/.config/.jira/.config.yml}"
    if [ -f "$config_file" ]; then
      grep 'server:' "$config_file" | head -1 | awk '{print $2}'
    fi
  fi
}

jira_upload_attachment() {
  local issue_id="$1"
  local file_path="$2"

  if [ ! -f "$file_path" ]; then
    log "WARNING: File not found, skipping upload: $file_path"
    return 0
  fi

  local base_url auth
  base_url=$(_jira_base_url)
  auth=$(_jira_attachment_auth)

  if [ -z "$base_url" ] || [ -z "$auth" ]; then
    log "WARNING: Cannot upload attachment — missing Jira credentials or base URL"
    return 1
  fi

  curl -s -f \
    -X POST \
    -H "Authorization: $auth" \
    -H "X-Atlassian-Token: no-check" \
    -F "file=@${file_path}" \
    "${base_url}/rest/api/2/issue/${issue_id}/attachments" >/dev/null

  log "Uploaded $(basename "$file_path") to $issue_id"
}

jira_download_attachment() {
  local issue_id="$1"
  local filename="$2"
  local output_path="$3"

  local base_url auth
  base_url=$(_jira_base_url)
  auth=$(_jira_attachment_auth)

  if [ -z "$base_url" ] || [ -z "$auth" ]; then
    log "WARNING: Cannot download attachment — missing Jira credentials or base URL"
    return 1
  fi

  # Get attachments for the issue
  local attachments_json
  attachments_json=$(curl -s -f \
    -H "Authorization: $auth" \
    -H "Content-Type: application/json" \
    "${base_url}/rest/api/2/issue/${issue_id}?fields=attachment" | jq -r '.fields.attachment')

  # Find the most recent attachment matching the filename
  local url
  url=$(echo "$attachments_json" | jq -r --arg fname "$filename" '[.[] | select(.filename == $fname)] | sort_by(.created) | last | .content // empty')

  if [ -n "$url" ]; then
    curl -s -f -L \
      -H "Authorization: $auth" \
      -o "$output_path" \
      "$url"
    log "Downloaded $filename from $issue_id"
  else
    log "Attachment '$filename' not found on $issue_id (may not exist yet)"
  fi
}

# --- Dependency checking ---

jira_has_blocked_dependencies() {
  # Returns 0 (true) if the task has blockers that are NOT in DONE status.
  local task_id="$1"

  local issue_json
  issue_json=$(jira_get_issue "$task_id")

  local blockers_not_done
  blockers_not_done=$(echo "$issue_json" | jq '[
    .fields.issuelinks // []
    | .[]
    | select(.type.inward == "is blocked by")
    | select(.inwardIssue.fields.status.name != "Done" and .inwardIssue.fields.status.name != "DONE")
    | .inwardIssue.key
  ] | length')

  [ "${blockers_not_done:-0}" -gt 0 ]
}
