---
name: tr-impl-review
description: Adversarial review of a task implementation for correctness, quality, and requirement coverage
---

## Your Task

Adversarially review the implementation for Jira task `$TR_TASK_ID`.

### Process

1. Read the plan from `$TR_TMP_DIR/plan.md` to understand what should have been implemented
2. Read the Jira task for the original requirements
3. Read `storyBranch` and `taskBranch` from `$TR_TMP_DIR/ticket-ralph-state.json`, then use `git diff <storyBranch>...<taskBranch>` to see all changes made
4. Read the changed files in full to understand context
5. Run verification checks:
   - IDE diagnostics
   - Compile/build
   - Run tests
   - Check test coverage

### Review Criteria

- **Correctness**: Does the implementation actually work? Does it match the plan?
- **Requirement coverage**: Are ALL requirements from the Jira task met?
- **Test coverage**: Are all new code paths tested? Are edge cases covered?
- **SOLID compliance**: Any violations introduced?
- **Code quality**: Is the code clean, readable, and following codebase conventions?
- **Security**: Any hardcoded secrets, injection vulnerabilities, or OWASP Top 10 issues?
- **Regressions**: Could these changes break existing functionality?
- **Unnecessary changes**: Are there changes beyond what the plan/task required?

### Output

Write your review to `$TR_TMP_DIR/review.json` as a JSON array:

```json
[
  {
    "file": "path/to/file.py",
    "issue": "Clear description of the problem",
    "suggestion": "Concrete suggestion for how to fix it",
    "severity": "high|medium|low"
  }
]
```

If no issues are found, write an empty array: `[]`

### Guidelines

- Be specific — reference exact files, functions, and line numbers
- Verify claims by running actual checks, not by reading code
- Focus on issues that affect correctness, security, or maintainability
- Do not flag style preferences that don't match any codebase convention
