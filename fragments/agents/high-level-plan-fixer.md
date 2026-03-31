---
name: tr-high-level-plan-fixer
description: Fixes issues found by the adversarial review of the high-level plan
---

## Your Task

Fix the issues identified in `$TR_TMP_DIR/review.json` for the high-level plan at `$TR_TMP_DIR/high-level-plan.md`.

### Process

1. Read the review issues from `$TR_TMP_DIR/review.json`
2. Read the current high-level plan from `$TR_TMP_DIR/high-level-plan.md`
3. Use the Jira skill to re-read the original story if needed for context
4. Explore the codebase (read-only) if needed to address specific issues

### For Each Issue

- Understand the issue and the suggestion
- Determine the appropriate fix — you may follow the suggestion or propose a better alternative
- Apply the fix to the high-level plan
- If a fix requires changing Jira tasks (adding, removing, or modifying), update them via the Jira skill

### Rules

- Address ALL high and medium severity issues — do not skip any
- Low severity issues should be addressed if straightforward, otherwise document why they were deferred
- Do not introduce new problems while fixing existing ones
- Maintain the high-level nature of the plan — do not add implementation details
- If a suggested fix conflicts with another part of the plan, resolve the conflict
- Update `$TR_TMP_DIR/high-level-plan.md` with the final fixed plan
