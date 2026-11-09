# Workflow: /implement-task

Execute an approved task cleanly within strictly bounded scope.

## Steps:
1. **Prerequisite Check**:
   - Read the approved task plan, relevant architecture docs, and active rules (`.agents/rules/`).
   - Confirm that the current phase gate in `TASK_GATES.md` permits this implementation.

2. **Scoped Implementation**:
   - Implement only the approved scope. Do not make unrelated changes or add speculative abstractions.
   - Adhere to invariants: Decimal arithmetic for currency, untrusted LLM/external data boundaries, fail-closed handling.
   - Maintain documentation integrity and preserve existing comments.

3. **Validation & Routine Checks**:
   - Run safe local verification commands (e.g., test runner, Ruff linter, type checks) via PowerShell.
   - Verify that negative edge cases and validation rules behave as specified.

4. **Status & Change Reporting**:
   - Update `docs/planning/CURRENT_STATUS.md` if milestones or component statuses changed.
   - Report exact files modified and provide a concise summary of changes and test results.

