---
trigger: glob
globs: "**/*.py"
description: "Python and Django conventions for TrustCart source files."
---

# 10 - Python & Django Standards

1. **Python Environment**: Target Python 3.14 (running in `.venv`). Use modern Python syntax and standard library typing (`typing`, `dataclasses`, `enum`).
2. **Monetary Types**: Always import and use `decimal.Decimal` with explicit string or integer construction (e.g. `Decimal("19.99")`). Never use `float` in pricing, tax, or discount logic.
3. **Django Models & Architecture**:
   - Keep business logic in deterministic domain service modules, not in fat models or view functions.
   - Use explicit transactions (`transaction.atomic`) for state transitions involving order lifecycle and payment state.
   - Implement explicit status state machines (e.g., `Draft` -> `Proposed` -> `Approved` -> `Authorized` -> `Captured` -> `Reconciled` / `Failed`).
   - Store monetary fields as `DecimalField(max_digits=12, decimal_places=2)`.
4. **Validation & Contracts**:
   - Validate incoming payloads strictly with schema-enforced dataclasses or forms before processing.
   - Enforce immutability on approval and payment records once transitions occur.
5. **Linting & Code Quality**:
   - Code must pass Ruff formatting and linting.
   - Include type annotations on all service function signatures.
   - Preserve comments and docstrings.

