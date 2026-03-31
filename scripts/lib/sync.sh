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

# Sync key story-level files to Jira
sync_story_files() {
  local story_id="$1"
  sync_to_jira "$story_id" "$TR_TMP_DIR/high-level-plan.md"
  sync_to_jira "$story_id" "$TR_TMP_DIR/progress.txt"
}

# Sync key task-level files to Jira
sync_task_files() {
  local task_id="$1"
  sync_to_jira "$task_id" "$TR_TMP_DIR/plan.md"
  sync_to_jira "$task_id" "$TR_TMP_DIR/qa-report.md"
}

# Download story-level context files from Jira to tmp
download_story_context() {
  local story_id="$1"
  sync_from_jira "$story_id" "high-level-plan.md"
  sync_from_jira "$story_id" "progress.txt"
}
