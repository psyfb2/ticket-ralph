#!/usr/bin/env bash
# Fetches Jira ticket data and writes it to $TR_TMP_DIR/ticket-context.json.
# If the ticket is a child of a Story (via "Parent/Child" issuelink), also
# fetches the parent story context to parent-context.json.
# Deterministic task — no agent needed, saves tokens.
#
# Requires: lib/jira.sh and lib/utils.sh to be sourced first.
# Requires: TR_TMP_DIR to be set.
#
# Output: $TR_TMP_DIR/ticket-context.json with shape:
# {
#   "ticketId": "PROJ-123",
#   "issueType": "Task",
#   "summary": "...",
#   "description": "...",
#   "comments": [...],
#   "attachments": [{"filename": "...", "localPath": "..."}],
#   "parentStoryKey": "PROJ-100" | null
# }
#
# If parent story exists: $TR_TMP_DIR/parent-context.json (same shape, no attachments downloaded)

# Fetches issue data and downloads attachments.
# Args: $1 = issue ID, $2 = output file path, $3 = "true" to download attachments (default: "true")
_fetch_ticket_json() {
  local issue_id="$1"
  local output_path="$2"
  local download_attachments="${3:-true}"

  local issue_json
  issue_json=$(jira_get_issue "$issue_id")

  local summary description issue_type parent_story_key
  summary=$(echo "$issue_json" | jq -r '.fields.summary // ""')
  description=$(echo "$issue_json" | jq -r '.fields.description // ""')
  issue_type=$(echo "$issue_json" | jq -r '.fields.issuetype.name // ""')
  parent_story_key=$(jira_get_parent_story_key "$issue_json")

  # Extract comments
  local comments
  comments=$(echo "$issue_json" | jq '[
    .fields.comment.comments // []
    | .[]
    | {author: .author.displayName, body: .body, created: .created}
  ]')

  # Extract attachment metadata
  local attachments_meta
  attachments_meta=$(echo "$issue_json" | jq '[.fields.attachment // [] | .[] | {filename, content}]')

  local attachments_result="[]"
  local attachment_count
  attachment_count=$(echo "$attachments_meta" | jq 'length')

  if [ "$attachment_count" -gt 0 ] && [ "$download_attachments" = "true" ]; then
    log "Downloading $attachment_count attachment(s) for $issue_id"

    local base_url auth
    base_url=$(_jira_base_url)
    auth=$(_jira_attachment_auth)

    attachments_result="["
    local first=true

    for i in $(seq 0 $((attachment_count - 1))); do
      local filename content_url local_path
      filename=$(echo "$attachments_meta" | jq -r ".[$i].filename")
      content_url=$(echo "$attachments_meta" | jq -r ".[$i].content")
      local_path="$TR_TMP_DIR/$filename"

      if [ -n "$auth" ] && [ -n "$base_url" ]; then
        if curl -s -f -L \
            -H "Authorization: $auth" \
            -o "$local_path" \
            "$content_url"; then
          log "Downloaded attachment: $filename"
        else
          log "WARNING: Failed to download $filename — skipping"
          continue
        fi
      fi

      if [ "$first" = true ]; then
        first=false
      else
        attachments_result+=","
      fi
      attachments_result+="{\"filename\":$(printf '%s' "$filename" | jq -Rs .),\"localPath\":$(printf '%s' "$local_path" | jq -Rs .)}"
    done

    attachments_result+="]"
  elif [ "$attachment_count" -gt 0 ]; then
    # List attachments without downloading
    attachments_result=$(echo "$attachments_meta" | jq '[.[] | {filename}]')
  fi

  # Build context JSON
  jq -n \
    --arg ticketId "$issue_id" \
    --arg issueType "$issue_type" \
    --arg summary "$summary" \
    --arg description "$description" \
    --argjson comments "$comments" \
    --argjson attachments "$attachments_result" \
    --arg parentStoryKey "$parent_story_key" \
    '{
      ticketId: $ticketId,
      issueType: $issueType,
      summary: $summary,
      description: $description,
      comments: $comments,
      attachments: $attachments,
      parentStoryKey: (if $parentStoryKey == "" then null else $parentStoryKey end)
    }' > "$output_path"
}

fetch_ticket_context() {
  local ticket_id="$1"

  log "Fetching Jira ticket data for $ticket_id"

  _fetch_ticket_json "$ticket_id" "$TR_TMP_DIR/ticket-context.json" "true"
  log "Ticket context written to $TR_TMP_DIR/ticket-context.json"

  # If ticket is a child of a Story, fetch parent story context (without downloading attachments)
  local parent_story_key
  parent_story_key=$(jq -r '.parentStoryKey // empty' "$TR_TMP_DIR/ticket-context.json")

  if [ -n "$parent_story_key" ]; then
    log "Ticket is child of story $parent_story_key — fetching story context"
    _fetch_ticket_json "$parent_story_key" "$TR_TMP_DIR/parent-context.json" "false"
    log "Parent story context written to $TR_TMP_DIR/parent-context.json"
  fi
}
