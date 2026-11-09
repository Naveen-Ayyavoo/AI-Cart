---
description: "Core non-negotiable architectural and trust invariants for TrustCart"
trigger: always_on
---

# 00 - TrustCart Project Invariants

1. **Untrusted Reasoning Boundary**: Gemini is an advisory, untrusted reasoning engine. It generates structured purchase proposals and comparisons, but it NEVER owns state, approval decisions, or payment triggers.
2. **Deterministic Backend Authority**: Deterministic Python backend code owns contract validation, policy evaluation, transaction state machines, approval tokens, and payment calls.
3. **External Evidence Boundary**: Product data from Channel3 is untrusted external evidence. The backend must preserve source, retrieval timestamp, currency, variant identity, and provenance.
4. **Fail-Closed Principle**: Any missing, conflicting, ambiguous, or unverifiable critical purchase facts (price, stock, merchant identity, currency) MUST fail closed with a clear error.
5. **Exact Monetary Calculations**: All currency and price calculations MUST use Python `Decimal`. Binary floating-point arithmetic (`float`) is strictly prohibited for monetary values.
6. **Immutable Approval Binding**: Purchase approval binds cryptographically to exact parameters: product ID, variant ID, merchant/payee ID, quantity, unit price, total price, currency, and cart fingerprint. Any material change invalidates the approval token.
7. **Single-Use, Time-Limited Approvals**: Approvals must have a strict TTL (time-to-live) and be consumable exactly once via atomic state transition.
8. **Decoupled Approvals**: Internal TrustCart purchase approval and external PayPal buyer approval are separate sequential gates.
9. **Server-Side PayPal Capture**: Payment capture occurs exclusively server-side after deterministic revalidation and explicit buyer approval.
10. **Idempotency & Webhook Verification**: All payment mutations require idempotency keys. All incoming PayPal webhook events require cryptographic signature verification before processing.
11. **No Sensitive Payment Data Storage**: Never accept or persist credit card numbers, CVVs, or bank credentials.
12. **Secret Isolation**: API credentials remain strictly server-side and outside version control.
13. **Demo Merchant Disclosure**: PayPal Sandbox transactions settle against a controlled, clearly disclosed demo merchant/payee, never pretending to execute arbitrary external retail checkout.
14. **Integration Decoupling**: Product discovery (Channel3) and payment execution (PayPal) are strictly separate integrations.
15. **Zero-Spend Engineering Policy**: Total additional expenditure across development, testing, demonstration, and submission MUST remain strictly ZERO. Use verified free tiers only (Gemini Free Tier, Channel3 free allowance, Context7 Free, PayPal Sandbox, open-source libraries). Never enable paid billing, upgrade tiers, attach paid fallbacks, or incur financial charges. On quota exhaustion, immediately stop calls, signal status, and fall back to clearly labeled local fixtures without misrepresenting them as live data.

