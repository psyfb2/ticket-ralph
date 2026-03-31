---
name: tr-high-level-plan-review
description: Adversarial review of a high-level architectural plan for feasibility, correctness, and completeness
---

## Your Task

Adversarially review the high-level plan at `$TR_TMP_DIR/high-level-plan.md` for the Jira story `$TR_STORY_ID`.

### Process

1. Read the high-level plan from `$TR_TMP_DIR/high-level-plan.md`
2. Use the Jira skill to read the original story requirements
3. Explore the codebase (read-only) to verify the plan's assumptions

### Review Criteria

Evaluate the plan against each of these criteria:

- **Feasibility**: Can this actually be built with the current codebase and infrastructure?
- **Completeness**: Does the plan address ALL requirements from the Jira story? Are any requirements missed?
- **Correctness**: Are the architectural assumptions valid? Does the approach work with the existing code?
- **SOLID compliance**: Does the approach violate any SOLID principles?
- **Architectural integrity**: Does the plan respect existing patterns? Does it introduce unnecessary complexity?
- **Task granularity**: Is each task small, self-contained, and limited to one repo?
- **Task dependencies**: Are dependencies correctly identified? Are there missing dependencies or cycles?
- **Risks**: Are risks and assumptions adequately documented? Are there unidentified risks?
- **Achievability**: Is the overall scope realistic?

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

- Be specific — reference exact sections of the plan
- Every issue MUST have a concrete, actionable suggestion
- Do not nitpick style — focus on substantive issues
- **high**: Missing requirements, wrong assumptions, infeasible approach, architectural violations
- **medium**: Unclear steps, missing dependencies, underestimated complexity
- **low**: Minor improvements, documentation gaps
