#!/usr/bin/env bash
# File sync between local tmp directory and Jira attachments.
# Called by orchestration scripts after each agent completes.
# Requires lib/jira.sh and lib/utils.sh to be sourced first.

sync_to_jira() {
  local issue_id="$1"
  local file_path="$2"

  if [ -f "$file_path" ]; then
    log "Syncing $(basename "$file_path") -> Jira $issue_id"
    jira_upload_attachment "$issue_id" "$file_path"
  fi
}

sync_from_jira() {
  local issue_id="$1"
  local filename="$2"
  local output_path="${3:-${TR_TMP_DIR}/${filename}}"

  log "Syncing Jira $issue_id -> $filename"
  jira_download_attachment "$issue_id" "$filename" "$output_path"
}

# Sync key ticket-level files to Jira
sync_ticket_files() {
  local ticket_id="$1"
  sync_to_jira "$ticket_id" "$TR_TMP_DIR/PRD.json"
  sync_to_jira "$ticket_id" "$TR_TMP_DIR/progress.txt"
}

# Download ticket-level context files from Jira to tmp
download_ticket_context() {
  local ticket_id="$1"
  sync_from_jira "$ticket_id" "PRD.json"
  sync_from_jira "$ticket_id" "progress.txt"
}
