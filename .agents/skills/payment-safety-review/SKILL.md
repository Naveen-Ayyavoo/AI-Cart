---
name: payment-safety-review
description: Inspects purchase approval binding, state transitions, order identity, Decimal monetary precision, idempotency, PayPal buyer approval, server-side capture, and webhook signature verification.
---

# Payment Safety Review Skill

This skill performs a rigorous, deterministic safety audit across all purchase approval and payment execution components.

> [!CRITICAL]
> Under no circumstances may LLM reasoning or prompt output be accepted as proof of payment safety. All assertions must be backed by deterministic code logic, cryptographic checks, or automated tests.

## Inspection Checklist:

1. **Purchase Approval Binding & Invalidation**:
   - Verify approval token binds immutably to product ID, variant ID, merchant/payee ID, quantity, unit price, total price, currency, and cart fingerprint.
   - Confirm approval token expiration (TTL) is enforced.
   - Confirm single-use consumption semantics: verify approval token cannot be reused across multiple orders.
   - Confirm that any mutation in cart items, shipping address, or price invalidates existing approval tokens.

2. **Monetary Precision**:
   - Verify all monetary calculations use `decimal.Decimal` with explicit string conversion.
   - Confirm zero floating-point arithmetic in line-item summing, discounts, or tax computations.

3. **PayPal Orders API Sandbox Boundary**:
   - Confirm payment capture runs strictly server-side.
   - Verify TrustCart purchase approval and PayPal buyer approval are separate, sequential gates.
   - Verify `PayPal-Request-Id` idempotency header is present on order creation and capture calls.
   - Verify final deterministic revalidation occurs immediately before the PayPal capture API call.

4. **Webhook Security & Replay Defense**:
   - Confirm cryptographic signature verification on all incoming PayPal webhook requests prior to reading event payloads.
   - Confirm webhook handler idempotency against duplicate webhook deliveries.

5. **Data Protection & Demo Isolation**:
   - Confirm no credit card numbers, CVVs, or sensitive authentication details are stored, logged, or received.
   - Confirm transaction specifies the controlled demo merchant/payee and clearly discloses Sandbox settlement.

## Verdict Output:
Return `PASS` or `FAIL` with itemized evidence for each checklist point.

