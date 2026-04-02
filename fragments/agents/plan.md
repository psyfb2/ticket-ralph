---
name: tr-plan
description: >
  Architect agent that reads a Jira task, which has a parent story with
  a high-level-plan.md and progress.txt file uploaded as attachments. 
  It then explores the codebase, produces a plan and creates a branch.
model: claude-opus-4-6
agentMetadata:
  hooks:
    PreToolUse:
      - matcher: "Edit|Write"
        hooks:
          - type: command
            command: "bash ~/.claude/hooks/tr-file-write-guard.sh"
---

{{role}}

