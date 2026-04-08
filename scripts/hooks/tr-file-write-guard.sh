#!/usr/bin/env bash
# PreToolUse hook for tr-high-level-plan agent.
# Restricts Edit/Write operations to $TR_TMP_DIR only.

file_path=$(cat | jq -r '.tool_input.file_path // empty')

[[ -z "$file_path" ]] && exit 0
[[ -z "${TR_TMP_DIR:-}" ]] && { echo "Blocked: TR_TMP_DIR is not set"; exit 2; }
[[ "$file_path" == "$TR_TMP_DIR"/* ]] && exit 0

echo "Blocked: writes are restricted to ${TR_TMP_DIR} (attempted: $file_path)"
exit 2
