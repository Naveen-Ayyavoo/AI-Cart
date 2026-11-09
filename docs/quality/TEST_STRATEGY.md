# TrustCart Test Strategy & Quality Framework

This document outlines the testing methodology, categories, tooling, and strict negative test requirements for TrustCart.

---

## 1. Core Testing Principles

1. **Evidence-Based Gate Verification**: No phase gate in `TASK_GATES.md` is considered complete without verifiable automated test execution outputs.
2. **Mandatory Negative Paths**: Every functional test suite MUST include explicit negative test cases asserting fail-closed behavior on corrupted, tampered, expired, or malicious inputs.
3. **Monetary Precision Isolation**: All financial arithmetic must be asserted using exact Python `Decimal` values. Binary floating-point comparisons are prohibited.
4. **Deterministic Mocking**: Unit and standard integration tests must run isolated from external network dependencies (Gemini, Channel3, PayPal) using verified mock fixtures. Live API smoke tests run separately under explicit flags.

---

## 2. Test Categories & Scope

```
                ▲
               / \
              /   \
             / E2E \       End-to-End User Journeys (Phase P7)
            /-------\
           / Failure \     Failure Injection & Chaos Tests (Phase P7)
          / Injection \
         /-------------\
        /   Security    \  Adversarial, Replay & Signature Tests (Phase P6-P7)
       /-----------------\
      /    Integration    \  Service Layer & API Contract Tests (Phase P2-P6)
     /---------------------\
    /      Unit Tests       \  Domain Logic, Decimal Math, Policies (Phase P1-P5)
   /-------------------------\
```

### A. Unit Testing
- **Focus**: Pure domain logic, schema parsers, cryptographic fingerprinting, and policy rules.
- **Key Suites**:
  - `test_decimal_math`: Verifies sum, discount, and tax calculations with zero rounding error.
  - `test_purchase_contract`: Validates schema parsing and boundary conditions (e.g., negative budget, missing currency).
  - `test_policy_engine`: Evaluates budget boundary tests ($150.00 max vs $150.01 item), merchant matching, variant criteria.
  - `test_cart_fingerprint`: Verifies SHA-256 fingerprint generation and tamper detection.

### B. Integration Testing
- **Focus**: Django service layers, database transaction atomicity, and API client interactions using mock fixtures.
- **Key Suites**:
  - `test_gemini_client`: Mock Gemini responses (valid JSON, malformed JSON, markdown-wrapped JSON, missing attributes).
  - `test_channel3_client`: Mock Channel3 responses (in-stock, out-of-stock, rate-limited, stale timestamps).
  - `test_paypal_client`: Mock PayPal Orders v2 endpoints (`/v2/checkout/orders`, `/capture`) with idempotency headers.
  - `test_order_state_machine`: Verifies valid transitions (`PROPOSED` -> `APPROVED` -> `CAPTURED`) and blocks illegal transitions (e.g., `DRAFT` -> `CAPTURED`).

### C. Security Testing
- **Focus**: Adversarial verification matching `docs/security/THREAT_MODEL.md`.
- **Key Suites**:
  - `test_prompt_injection`: Submits adversarial prompt strings; asserts backend policy overrides model suggestions.
  - `test_approval_tampering`: Attempts to modify unit price, quantity, or variant ID after approval token generation; asserts immediate rejection.
  - `test_approval_replay`: Replays an already consumed or expired approval token; asserts fail-closed rejection.
  - `test_webhook_signatures`: Submits spoofed PayPal webhook payloads; asserts 400 Bad Request on invalid signatures.

### D. Failure Injection Testing
- **Focus**: Simulating network splits, transient API errors, race conditions, and dynamic market shifts.
- **Key Suites**:
  - `test_price_change_during_checkout`: Simulates a price change after user approval; asserts payment capture is aborted.
  - `test_concurrent_capture`: Triggers simultaneous capture requests for the same order; asserts exactly one succeeds and the duplicate fails safely via idempotency.
  - `test_external_api_timeout`: Injects timeouts during Channel3 or PayPal calls; verifies graceful degradation.

### E. End-to-End (E2E) Testing
- **Focus**: Complete user journeys simulated through Django test client from prompt entry to PayPal Sandbox capture.
- **Key Suites**:
  - Happy path: Shopper intent -> Contract -> Channel3 discovery -> Policy pass -> Proposal -> Approval -> PayPal checkout -> Capture -> Reconciliation.
  - User cancellation path: Shopper cancels PayPal checkout -> Order returns cleanly to `PROPOSED` state.

---

## 3. Test Execution Framework

- **Runner**: Django test runner (`python manage.py test`) or `pytest` / `pytest-django`.
- **Linter & Code Quality**: Ruff (`ruff check .`, `ruff format --check .`).
- **Reporting**: Detailed console output and test result summaries recorded during phase gate reviews.

