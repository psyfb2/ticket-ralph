---
name: tr-impl-review-fixer
description: Fixes issues found by the adversarial review of a task implementation
---

## Your Task

Fix the issues identified in `$TR_TMP_DIR/review.json` for the implementation of Jira task `$TR_TASK_ID`.

### Process

1. Read the review issues from `$TR_TMP_DIR/review.json`
2. Read `$TR_TMP_DIR/plan.md` for context on what was intended
3. Read the Jira task for the original requirements
4. For each issue, understand the problem and apply the fix

### For Each Issue

- Read the affected file(s) in full
- Apply the suggested fix or a better alternative
- Verify the fix:
  - Run IDE diagnostics
  - Compile/build
  - Run the relevant test subset
  - Check test coverage (100% of new non-IaC code)
  - Run linters
- Commit the fix with a clear conventional commit message

### Rules

- Address ALL high and medium severity issues
- Low severity issues should be addressed if straightforward
- Do not introduce new problems while fixing existing ones
- Do not change the implementation approach — fix within the existing pattern
- If a fix requires changes that conflict with the plan, document why in a Jira comment
- Verify each fix individually before moving to the next
