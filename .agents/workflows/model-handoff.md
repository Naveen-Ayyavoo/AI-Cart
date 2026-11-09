# Workflow: /model-handoff

Prepare a structured handoff document prior to switching models, subagents, or ending turns.

## Steps:
1. **Collate Session State**:
   - Identify the current active phase gate in `TASK_GATES.md`.
   - List all completed tasks, deliverables, and decisions made in the current session.
   - List all files created, modified, or deleted during the turn.

2. **Record Test & Verification Evidence**:
   - Record exact tests run, command outputs, and verification results.
   - Document any failed attempts, edge cases investigated, or temporary workarounds.

3. **Identify Blockers & Next Action**:
   - List any unresolved questions, unverified components, or active blockers.
   - Specify the exact, unambiguous next step for the incoming model or session.

4. **Update Handoff Document**:
   - Write the consolidated report directly into `docs/planning/HANDOFF.md`.
   - Ensure the handoff is self-contained so that a fresh context can resume without loss of continuity.

