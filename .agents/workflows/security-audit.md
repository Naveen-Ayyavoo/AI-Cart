# Workflow: /security-audit

Comprehensive audit of security posture, trust boundaries, and payment integrity.

## Steps:
1. **Trust Boundary Review**:
   - Inspect all interaction points with Gemini: verify prompt sanitization, strict schema adherence, and confirm that the LLM cannot trigger state changes or payments.
   - Inspect all Channel3 product data ingestion: verify provenance recording, freshness TTL enforcement, and fail-closed handling of conflicting/missing attributes.

2. **Authorization & State Machine Integrity**:
   - Verify approval token cryptographic binding (product ID, variant ID, payee, quantity, prices, cart fingerprint).
   - Verify approval single-use enforcement and TTL expiration.
   - Confirm that any cart or price mutation invalidates active approval tokens.

3. **Payment State & PayPal Integration**:
   - Confirm PayPal capture is executed exclusively server-side following explicit buyer approval.
   - Verify idempotency keys (`PayPal-Request-Id`) are present on all state-mutating requests.
   - Verify cryptographic verification of PayPal webhook signatures.
   - Confirm that zero credit card or sensitive authentication data is persisted or accepted.

4. **Secrets & Logging Audit**:
   - Audit code and logs to ensure no API keys, client secrets, or sensitive tokens are exposed or committed.
   - Validate that `.env` remains excluded from Git tracking.

5. **Report & Prioritization**:
   - Prioritize findings by severity and exploitability.
   - Recommend concrete remediations before phase progression.

