# Trust Boundaries & Security Enclaves

TrustCart enforces rigid boundaries between untrusted external actors, advisory AI services, untrusted third-party data providers, and the deterministic core engine.

---

## 1. Trust Boundary Matrix

| Entity / Component | Trust Level | Failure Mode | Permitted Actions | Prohibited Actions |
| :--- | :--- | :--- | :--- | :--- |
| **Shopper / Client Browser** | **Untrusted** | Reject request / 400 Bad Request | Provide natural language intent, approve proposal, complete PayPal checkout | Directly alter pricing, bypass approval, invoke server capture |
| **Gemini AI Service** | **Untrusted Advisory** | Discard output / Fallback / Prompt Error | Propose structured contracts, generate product trade-off summaries | Transition state, touch payment tokens, authorize transactions |
| **Channel3 API** | **Untrusted Evidence** | Fail closed / Invalidate item / Refresh | Provide catalog listings, prices, merchant details, stock status | Mandate checkout, alter backend policies, deliver unescaped HTML |
| **TrustCart Backend Core** | **Trusted Core** | Log failure / Abort atomic transaction | Enforce policies, compute fingerprints, issue approval tokens, capture payment | Use floating-point math, accept unverified webhooks, bypass user approval |
| **PayPal Orders API** | **External Payment Gateway** | Abort checkout / Mark payment failed | Authenticate buyer, authorize charge, execute capture, send signed webhooks | Modify internal TrustCart cart items, execute capture without idempotency |

---

## 2. Boundary Descriptions & Invariants

```
 +---------------------------------------------------------------------------------------+
 | UNTRUSTED EXTERNAL ZONE                                                               |
 |   - Shopper Browser (HTML/JS)                                                         |
 |   - Channel3 Product API (External Catalog)                                           |
 |   - Gemini AI API (Advisory Reasoning)                                                |
 +---------------------------------------------------------------------------------------+
                                        │
                                        ▼  (Strict Validation, Sanitization & Schema Enforcement)
 +---------------------------------------------------------------------------------------+
 | TRUSTED CORE ZONE (TrustCart Backend Engine)                                         |
 |   - Deterministic Policy Engine (Python)                                              |
 |   - Decimal Money Calculator                                                           |
 |   - Cryptographic Approval Binding (SHA-256 Fingerprint)                              |
 |   - Order & Transaction State Machines (Atomic DB Transactions)                       |
 +---------------------------------------------------------------------------------------+
                                        │
                                        ▼  (Authenticated, Idempotent Server-to-Server Calls)
 +---------------------------------------------------------------------------------------+
 | SECURED EXECUTION GATEWAY (PayPal Sandbox)                                            |
 |   - PayPal Orders v2 API                                                              |
 |   - PayPal Buyer Approval Flow                                                        |
 |   - Cryptographically Signed Webhooks                                                 |
 +---------------------------------------------------------------------------------------+
```

### Boundary 1: Shopper Input Boundary
- Shopper intent strings are sanitized to prevent direct prompt injection attacks.
- Client requests cannot directly set prices, discounts, or skip verification steps.
- Approval requires explicit user action via an authenticated session.

### Boundary 2: Gemini LLM Boundary
- All prompts are sent with system instructions enforcing strict structured JSON schemas.
- Model output is parsed through deterministic Pydantic/dataclass schemas; any extraneous fields, malformed JSON, or type mismatches are rejected immediately.
- Gemini is never granted tools or permissions to call payment endpoints or database mutations.

### Boundary 3: Channel3 Evidence Boundary
- Catalog listings, titles, descriptions, and seller notes are treated as untrusted text.
- HTML in product descriptions is never rendered unescaped (defending against stored XSS).
- Product pricing is extracted as raw text, verified as positive numerical values, and immediately converted to `Decimal`.
- Items with ambiguous stock, missing prices, or conflicting currencies fail closed.

### Boundary 4: Approval Binding Boundary
- An approval token is cryptographically bound to the tuple:
  `{product_id, variant_id, payee_id, quantity, unit_price, total_price, currency, cart_fingerprint}`.
- If any element of this tuple changes between presentation and checkout initiation, the token becomes invalid.
- Approval tokens are single-use and expire after a strict 15-minute TTL.

### Boundary 5: PayPal Payment Boundary
- All PayPal API requests originate strictly from the backend server; client-side SDKs are prohibited from executing capture.
- Every order creation request contains a UUIDv4 `PayPal-Request-Id` idempotency header.
- Webhook notifications from PayPal are subjected to cryptographic signature verification (using PayPal public certs) before any local order status update is performed.

