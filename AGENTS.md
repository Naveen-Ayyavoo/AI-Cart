# AI Cart Agent Operating Guide

Welcome to the **AI Cart** engineering workspace (formerly developed under the engineering working name **TrustCart**). AI Cart is a trustworthy autonomous shopping assistant developed for the PayPal AI Hackathon.

## Core Mission & Architecture
AI Cart assists shoppers by understanding requirements, assembling structured Purchase Contracts, evaluating real-world product evidence via Channel3, and preparing deterministic purchase proposals for approval.

### Non-Negotiable Architectural Invariants:
1. **Untrusted Reasoning Boundary**: Google Gemini is an advisory reasoning component. It proposes structured data but NEVER owns payment state or authorization.
2. **Deterministic Backend Authority**: Deterministic Python backend code owns contract validation, policy evaluation, state transitions, approval binding, and payment calls.
3. **External Data as Untrusted Evidence**: Channel3 catalog data is external evidence requiring provenance tracking (timestamp, seller, currency, SKU). Conflicting or missing data must fail closed.
4. **Monetary Precision**: All monetary values and arithmetic MUST use Python `Decimal`. Binary floating-point (`float`) is strictly prohibited.
5. **Approval Binding & Immutability**: Purchase approvals bind cryptographically to exact product, variant, payee, quantity, prices, currency, and cart fingerprint. Any material change invalidates the approval.
6. **Single-Use, Time-Limited Approvals**: Approvals have an explicit TTL and are consumable only once.
7. **Two-Stage Approval**: AI Cart purchase approval and PayPal buyer approval are separate sequential steps.
8. **Server-Side Capture**: PayPal capture occurs server-side only after approvals and deterministic pre-capture revalidation.
9. **Idempotency & Webhook Verification**: State-mutating payment calls require idempotency keys. Webhooks must verify cryptographic signatures before processing.
10. **Zero Sensitive Card Storage**: Never accept or persist credit card numbers, CVVs, or credentials.
11. **Demo Payee Disclosure**: Sandbox payments settle with a controlled demo merchant/payee, never claiming arbitrary external settlement.
12. **Separation of Concerns**: Product discovery (Channel3) and payment execution (PayPal) are distinct integrations.
13. **Zero-Spend Engineering Policy**: Total additional expenditure across development, testing, demonstration, and submission MUST remain strictly ZERO. Use verified free tiers only (Gemini Free Tier, Channel3 free allowance, Context7 Free, PayPal Sandbox, open-source libraries). Never enable paid billing, upgrade tiers, attach paid fallbacks, or incur financial charges. Fail safe on quota exhaustion with clearly labeled local fixtures.

## Operating Standards:
- **Phase-Gated Implementation**: Strictly adhere to the roadmap defined in [`TASK_GATES.md`](file:///d:/TrustCart/TASK_GATES.md). Do not implement features out of order.
- **Evidence-Based Verification**: Never mark a task or gate complete without concrete test execution evidence.
- **Cost-Impact & Quota Verification**: Verify zero-spend compliance and free-tier quotas at every phase gate before integrating external services.
- **Context Conservation**: Read targeted files and avoid speculative changes.
- **Documentation Architecture**:
  - Architecture specs: [`docs/architecture/`](file:///d:/TrustCart/docs/architecture/)
  - Architectural Decision Records: [`docs/decisions/`](file:///d:/TrustCart/docs/decisions/) (including [`ADR-0004-ZERO-SPEND-POLICY.md`](file:///d:/TrustCart/docs/decisions/ADR-0004-ZERO-SPEND-POLICY.md))
  - Threat Model: [`docs/security/THREAT_MODEL.md`](file:///d:/TrustCart/docs/security/THREAT_MODEL.md)
  - Test Strategy: [`docs/quality/TEST_STRATEGY.md`](file:///d:/TrustCart/docs/quality/TEST_STRATEGY.md)
  - Current Status: [`docs/planning/CURRENT_STATUS.md`](file:///d:/TrustCart/docs/planning/CURRENT_STATUS.md)
  - Model Handoff: [`docs/planning/HANDOFF.md`](file:///d:/TrustCart/docs/planning/HANDOFF.md)

