---
description: "Security rules, credential safety, and external integration boundaries"
trigger: model_decision
---

# 20 - Security & Integration Rules

1. **AI / LLM Defense**:
   - Treat all Gemini outputs as untrusted data proposals.
   - Use structured outputs / strict JSON schema parsing; discard malformed responses.
   - Sanitize product descriptions and user queries before context injection to defend against indirect prompt injection.
   - The LLM must have no direct execution tools for payment, order placement, or wallet deduction.
2. **External Product Data (Channel3)**:
   - External catalog payloads are untrusted evidence.
   - Always record and verify provenance: timestamp, source seller, original currency, SKU/variant ID.
   - Stale product data (older than allowed TTL) must trigger refresh or fail closed.
3. **Payment Security (PayPal Orders API Sandbox)**:
   - All PayPal API interactions must occur exclusively in server-side services with credentials loaded from environment variables.
   - Every order creation call must include a unique idempotency key (`PayPal-Request-Id`).
   - Webhook events must be cryptographically verified against PayPal certificate/signature headers before database ingestion.
   - Revalidate cart fingerprint, price, quantity, and merchant ID immediately before executing payment capture.
4. **Secrets Management**:
   - Never log, commit, or return API keys, client secrets, or webhook tokens in client responses or telemetry.
   - Read configurations exclusively via environment variables.

