#!/usr/bin/env bash
# PreToolUse hook for tr-high-level-plan agent.
# Restricts Edit/Write operations to /tmp/ticket-ralph/ only.

file_path=$(cat | jq -r '.tool_input.file_path // empty')

[[ -z "$file_path" ]] && exit 0
[[ "$file_path" == /tmp/ticket-ralph/* ]] && exit 0

echo "Blocked: writes are restricted to /tmp/ticket-ralph/ (attempted: $file_path)"
exit 2
