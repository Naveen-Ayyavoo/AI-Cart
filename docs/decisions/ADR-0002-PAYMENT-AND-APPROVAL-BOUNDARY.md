# ADR-0002: Payment and Approval Boundary Architecture

## Status
Accepted

## Context
Autonomous agents that interact with payments pose severe risks of unauthorized spending, unintended checkout, price-tampering, prompt injection, and double charging. We must establish an unbreachable boundary separating AI reasoning from payment execution authority.

## Decision
1. **Decoupled Two-Stage Approval**:
   - Internal TrustCart purchase approval (shopper reviewing exact cart proposal) and external PayPal buyer approval (shopper authorizing payment in PayPal) are strictly separate, sequential steps.
   - An approval is single-use, time-limited (15-minute TTL), and cryptographically bound via a SHA-256 cart fingerprint.
2. **Cryptographic Cart Fingerprinting**:
   - Fingerprint binds: `{product_id, variant_id, quantity, unit_price, total_amount, currency, payee_id}`.
   - Any price change, quantity adjustment, or item modification instantly revokes the active approval token.
3. **Server-Side Capture Execution**:
   - PayPal capture is performed solely by server-side Python code via `POST /v2/checkout/orders/{id}/capture`.
   - The client browser and LLM have zero ability to execute capture.
   - Before calling capture, the server deterministically re-evaluates the approval token, cart fingerprint, and amount.
4. **Idempotency & Webhooks**:
   - Every state-mutating PayPal API call sends a unique UUIDv4 `PayPal-Request-Id` idempotency header.
   - All incoming webhook notifications undergo cryptographic signature verification against PayPal public certificate endpoints before updating local transaction states.
5. **No Card Data Storage**:
   - TrustCart never collects, transmits, or persists credit card numbers, CVVs, or bank credentials.

## Consequences
- **Positive**: Complete defense against unauthorized agent purchases, price manipulation, double charging, and prompt injection attacks targeting payment logic.
- **Negative**: Requires careful handling of multi-step redirects and state synchronization between internal approval, PayPal approval, and server capture.

## Assumptions & Unresolved Questions
- **Assumption**: PayPal Sandbox Orders API supports server-side capture following standard buyer approval redirect flow.
- **Assumption**: PayPal webhook simulators or ngrok/tunneling will be required to verify webhook signatures in local development.
- **Unresolved Question**: How will webhook testing be handled during local automated integration test runs? *(Answer: Mocks for unit/integration suites; live webhook tunnel for Phase P6 validation).*

