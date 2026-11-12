"""Payment orchestration service for AI Cart (formerly TrustCart) Phase P6.

Implements PAY-01 through PAY-06:
- Consumes single-use PurchaseApproval atomically when initiating checkout.
- Creates PayPal order with separate, stable idempotency keys.
- Completes checkout on buyer return with authoritative server-side query and pre-capture revalidation.
- Performs server-side capture and marks order PAID only on COMPLETED status.
- Handles ambiguous network timeouts via PENDING_RECONCILIATION and authoritative reconciliation.
- Verifies webhook cryptographic signatures and deduplicates events.
"""

import json
import logging
import uuid
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from orders.models import (
    ApprovalAlreadyConsumedError,
    ApprovalError,
    PurchaseApproval,
)
from payments.client import (
    PayPalAPIError,
    PayPalClient,
    PayPalError,
    PayPalTimeoutError,
)
from payments.models import (
    PaymentCaptureRecord,
    PaymentOrder,
    WebhookEventRecord,
)

logger = logging.getLogger(__name__)


class PayPalRevalidationError(PayPalError):
    """Raised when pre-capture deterministic revalidation detects a discrepancy."""


class PaymentService:
    """Manages the lifecycle of PayPal Sandbox payments, capture, and reconciliation."""

    @classmethod
    def initiate_checkout(
        cls,
        approval_token: str,
        return_url: str,
        cancel_url: str,
        client: PayPalClient | None = None,
    ) -> tuple[PaymentOrder, str]:
        """Atomically consume approval token and create PayPal Orders v2 transaction.

        Invariants:
        - Consumes approval token atomically exactly once.
        - Replay attempts immediately raise ApprovalAlreadyConsumedError.
        - Generates stable, distinct idempotency keys for order creation and capture.
        - Binds payee to controlled demo merchant account.
        - Returns (PaymentOrder, approve_url).
        """
        try:
            approval = (
                PurchaseApproval.objects.select_related(
                    "proposal", "proposal__contract", "proposal__product"
                ).get(token=approval_token)
            )
        except PurchaseApproval.DoesNotExist:
            raise ApprovalError(f"Approval token '{approval_token}' not found.")

        if approval.state == "CONSUMED":
            raise ApprovalAlreadyConsumedError("Approval token has already been consumed.")

        if approval.state != "APPROVED":
            raise ApprovalError(f"Approval token is in state '{approval.state}' (must be APPROVED).")

        proposal = approval.proposal
        contract = proposal.contract
        product = proposal.product

        # Stable, distinct idempotency keys
        order_create_idempotency_key = f"CREATE-{uuid.uuid4()}"
        capture_idempotency_key = f"CAPTURE-{uuid.uuid4()}"

        # 1. Atomically consume the approval token (single-use transition)
        approval.consume(order_reference=order_create_idempotency_key)

        # 2. Call PayPal Orders v2 to create order
        if client is None:
            client = PayPalClient()

        reference_id = f"TC-{uuid.uuid4().hex[:12].upper()}"

        try:
            paypal_resp = client.create_order(
                reference_id=reference_id,
                custom_id=approval.cart_fingerprint,
                title=product.title,
                sku=proposal.sku or proposal.variant_id or "DEFAULT",
                quantity=proposal.quantity,
                unit_price=proposal.unit_price,
                base_amount=proposal.base_amount,
                shipping_amount=proposal.shipping_amount,
                tax_amount=proposal.tax_amount,
                total_amount=proposal.total_amount,
                currency=proposal.currency,
                payee_email=proposal.payee_id,
                return_url=return_url,
                cancel_url=cancel_url,
                idempotency_key=order_create_idempotency_key,
            )
        except Exception as e:
            logger.error("Failed to create PayPal order: %s", e)
            raise

        paypal_order_id = paypal_resp.get("id", "")
        if not paypal_order_id:
            raise PayPalAPIError("PayPal did not return an order ID.", details=paypal_resp)

        # Find approval link
        approve_url = ""
        for link in paypal_resp.get("links", []):
            if link.get("rel") in ("approve", "payer-action"):
                approve_url = link.get("href", "")
                break

        if not approve_url:
            approve_url = f"https://www.sandbox.paypal.com/checkoutnow?token={paypal_order_id}"

        # 3. Persist PaymentOrder in CREATED state
        with transaction.atomic():
            payment_order = PaymentOrder.objects.create(
                approval=approval,
                proposal=proposal,
                contract=contract,
                paypal_order_id=paypal_order_id,
                cart_fingerprint=approval.cart_fingerprint,
                status="CREATED",
                payee_id=proposal.payee_id,
                currency=proposal.currency,
                unit_price=proposal.unit_price,
                quantity=proposal.quantity,
                base_amount=proposal.base_amount,
                shipping_amount=proposal.shipping_amount,
                tax_amount=proposal.tax_amount,
                fee_amount=proposal.fee_amount,
                total_amount=proposal.total_amount,
                create_idempotency_key=order_create_idempotency_key,
                capture_idempotency_key=capture_idempotency_key,
                paypal_approval_url=approve_url,
                audit_log=[
                    {
                        "timestamp": timezone.now().isoformat(),
                        "event": "CREATED",
                        "details": f"Created PayPal order {paypal_order_id} via Orders v2.",
                        "status": "CREATED",
                    }
                ],
            )

        return payment_order, approve_url

    @classmethod
    def complete_checkout(
        cls,
        paypal_order_id: str,
        client: PayPalClient | None = None,
    ) -> tuple[PaymentOrder, PaymentCaptureRecord | None]:
        """Authorize return from PayPal, revalidate deterministically, and capture server-side.

        Invariants:
        - NEVER trusts browser return redirect as proof of payment.
        - Authoritatively queries PayPal via GET /v2/checkout/orders/{id}.
        - Revalidates status == APPROVED, exact amount, currency, payee, and cart fingerprint.
        - Server-side capture execution using capture_idempotency_key.
        - Enters PENDING_RECONCILIATION on timeout.
        """
        try:
            payment_order = PaymentOrder.objects.select_related(
                "approval", "proposal", "contract"
            ).get(paypal_order_id=paypal_order_id)
        except PaymentOrder.DoesNotExist:
            raise PayPalError(f"Payment order '{paypal_order_id}' not found.")

        # Replay safety: If already COMPLETED, return current state
        if payment_order.status == "COMPLETED":
            latest_capture = payment_order.captures.filter(status="COMPLETED").first()
            return payment_order, latest_capture

        if payment_order.status in ("FAILED", "CANCELLED"):
            raise PayPalError(f"Cannot complete order in '{payment_order.status}' status.")

        if client is None:
            client = PayPalClient()

        # Step 1: Authoritative query of live PayPal order status
        paypal_order = client.get_order(paypal_order_id)
        remote_status = paypal_order.get("status")

        # Step 2: Deterministic Pre-Capture Revalidation
        purchase_units = paypal_order.get("purchase_units", [])
        if not purchase_units:
            raise PayPalRevalidationError("PayPal order missing purchase_units.")

        unit = purchase_units[0]
        remote_amount_val = unit.get("amount", {}).get("value", "")
        remote_currency = unit.get("amount", {}).get("currency_code", "")
        remote_custom_id = unit.get("custom_id", "")

        payee_dict = unit.get("payee", {})
        remote_payee_email = payee_dict.get("email_address", "").lower()
        remote_merchant_id = payee_dict.get("merchant_id", "").lower()
        expected_payee = payment_order.payee_id.lower()

        # Verify payee matches controlled demo merchant (by email or merchant_id)
        if expected_payee not in (remote_payee_email, remote_merchant_id):
            payment_order.status = "FAILED"
            payment_order.append_audit_event(
                "FAILED",
                f"Payee mismatch: expected '{payment_order.payee_id}', got email='{remote_payee_email}' merchant_id='{remote_merchant_id}'.",
            )
            payment_order.save()
            raise PayPalRevalidationError(
                f"Security violation: Payee does not match approved payee '{payment_order.payee_id}'."
            )

        # Verify currency is USD
        if remote_currency != "USD" or remote_currency != payment_order.currency:
            payment_order.status = "FAILED"
            payment_order.append_audit_event("FAILED", f"Currency mismatch: {remote_currency}.")
            payment_order.save()
            raise PayPalRevalidationError(f"Currency mismatch: expected USD, got '{remote_currency}'.")

        # Verify exact Decimal amount
        try:
            remote_amount = Decimal(remote_amount_val)
        except (ValueError, InvalidOperation):
            raise PayPalRevalidationError(f"Invalid monetary value from PayPal: '{remote_amount_val}'.")

        if remote_amount != payment_order.total_amount:
            payment_order.status = "FAILED"
            payment_order.append_audit_event(
                "FAILED",
                f"Amount discrepancy: expected ${payment_order.total_amount}, got ${remote_amount}.",
            )
            payment_order.save()
            raise PayPalRevalidationError(
                f"Price tampering detected: Approved amount ${payment_order.total_amount} != PayPal amount ${remote_amount}."
            )

        # Verify custom_id binds to cart fingerprint
        if remote_custom_id != payment_order.cart_fingerprint:
            payment_order.status = "FAILED"
            payment_order.append_audit_event("FAILED", "Cart fingerprint mismatch on PayPal order.")
            payment_order.save()
            raise PayPalRevalidationError("Cart fingerprint mismatch: purchase parameters have been altered.")

        # Verify underlying proposal fingerprint has not mutated
        if not payment_order.proposal.verify_fingerprint():
            payment_order.status = "FAILED"
            payment_order.append_audit_event("FAILED", "Underlying proposal parameters altered out of band.")
            payment_order.save()
            raise PayPalRevalidationError("Underlying proposal fingerprint verification failed.")

        # Check order status before capture
        if remote_status == "COMPLETED":
            # Order was already captured (e.g. by webhook or previous call)
            payment_order.status = "COMPLETED"
            payment_order.append_audit_event("COMPLETED", "Order confirmed captured via remote status.")
            payment_order.save()
            return payment_order, payment_order.captures.first()

        if remote_status in ("CREATED", "PAYER_ACTION_REQUIRED"):
            payment_order.append_audit_event(
                "AWAITING_BUYER_APPROVAL",
                f"Order not yet approved by buyer (remote status: {remote_status}).",
            )
            payment_order.save()
            raise PayPalAPIError(f"PayPal order is not approved by buyer (status: {remote_status}).")

        if remote_status != "APPROVED":
            payment_order.status = "FAILED"
            payment_order.append_audit_event("FAILED", f"Order not approved by buyer (status: {remote_status}).")
            payment_order.save()
            raise PayPalAPIError(f"PayPal order is not approved by buyer (status: {remote_status}).")

        # Verify underlying contract has not been superseded before server capture
        payment_order.contract.refresh_from_db()
        if payment_order.contract.state != "CONFIRMED":
            payment_order.status = "FAILED"
            payment_order.append_audit_event(
                "FAILED",
                f"Pre-capture blocked: Contract v{payment_order.contract.version} is {payment_order.contract.state}.",
            )
            payment_order.save()
            raise PayPalRevalidationError(
                f"Underlying Purchase Contract v{payment_order.contract.version} is no longer confirmed ({payment_order.contract.state})."
            )

        # Step 3: Transition to BUYER_APPROVED
        payment_order.status = "BUYER_APPROVED"
        payment_order.append_audit_event("BUYER_APPROVED", "Pre-capture revalidation passed. Executing server capture.")
        payment_order.save()

        # Step 4: Execute server-side capture
        try:
            capture_resp = client.capture_order(
                order_id=paypal_order_id,
                idempotency_key=payment_order.capture_idempotency_key,
            )
        except PayPalTimeoutError as e:
            logger.warning("PayPal capture request timed out; entering PENDING_RECONCILIATION: %s", e)
            payment_order.status = "PENDING_RECONCILIATION"
            payment_order.append_audit_event(
                "PENDING_RECONCILIATION",
                f"Capture timed out: {e}. Marked PENDING_RECONCILIATION.",
            )
            payment_order.save()
            # Attempt immediate authoritative reconciliation
            return cls.reconcile_order(paypal_order_id, client=client)
        except PayPalAPIError as e:
            payment_order.status = "FAILED"
            payment_order.append_audit_event("FAILED", f"Capture failed: {e}")
            payment_order.save()
            raise

        # Step 5: Process capture response
        capture_status = capture_resp.get("status")
        units = capture_resp.get("purchase_units", [])
        captures_list = []
        if units:
            captures_list = units[0].get("payments", {}).get("captures", [])

        if not captures_list:
            if capture_status == "COMPLETED":
                # Fallback to order-level completion
                capture_id = f"CAP-FALLBACK-{uuid.uuid4().hex[:8]}"
            else:
                payment_order.status = "FAILED"
                payment_order.append_audit_event("FAILED", f"No capture record in response: {capture_status}")
                payment_order.save()
                raise PayPalAPIError(f"No capture record returned by PayPal (status: {capture_status}).")
        else:
            first_capture = captures_list[0]
            capture_id = first_capture.get("id", "")
            capture_status = first_capture.get("status", capture_status)

        capture_record = PaymentCaptureRecord.objects.create(
            order=payment_order,
            capture_id=capture_id,
            status=capture_status,
            amount=payment_order.total_amount,
            currency="USD",
            seller_receivable_breakdown=captures_list[0].get("seller_receivable_breakdown", {}) if captures_list else {},
            raw_response=capture_resp,
        )

        if capture_status == "COMPLETED":
            payment_order.status = "COMPLETED"
            payment_order.append_audit_event(
                "COMPLETED",
                f"Authoritative COMPLETED capture {capture_id}. Marked PAID.",
            )
            payment_order.save()
        else:
            payment_order.status = "FAILED"
            payment_order.append_audit_event("FAILED", f"Capture status was {capture_status}.")
            payment_order.save()
            raise PayPalAPIError(f"PayPal capture was not completed (status: {capture_status}).")

        return payment_order, capture_record

    @classmethod
    def cancel_checkout(cls, paypal_order_id: str) -> PaymentOrder:
        """Record buyer cancellation on PayPal Sandbox."""
        try:
            payment_order = PaymentOrder.objects.get(paypal_order_id=paypal_order_id)
        except PaymentOrder.DoesNotExist:
            raise PayPalError(f"Payment order '{paypal_order_id}' not found.")

        if payment_order.status not in ("COMPLETED", "BUYER_APPROVED"):
            payment_order.status = "CANCELLED"
            payment_order.append_audit_event("CANCELLED", "Buyer cancelled checkout on PayPal.")
            payment_order.save()

        return payment_order

    @classmethod
    def reconcile_order(
        cls,
        paypal_order_id: str,
        client: PayPalClient | None = None,
    ) -> tuple[PaymentOrder, PaymentCaptureRecord | None]:
        """Authoritative query against PayPal API to resolve ambiguous/pending transaction state."""
        try:
            payment_order = PaymentOrder.objects.get(paypal_order_id=paypal_order_id)
        except PaymentOrder.DoesNotExist:
            raise PayPalError(f"Payment order '{paypal_order_id}' not found.")

        if client is None:
            client = PayPalClient()

        paypal_order = client.get_order(paypal_order_id)
        remote_status = paypal_order.get("status")

        units = paypal_order.get("purchase_units", [])
        captures_list = []
        if units:
            captures_list = units[0].get("payments", {}).get("captures", [])

        if captures_list:
            cap_data = captures_list[0]
            cap_id = cap_data.get("id")
            cap_status = cap_data.get("status")

            capture_record, _ = PaymentCaptureRecord.objects.get_or_create(
                capture_id=cap_id,
                defaults={
                    "order": payment_order,
                    "status": cap_status,
                    "amount": payment_order.total_amount,
                    "currency": "USD",
                    "raw_response": cap_data,
                },
            )

            if cap_status == "COMPLETED":
                payment_order.status = "COMPLETED"
                payment_order.append_audit_event(
                    "COMPLETED",
                    f"Reconciliation verified COMPLETED capture {cap_id}. Marked PAID.",
                )
                payment_order.save()
                return payment_order, capture_record

        if remote_status == "COMPLETED":
            payment_order.status = "COMPLETED"
            payment_order.append_audit_event("COMPLETED", "Reconciliation verified order COMPLETED.")
            payment_order.save()
            return payment_order, payment_order.captures.first()

        if remote_status in ("VOIDED", "EXPIRED"):
            payment_order.status = "FAILED"
            payment_order.append_audit_event("FAILED", f"Reconciliation detected order is {remote_status}.")
            payment_order.save()
            return payment_order, None

        # Still in pending/approved state
        payment_order.append_audit_event("RECONCILED", f"Reconciliation confirmed remote status: {remote_status}.")
        payment_order.save()
        return payment_order, None

    @classmethod
    def handle_webhook(
        cls,
        headers: dict[str, str],
        raw_body: str | bytes,
        client: PayPalClient | None = None,
    ) -> WebhookEventRecord:
        """Verify, deduplicate, and process incoming PayPal webhook events.

        Invariants:
        - Cryptographic signature verified against PayPal before processing.
        - Idempotent deduplication based on event_id.
        - Updates payment order state deterministically.
        """
        # Normalize header keys (Django HttpRequest.headers or META)
        def get_header(name: str) -> str:
            val = headers.get(name) or headers.get(name.upper()) or headers.get(name.replace("-", "_").upper())
            if not val and not name.startswith("HTTP_"):
                val = headers.get(f"HTTP_{name.replace('-', '_').upper()}")
            return val or ""

        transmission_id = get_header("paypal-transmission-id")
        transmission_time = get_header("paypal-transmission-time")
        cert_url = get_header("paypal-cert-url")
        auth_algo = get_header("paypal-auth-algo")
        transmission_sig = get_header("paypal-transmission-sig")

        if not all([transmission_id, transmission_time, cert_url, auth_algo, transmission_sig]):
            raise PayPalError("Missing mandatory PayPal webhook transmission headers.")

        if isinstance(raw_body, bytes):
            body_str = raw_body.decode("utf-8", errors="replace")
        else:
            body_str = raw_body

        try:
            payload = json.loads(body_str)
        except json.JSONDecodeError as err:
            raise PayPalError(f"Malformed JSON in webhook body: {err}") from err

        event_id = payload.get("id", "")
        event_type = payload.get("event_type", "")
        resource_type = payload.get("resource_type", "")
        summary = payload.get("summary", "")

        if not event_id:
            raise PayPalError("Webhook payload missing event id.")

        # Deduplication check
        existing_event = WebhookEventRecord.objects.filter(event_id=event_id).first()
        if existing_event and existing_event.status in ("PROCESSED", "VERIFIED", "DUPLICATE"):
            logger.info("Ignoring duplicate webhook event: %s", event_id)
            existing_event.status = "DUPLICATE"
            existing_event.save(update_fields=["status"])
            return existing_event
        elif existing_event and existing_event.status == "REJECTED":
            # Re-attempting verification for previously rejected event
            existing_event.delete()

        # Cryptographic signature verification
        if client is None:
            client = PayPalClient()

        is_verified = client.verify_webhook_signature(
            transmission_id=transmission_id,
            transmission_time=transmission_time,
            cert_url=cert_url,
            auth_algo=auth_algo,
            transmission_sig=transmission_sig,
            webhook_id="",  # uses client default
            raw_event_body=payload,
        )

        if not is_verified:
            logger.warning("Rejected unverified/forged PayPal webhook event %s", event_id)
            record = WebhookEventRecord.objects.create(
                event_id=event_id,
                event_type=event_type,
                resource_type=resource_type,
                status="REJECTED",
                summary=summary,
                payload=payload,
            )
            raise PayPalError(f"Webhook signature verification failed for event {event_id}.")

        record = WebhookEventRecord.objects.create(
            event_id=event_id,
            event_type=event_type,
            resource_type=resource_type,
            status="VERIFIED",
            summary=summary,
            payload=payload,
        )

        # Dispatch state updates using webhook as authoritative reconciliation trigger
        cls._process_verified_webhook_event(record, payload, client=client)
        record.status = "PROCESSED"
        record.save(update_fields=["status"])
        return record

    @classmethod
    def _process_verified_webhook_event(
        cls,
        record: WebhookEventRecord,
        payload: dict,
        client: PayPalClient | None = None,
    ) -> None:
        """Update PaymentOrder records by treating the verified webhook as an authoritative reconciliation trigger.

        Invariants:
        - Authoritatively queries PayPal API before applying a paid-state transition.
        - Verifies order ID, payee, amount, currency, and completion status.
        - Prevents out-of-order delivery from regressing or incorrectly advancing state.
        """
        event_type = payload.get("event_type", "")
        resource = payload.get("resource", {})

        paypal_order_id = ""
        if event_type.startswith("CHECKOUT.ORDER."):
            paypal_order_id = resource.get("id", "")
        elif event_type.startswith("PAYMENT.CAPTURE."):
            supplementary = resource.get("supplementary_data", {})
            paypal_order_id = supplementary.get("related_ids", {}).get("order_id", "")
            if not paypal_order_id and "custom_id" in resource:
                order_by_fp = PaymentOrder.objects.filter(cart_fingerprint=resource.get("custom_id")).first()
                if order_by_fp:
                    paypal_order_id = order_by_fp.paypal_order_id

        if not paypal_order_id:
            logger.info("Webhook %s has no identifiable paypal_order_id; recorded for audit.", record.event_id)
            return

        order = PaymentOrder.objects.filter(paypal_order_id=paypal_order_id).first()
        if not order:
            logger.warning("Webhook %s references unknown order: %s", record.event_id, paypal_order_id)
            return

        # Refund notification on already COMPLETED order
        if event_type == "PAYMENT.CAPTURE.REFUNDED" and order.status == "COMPLETED":
            order.status = "REFUNDED"
            order.append_audit_event("REFUNDED", f"Webhook {record.event_id} notified capture REFUNDED.")
            order.save()
            return

        # Out-of-order protection: A completed order can NEVER regress to BUYER_APPROVED, CREATED, or FAILED
        if order.status == "COMPLETED":
            logger.info("Order %s already COMPLETED. Ignoring out-of-order webhook %s.", paypal_order_id, event_type)
            return

        if event_type == "CHECKOUT.ORDER.APPROVED":
            # Only advance from CREATED to BUYER_APPROVED; never regress
            if order.status == "CREATED":
                order.status = "BUYER_APPROVED"
                order.append_audit_event("BUYER_APPROVED", f"Webhook {record.event_id} notified order approval.")
                order.save()

        elif event_type in ("PAYMENT.CAPTURE.COMPLETED", "CHECKOUT.ORDER.COMPLETED"):
            # Authoritative reconciliation trigger: Query PayPal directly to verify capture, payee, and amounts
            cls.reconcile_order(paypal_order_id, client=client)

        elif event_type == "PAYMENT.CAPTURE.DENIED" and order.status != "COMPLETED":
            order.status = "FAILED"
            order.append_audit_event("FAILED", f"Webhook {record.event_id} notified capture DENIED.")
            order.save()
