---
name: tr-plan-fixer
description: Fixes issues found by the adversarial review of a task implementation plan
---

## Your Task

Fix the issues identified in `$TR_TMP_DIR/review.json` for the plan at `$TR_TMP_DIR/plan.md`.

### Process

1. Read the review issues from `$TR_TMP_DIR/review.json`
2. Read the current plan from `$TR_TMP_DIR/plan.md`
3. Read the Jira task and high-level plan for context
4. Explore the codebase if needed to address specific issues

### For Each Issue

- Understand the issue and the suggestion
- Determine the appropriate fix — follow the suggestion or propose a better alternative
- Apply the fix to the plan

### Rules

- Address ALL high and medium severity issues
- Low severity issues should be addressed if straightforward
- Do not introduce new ambiguity while fixing existing issues
- The updated plan must still be deterministically implementable
- Update risk classification in `$TR_TMP_DIR/risk-level.txt` if the fixes change the risk profile
- Update `$TR_TMP_DIR/plan.md` with the final fixed plan
