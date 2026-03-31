## File Conventions

All working files are stored in `$TR_TMP_DIR` (resolves to `/tmp/ticket-ralph/<STORY_ID>/`).

### Key Files

| File | Synced To | Description |
|------|-----------|-------------|
| `high-level-plan.md` | Jira story | High-level architectural plan for the story |
| `progress.txt` | Jira story | Cross-task learnings, patterns, gotchas |
| `plan.md` | Jira task | Detailed implementation plan for a single task |
| `task-id.txt` | Local only | The Jira task ID selected by the plan agent |
| `risk-level.txt` | Local only | Risk classification (`low`, `medium`, or `high`) |
| `review.json` | Local only | Adversarial review output (JSON array) |
| `qa-report.md` | Jira task | QA verification report |
| `qa-status.json` | Local only | QA pass/fail: `{"readyToMerge": true/false}` |

### Rules

- Always write files to `$TR_TMP_DIR` — the orchestration scripts handle syncing to Jira
- Use the exact filenames listed above — the scripts depend on them
- JSON files must be valid JSON — the orchestration scripts parse them with `jq`
