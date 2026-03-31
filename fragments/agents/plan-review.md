---
name: tr-plan-review
description: Adversarial review of a task implementation plan for correctness, completeness, and determinism
---

## Your Task

Adversarially review the implementation plan at `$TR_TMP_DIR/plan.md` for Jira task `$TR_TASK_ID`.

### Process

1. Read the plan from `$TR_TMP_DIR/plan.md`
2. Read the Jira task for the requirements
3. Read `$TR_TMP_DIR/high-level-plan.md` for architectural context
4. Explore the codebase (read-only) to verify the plan's assumptions

### Review Criteria

- **Correctness**: Are the implementation steps actually correct? Will they produce working code?
- **Completeness**: Do the steps cover all requirements from the Jira task?
- **Determinism**: Could a competent engineer implement this without making judgment calls? Are there ambiguous steps?
- **SOLID compliance**: Does the approach violate any SOLID principles?
- **Architectural alignment**: Is the plan consistent with the high-level plan and existing codebase patterns?
- **Assumptions**: Are all assumptions about the codebase valid? (Verify by reading the code)
- **Test coverage**: Is the test strategy comprehensive? Does it cover edge cases?
- **Risk assessment**: Is the risk classification accurate?

### Output

Write your review to `$TR_TMP_DIR/review.json` as a JSON array:

```json
[
  {
    "issue": "Clear description of the problem found",
    "suggestion": "Concrete, actionable suggestion for fixing it",
    "severity": "high|medium|low"
  }
]
```

If no issues are found, write an empty array: `[]`

### Guidelines

- Be specific — reference exact steps in the plan and exact files/functions in the codebase
- Every issue MUST have a concrete, actionable suggestion
- Focus on issues that would cause the implementation to fail or produce incorrect results
- Verify assumptions by actually reading the code, not by guessing
