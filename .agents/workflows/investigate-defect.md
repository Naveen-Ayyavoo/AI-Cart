# Workflow: /investigate-defect

Systematically diagnose, reproduce, and resolve defects without speculative changes.

## Steps:
1. **Deterministic Reproduction**:
   - Formulate a reproducible test case or script replicating the defect before touching application code.
   - Capture exact error messages, stack traces, and relevant state transitions.

2. **Root Cause Analysis**:
   - Trace data flow and callers leading to the unexpected state.
   - Inspect boundary transitions (e.g. LLM output parsing, external API payloads, approval token validation, payment state machines).
   - Identify whether the defect stems from logic errors, unhandled negative states, or trust assumption violations.

3. **Regression Test Addition**:
   - Add a targeted unit or integration test capturing the failing condition to prevent regression.

4. **Minimal Targeted Remediation**:
   - Implement the minimal correct fix addressing the root cause.
   - Avoid speculative or sweeping refactorings.
   - Re-run the regression test and existing test suite to verify the resolution.

