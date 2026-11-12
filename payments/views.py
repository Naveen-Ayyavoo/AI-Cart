"""Views for AI Cart (formerly TrustCart) Phase P6: PayPal Sandbox Checkout, Return, Capture, and Webhook Listener.

Governing Invariants:
- Checkout creation is CSRF-protected POST requiring an approved PurchaseApproval.
- Return handler NEVER trusts browser redirect data; executes authoritative server query.
- Server performs deterministic pre-capture revalidation and executes capture.
- Webhook listener verifies cryptographic signatures via official PayPal API.
- All checkout, pending, and receipt templates prominently display controlled demo merchant disclosure.
"""

import logging
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from contracts.access import authorize_contract_access, ensure_session_key
from orders.models import DEMO_PAYEE_DISCLOSURE, ApprovalError, PurchaseApproval
from payments.client import PayPalError
from payments.models import PaymentOrder
from payments.services import PaymentService, PayPalRevalidationError

logger = logging.getLogger(__name__)


def checkout_initiate(request: HttpRequest, token: str) -> HttpResponse:
    """Initiate PayPal Sandbox checkout for an approved proposal.

    Invariants:
    - Must be a CSRF-protected POST request.
    - Atomically consumes approval token (1-use).
    - Redirects buyer to PayPal Sandbox approval URL.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("Checkout initiation requires a CSRF-protected POST request.")

    return_url = request.build_absolute_uri(reverse("payments:checkout_return"))
    cancel_url = request.build_absolute_uri(reverse("payments:checkout_cancel"))

    approval_record = PurchaseApproval.objects.select_related("proposal", "proposal__contract").filter(token=token).first()
    if approval_record:
        authorize_contract_access(request, approval_record.proposal.contract)

    try:
        _payment_order, approve_url = PaymentService.initiate_checkout(
            approval_token=token,
            return_url=return_url,
            cancel_url=cancel_url,
        )
        return redirect(approve_url)
    except ApprovalError as e:
        logger.warning("Approval error during checkout initiation: %s", e)
        messages.error(request, f"Approval error: {e}")
        if approval_record:
            return redirect("approval_detail", public_ref=approval_record.public_ref)
        return redirect("home")
    except PayPalError as e:
        logger.error("PayPal error during checkout initiation: %s", e)
        messages.error(request, f"PayPal error: {e}")
        if approval_record:
            return redirect("approval_detail", public_ref=approval_record.public_ref)
        return redirect("home")


def checkout_return(request: HttpRequest) -> HttpResponse:
    """Handle buyer return from PayPal Sandbox.

    Invariants:
    - Never trusts query parameters as proof of payment.
    - Queries PayPal Orders v2 server-side.
    - Revalidates approved cart fingerprint, items, payee, and amount before capture.
    - Executes server-side capture and marks order PAID only on COMPLETED status.
    """
    paypal_order_id = request.GET.get("token") or request.GET.get("order_id")
    if not paypal_order_id:
        return render(
            request,
            "payments/failed.html",
            {
                "order": None,
                "error_message": "Missing PayPal order token parameter.",
                "demo_payee_disclosure": DEMO_PAYEE_DISCLOSURE,
            },
            status=400,
        )

    existing_order = PaymentOrder.objects.select_related("contract").filter(paypal_order_id=paypal_order_id).first()
    if existing_order:
        authorize_contract_access(request, existing_order.contract)

    try:
        order, _capture = PaymentService.complete_checkout(paypal_order_id)
        if order.status in ("COMPLETED", "PENDING_RECONCILIATION"):
            # Redirect cleanly to strip transient PayPal query parameters (?token=..., PayerID=...)
            return redirect("payments:order_detail", paypal_order_id=order.paypal_order_id)
        return render(
            request,
            "payments/failed.html",
            {
                "order": order,
                "error_message": f"Payment status: {order.status}",
                "demo_payee_disclosure": DEMO_PAYEE_DISCLOSURE,
            },
        )
    except PayPalRevalidationError as e:
        logger.error("Pre-capture revalidation failed for order %s: %s", paypal_order_id, e)
        order = PaymentOrder.objects.filter(paypal_order_id=paypal_order_id).first()
        return render(
            request,
            "payments/failed.html",
            {
                "order": order,
                "error_message": f"Security Revalidation Failed: {e}",
                "demo_payee_disclosure": DEMO_PAYEE_DISCLOSURE,
            },
        )
    except PayPalError as e:
        logger.error("Error completing checkout for order %s: %s", paypal_order_id, e)
        order = PaymentOrder.objects.filter(paypal_order_id=paypal_order_id).first()
        return render(
            request,
            "payments/failed.html",
            {
                "order": order,
                "error_message": f"PayPal Checkout Error: {e}",
                "demo_payee_disclosure": DEMO_PAYEE_DISCLOSURE,
            },
        )


def checkout_cancel(request: HttpRequest) -> HttpResponse:
    """Handle buyer cancellation from PayPal Sandbox."""
    paypal_order_id = request.GET.get("token") or request.GET.get("order_id")
    order = None
    if paypal_order_id:
        existing_order = PaymentOrder.objects.select_related("contract").filter(paypal_order_id=paypal_order_id).first()
        if existing_order:
            authorize_contract_access(request, existing_order.contract)
        try:
            order = PaymentService.cancel_checkout(paypal_order_id)
        except PayPalError as e:
            logger.warning("Error cancelling checkout for order %s: %s", paypal_order_id, e)
            order = PaymentOrder.objects.filter(paypal_order_id=paypal_order_id).first()

    return render(
        request,
        "payments/cancelled.html",
        {
            "order": order,
            "demo_payee_disclosure": DEMO_PAYEE_DISCLOSURE,
        },
    )


def _verify_order_receipt_amounts(order: PaymentOrder, capture) -> dict:
    """Verify persisted PaymentOrder monetary breakdown against PayPal capture evidence."""
    expected_total = (
        order.base_amount + order.shipping_amount + order.tax_amount + order.fee_amount
    )
    order_math_matches = order.total_amount == expected_total

    capture_amount = None
    capture_currency = None
    capture_matches_order = False
    if capture is not None:
        capture_amount = capture.amount
        capture_currency = capture.currency
        # Prefer explicit seller receivable gross_amount or capture payload amount if present
        raw = capture.raw_response if isinstance(capture.raw_response, dict) else {}
        raw_amt = raw.get("amount", {}) if isinstance(raw.get("amount"), dict) else {}
        if raw_amt.get("value"):
            try:
                capture_amount = Decimal(str(raw_amt["value"]))
                capture_currency = str(raw_amt.get("currency_code") or capture_currency)
            except (ValueError, InvalidOperation):
                pass
        capture_matches_order = (
            capture_amount == order.total_amount
            and (capture_currency or "").upper() == (order.currency or "").upper()
        )

    return {
        "expected_total": expected_total,
        "order_math_matches": order_math_matches,
        "capture_amount": capture_amount,
        "capture_currency": capture_currency,
        "capture_matches_order": capture_matches_order,
        "amounts_verified": bool(order_math_matches and (capture is None or capture_matches_order)),
    }


def payment_history(request: HttpRequest) -> HttpResponse:
    """Session-scoped Payment History displaying actual persisted transactions only."""
    session_key = ensure_session_key(request)
    status_filter = (request.GET.get("status") or "").strip().upper()

    orders_qs = (
        PaymentOrder.objects.select_related("contract", "proposal", "proposal__product")
        .prefetch_related("captures")
        .filter(contract__owner_session_key=session_key)
        .order_by("-created_at")
    )

    pending_statuses = {"CREATED", "BUYER_APPROVED", "PENDING_RECONCILIATION"}
    if status_filter == "PENDING":
        orders_qs = orders_qs.filter(status__in=pending_statuses)
    elif status_filter in {"COMPLETED", "FAILED", "CANCELLED", "REFUNDED"}:
        orders_qs = orders_qs.filter(status=status_filter)
    else:
        status_filter = "ALL"

    status_display_map = {
        "COMPLETED": ("Completed", "tc-badge-success", True, True),
        "PENDING_RECONCILIATION": ("Pending Reconciliation", "tc-badge-pref", False, False),
        "CREATED": ("Pending Approval", "tc-badge-pref", False, False),
        "BUYER_APPROVED": ("Pending Capture", "tc-badge-pref", False, False),
        "FAILED": ("Failed", "tc-badge-danger", False, False),
        "CANCELLED": ("Cancelled", "tc-badge-outline", False, False),
        "REFUNDED": ("Refunded", "tc-badge-spec", False, True),
    }

    history_rows = []
    for order in orders_qs:
        label, badge_cls, is_paid, has_receipt = status_display_map.get(
            order.status,
            (order.status.title(), "tc-badge-outline", False, False),
        )
        history_rows.append(
            {
                "order": order,
                "product_title": order.proposal.product.title if order.proposal and order.proposal.product else "Product order",
                "merchant_name": order.proposal.source_merchant if order.proposal else "",
                "status_label": label,
                "badge_class": badge_cls,
                "is_paid": is_paid,
                "has_receipt": has_receipt,
                "detail_url": reverse("payments:order_detail", args=[order.paypal_order_id]),
            }
        )

    return render(
        request,
        "payments/history.html",
        {
            "history_rows": history_rows,
            "status_filter": status_filter,
            "demo_payee_disclosure": DEMO_PAYEE_DISCLOSURE,
        },
    )


def order_detail(request: HttpRequest, paypal_order_id: str) -> HttpResponse:
    """View payment receipt and transaction history."""
    order = get_object_or_404(
        PaymentOrder.objects.select_related("approval", "proposal", "contract"),
        paypal_order_id=paypal_order_id,
    )
    authorize_contract_access(request, order.contract)
    latest_capture = order.captures.filter(status="COMPLETED").first() or order.captures.first()

    if order.status in ("COMPLETED", "REFUNDED"):
        receipt_audit = _verify_order_receipt_amounts(order, latest_capture)
        return render(
            request,
            "payments/receipt.html",
            {
                "order": order,
                "capture": latest_capture,
                "receipt_audit": receipt_audit,
                "demo_payee_disclosure": DEMO_PAYEE_DISCLOSURE,
            },
        )
    elif order.status == "PENDING_RECONCILIATION":
        return render(
            request,
            "payments/pending.html",
            {
                "order": order,
                "title": "Payment Pending Reconciliation",
                "message": "A network delay occurred while confirming payment. AI Cart is waiting for confirmation from PayPal before finalizing your order.",
                "demo_payee_disclosure": DEMO_PAYEE_DISCLOSURE,
            },
        )
    elif order.status == "CREATED":
        return render(
            request,
            "payments/pending.html",
            {
                "order": order,
                "title": "Awaiting PayPal Sandbox Buyer Approval",
                "message": "This order has been initialized and is awaiting explicit approval on PayPal Sandbox.",
                "demo_payee_disclosure": DEMO_PAYEE_DISCLOSURE,
            },
        )
    elif order.status == "BUYER_APPROVED":
        return render(
            request,
            "payments/pending.html",
            {
                "order": order,
                "title": "Buyer Approved — Ready for Server Capture",
                "message": "Buyer approval confirmed. Ready for server-side pre-capture revalidation and capture execution.",
                "demo_payee_disclosure": DEMO_PAYEE_DISCLOSURE,
            },
        )
    elif order.status == "CANCELLED":
        return render(
            request,
            "payments/cancelled.html",
            {
                "order": order,
                "demo_payee_disclosure": DEMO_PAYEE_DISCLOSURE,
            },
        )
    else:
        return render(
            request,
            "payments/failed.html",
            {
                "order": order,
                "error_message": f"Payment status: {order.status}",
                "demo_payee_disclosure": DEMO_PAYEE_DISCLOSURE,
            },
        )


def order_reconcile(request: HttpRequest, paypal_order_id: str) -> HttpResponse:
    """Manually trigger authoritative reconciliation for an order in PENDING_RECONCILIATION."""
    if request.method != "POST":
        return HttpResponseBadRequest("Reconciliation requires a POST request.")

    order_obj = get_object_or_404(PaymentOrder.objects.select_related("contract"), paypal_order_id=paypal_order_id)
    authorize_contract_access(request, order_obj.contract)

    try:
        order, _ = PaymentService.reconcile_order(paypal_order_id)
        messages.info(request, f"Reconciliation complete. Status: {order.status}")
    except PayPalError as e:
        messages.error(request, f"Reconciliation error: {e}")

    return redirect("payments:order_detail", paypal_order_id=paypal_order_id)


@csrf_exempt
def paypal_webhook_listener(request: HttpRequest) -> HttpResponse:
    """Receive and process incoming PayPal Sandbox webhook notifications.

    Invariants:
    - CSRF-exempt (as required for external webhooks).
    - Verifies cryptographic signature before reading/processing payload.
    - Idempotent: duplicate event IDs return 200 without reprocessing.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("Webhooks require POST requests.")

    try:
        event_record = PaymentService.handle_webhook(
            headers=request.headers,
            raw_body=request.body,
        )
        return JsonResponse(
            {
                "status": "ok",
                "event_id": event_record.event_id,
                "record_status": event_record.status,
            },
            status=200,
        )
    except PayPalError as e:
        logger.warning("PayPal webhook processing error: %s", e)
        return HttpResponseBadRequest(f"Webhook error: {e}")
    except (ValueError, KeyError) as e:
        logger.error("Unexpected error in webhook listener: %s", e)
        return HttpResponseBadRequest("Internal webhook error")
