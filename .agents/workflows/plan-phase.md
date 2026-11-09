# Workflow: /plan-phase

Plan a project phase or major task thoroughly before executing changes.

## Steps:
1. **Context & Document Review**:
   - Read `TASK_GATES.md` to identify the current phase gate requirements and acceptance criteria.
   - Review relevant architectural documents in `docs/architecture/` and decisions in `docs/decisions/`.
   - Verify compliance with `.agents/rules/00-project-invariants.md`.

2. **Scope & Risk Analysis**:
   - Define exact in-scope items and explicitly list out-of-scope boundaries.
   - Map dependencies, prerequisites, and affected files/modules.
   - Analyze security risks, failure modes, and trust boundary crossings.

3. **Formulate Verification Strategy**:
   - Determine specific unit, integration, and negative test cases required for the phase gate.
   - Identify deterministic assertions and evidence required to satisfy the gate.

4. **Output Implementation Plan**:
   - Present a concise, phased implementation plan to the user.
   - **DO NOT** implement or write application code while in planning mode.
   - Await explicit user feedback or approval before transitioning to execution.

