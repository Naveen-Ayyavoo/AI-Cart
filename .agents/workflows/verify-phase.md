# Workflow: /verify-phase

Independently validate a phase against its explicit gate criteria before advancing.

## Steps:
1. **Audit Phase Criteria**:
   - Read the target phase definition in `TASK_GATES.md`.
   - Collate all required deliverables, required tests, and security checks for the phase.

2. **Execute Independent Verification**:
   - Run the full test suite for the phase, including negative test cases and security edge cases.
   - Inspect failure paths, error handling, and security-sensitive boundaries.
   - Verify that all calculations use Decimal arithmetic and that all external inputs are sanitized.

3. **Evidence Collection**:
   - Collect concrete command outputs, logs, and test execution results.
   - NEVER mark a phase gate complete without verifiable evidence.

4. **Verdict & Documentation**:
   - If all criteria pass: Update `TASK_GATES.md` status to COMPLETE with recorded evidence timestamp.
   - If any criteria fail or blockers arise: Mark FAIL or BLOCKED, detail exact discrepancies, and propose remedial actions.

