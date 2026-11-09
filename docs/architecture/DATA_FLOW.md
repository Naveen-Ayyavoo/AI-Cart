# TrustCart End-to-End Data Flow

This document details the lifecycle of a TrustCart shopping session, tracing data from the initial user requirement to final payment capture and reconciliation.

---

## Complete Transaction Lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor Shopper
    participant UI as Web Frontend
    participant Backend as TrustCart Core Engine
    participant Gemini as Gemini AI (Untrusted)
    participant Channel3 as Channel3 API (Evidence)
    participant PayPal as PayPal Sandbox

    Note over Shopper, Gemini: 1. Intent & Purchase Contract Phase
    Shopper->>UI: Inputs shopping prompt (e.g., "Find noise-canceling headphones under $150")
    UI->>Backend: POST /contracts/create/ {prompt}
    Backend->>Gemini: Request structured contract extraction (Schema enforced)
    Gemini-->>Backend: Return JSON {category, max_budget: "150.00", currency: "USD", specs: [...]}
    Backend->>Backend: Validate contract fields & constraints
    Backend-->>UI: Display structured Purchase Contract for user confirmation
    Shopper->>UI: Confirms Purchase Contract

    Note over Backend, Channel3: 2. Product Discovery & Evidence Phase
    UI->>Backend: POST /contracts/{id}/search/
    Backend->>Channel3: Query products matching contract specifications
    Channel3-->>Backend: Return product catalog listings with raw prices & merchants
    Backend->>Backend: Ingest evidence, sanitize descriptions, convert prices to Decimal, store provenance

    Note over Backend: 3. Deterministic Policy Evaluation Phase
    Backend->>Backend: Run policy engine against candidate items
    Backend->>Backend: Check budget limit (Decimal <= "150.00"), verify in-stock, verify US merchant
    Backend->>Backend: Select conforming candidate with best trade-off evaluation

    Note over Shopper, UI: 4. Proposed Purchase & Approval Binding Phase
    Backend->>Backend: Compute SHA-256 cart fingerprint over {item, variant, qty, unit_price, total, payee}
    Backend->>Backend: Generate single-use Approval Token (TTL: 15 mins)
    Backend-->>UI: Render Proposed Purchase & binding details (Price: $149.99, Demo Payee Notice)
    Shopper->>UI: Clicks "Approve Purchase"
    UI->>Backend: POST /orders/approve/ {approval_token}
    Backend->>Backend: Verify token validity, expiration, and fingerprint integrity

    Note over Backend, PayPal: 5. PayPal Sandbox Checkout & Server Capture
    Backend->>PayPal: POST /v2/checkout/orders (Idempotency Key: UUID, Amount: "149.99", Currency: "USD")
    PayPal-->>Backend: Return Order ID & buyer approval redirect link
    Backend-->>UI: Redirect shopper to PayPal Sandbox buyer approval URL
    Shopper->>PayPal: Authenticates in PayPal Sandbox & approves payment
    PayPal-->>UI: Redirect back to return_url?token={order_id}
    UI->>Backend: GET /payments/complete/?token={order_id}
    Backend->>Backend: Final deterministic revalidation (re-check approval token, cart fingerprint, amount)
    Backend->>PayPal: POST /v2/checkout/orders/{order_id}/capture (Idempotency Key: UUID)
    PayPal-->>Backend: 201 Created (Status: COMPLETED, Transaction ID)
    Backend->>Backend: Atomically mark order CAPTURED, consume Approval Token

    Note over PayPal, Backend: 6. Webhook Reconciliation Phase
    PayPal->>Backend: POST /webhooks/paypal/ (Event: PAYMENT.CAPTURE.COMPLETED, Headers: Signatures)
    Backend->>PayPal: Verify webhook signature against public certificate
    Backend->>Backend: Idempotent reconciliation check & audit logging
    Backend-->>PayPal: 200 OK
```

---

## Data State Machine

An order traverses the following deterministic state transitions:

```
[ DRAFT ]
    │
    ▼ (User confirms Purchase Contract)
[ CONTRACT_CONFIRMED ]
    │
    ▼ (Channel3 search & deterministic policy pass)
[ PROPOSED ]
    │
    ▼ (Shopper explicitly approves proposal)
[ APPROVED ] (Approval Token generated; TTL 15 mins)
    │
    ├───(Token expires or details mutate)───► [ VOIDED / EXPIRED ]
    │
    ▼ (PayPal order created; buyer redirects)
[ PAYPAL_AUTHORIZED ]
    │
    ▼ (Server revalidation & successful capture)
[ CAPTURED ]
    │
    ▼ (Webhook verified)
[ RECONCILED ]
```

### Safety Rules Enforced Across Transitions:
1. Moving from `PROPOSED` to `APPROVED` requires an active, authenticated shopper session.
2. If any cart attribute (price, shipping, item variant) changes while in `APPROVED`, the status immediately transitions to `VOIDED`.
3. Capture can only be triggered from `PAYPAL_AUTHORIZED` and must result in atomic transition to `CAPTURED`. Duplicate capture attempts are prevented via idempotency keys and database-level row locking.

