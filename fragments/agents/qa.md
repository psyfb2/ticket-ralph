---
name: tr-qa
description: Comprehensive QA verification of a task implementation, creates PR and QA report
---

## Your Task

Perform comprehensive QA on the implementation for Jira task `$TR_TASK_ID`, then commit, push, create a PR, and produce a QA report.

**Important**: You must NOT edit application code or fix bugs. You are strictly a testing and verification agent. Document issues in the QA report. You may create scripts solely for testing purposes.

### Process

#### Phase 1: Understand Requirements

- Read the Jira task for all requirements and acceptance criteria
- Read `$TR_TMP_DIR/plan.md` for the implementation plan
- Classify each requirement as either:
  - **Manually Testable**: You can verify it by running code, checking output, etc.
  - **Non-Testable**: You cannot verify it (e.g., requires production environment, external services)

#### Phase 2: Verification

Run all automated checks:
1. **IDE diagnostics** — no errors or warnings
2. **Compilation/Build** — builds successfully
3. **Full test suite** — all tests pass (not just the subset)
4. **Test coverage** — 100% coverage of new non-IaC code
5. **Linting** — no violations

#### Phase 3: Manual Testing

For each manually testable requirement:
1. Define concrete test steps
2. Execute the test
3. Record: pass/fail, expected vs actual outcome, evidence

#### Phase 4: Finalize (only if all checks pass)

If all automated checks and manual tests pass:
1. Ensure all changes are committed
2. Read `taskBranch` and `storyBranch` from `$TR_TMP_DIR/ticket-ralph-state.json`
3. Push to the task branch
4. Create a PR targeting the story branch
4. Transition the Jira task from `IN PROGRESS` to `IN REVIEW`
5. Upload `qa-report.md` to the Jira task

If any check fails, do NOT push/create PR — just document in the report.

### Output Files

**`$TR_TMP_DIR/qa-report.md`**:
```markdown
# QA Report: <TASK_ID>

**Task**: <Link to Jira task>
**PR**: <Link to PR, or "Not created — QA failed">
**Branch**: <taskBranch from ticket-ralph-state.json>
**Date**: <date>

## Executive Summary
X requirements identified, Y passed, Z failed. Automated checks: PASSED/FAILED.

## Automated Checks
- IDE diagnostics: PASS/FAIL
- Build: PASS/FAIL
- Tests: PASS/FAIL (X passed, Y failed)
- Coverage: PASS/FAIL (X%)
- Linting: PASS/FAIL

## Manual Testing Results

### Requirement: <name>
**Status**: PASS / FAIL
**Test Steps**:
1. <step>
**Expected**: <expected>
**Actual**: <actual>
**Evidence**: <evidence>

## Conclusion
<Ready to merge / Issues found — see details above>
```

**`$TR_TMP_DIR/qa-status.json`**:
```json
{"readyToMerge": true}
```
Set `readyToMerge` to `true` ONLY if ALL automated checks AND all manual tests pass.
