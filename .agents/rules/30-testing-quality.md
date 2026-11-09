---
description: "Testing standards, negative test requirements, and quality verification"
trigger: model_decision
---

# 30 - Testing & Quality Standards

1. **Evidence-Based Verification**: Never mark a task or phase complete without executable test proof and direct output evidence.
2. **Mandatory Negative Paths**:
   - For every positive test case, write explicit negative test cases (e.g. malformed JSON, prompt injection strings, price tamper attempts, expired approval tokens, replayed idempotency keys, unverified webhooks).
   - Verify that all invalid or conflicting states fail closed safely.
3. **Monetary Precision Tests**:
   - Verify zero rounding drift across line items, tax, discounts, and total sum using Decimal arithmetic.
4. **Mocking External Integrations**:
   - Unit and integration tests must not make live calls to external APIs (Gemini, Channel3, PayPal).
   - Use deterministic, verified fixtures and mock responses mirroring actual vendor schemas.
   - Separate live integration smoke tests behind explicit configuration flags.
5. **State Transition Safety**:
   - Test race conditions and double-spending: attempt concurrent approval token consumption and concurrent capture attempts to ensure atomicity.

