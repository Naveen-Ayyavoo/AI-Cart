---
name: phase-gate-review
description: Inspects phase scope, deliverables, and acceptance criteria against TASK_GATES.md, verifying tests and invariants independently to return PASS, FAIL, or BLOCKED with evidence.
---

# Phase Gate Review Skill

This skill performs an objective, evidence-based review of the current project phase against the criteria defined in `TASK_GATES.md`.

## Execution Protocol:

1. **Gate Inspection**:
   - Locate the active phase gate in `TASK_GATES.md`.
   - Read the defined Purpose, Scope, Dependencies, Deliverables, Required Tests, Security Checks, and Completion Gate.

2. **Artifact & Code Audit**:
   - Verify that all specified deliverables exist and meet project standards (`.agents/rules/`).
   - Check that no scope creep or premature advancement into subsequent phases has occurred.

3. **Independent Test & Invariant Verification**:
   - Execute the test suite relevant to the phase.
   - Verify that negative test cases, error boundaries, and fail-closed behaviors were executed and passed.
   - Confirm adherence to core invariants: Decimal monetary types, strict trust boundaries, and zero secret leakage.

4. **Verdict Generation**:
   Generate an audit verdict formatted as follows:
   - **Status**: `PASS` | `FAIL` | `BLOCKED`
   - **Phase**: [e.g. P0, P1, P2...]
   - **Scope Compliance**: Detailed verification of deliverables.
   - **Verification Evidence**: Shell commands executed, exit codes, and test outputs.
   - **Defects / Blockers**: Unfulfilled criteria, failing tests, or missing evidence (if any).
   - **Recommendation**: Exact next steps for resolution or gate sign-off.

