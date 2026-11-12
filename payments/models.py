"""Domain models for AI Cart (formerly TrustCart) Phase P6: PayPal Orders, Captures, and Webhook Audit Records.

Governing Invariants:
- Payment orders link directly to consumed single-use PurchaseApprovals.
- Immutable cart fingerprint and approved amount breakdown are preserved.
- Monies are stored and computed strictly as Decimal.
- Stable, distinct idempotency keys for Order Creation and Capture.
- Complete state machine: CREATED -> BUYER_APPROVED -> COMPLETED / PENDING_RECONCILIATION / FAILED.
"""

import uuid
from decimal import Decimal

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone

from contracts.models import PurchaseContract
from orders.models import PurchaseApproval, PurchaseProposal


class PaymentOrder(models.Model):
    """Authoritative record linking a consumed PurchaseApproval to a PayPal Orders v2 transaction."""

    STATUS_CHOICES = [
        ("CREATED", "Created / Awaiting Buyer Approval"),
        ("BUYER_APPROVED", "Buyer Approved at PayPal / Ready for Capture"),
        ("COMPLETED", "Captured & Paid"),
        ("PENDING_RECONCILIATION", "Pending Reconciliation (Timeout / Ambiguous)"),
        ("FAILED", "Capture Failed / Denied"),
        ("CANCELLED", "Buyer Cancelled at PayPal"),
        ("REFUNDED", "Refunded"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    approval = models.OneToOneField(
        PurchaseApproval,
        on_delete=models.PROTECT,
        related_name="payment_order",
    )
    proposal = models.ForeignKey(
        PurchaseProposal,
        on_delete=models.PROTECT,
        related_name="payment_orders",
    )
    contract = models.ForeignKey(
        PurchaseContract,
        on_delete=models.PROTECT,
        related_name="payment_orders",
    )
    paypal_order_id = models.CharField(max_length=64, unique=True, db_index=True)
    cart_fingerprint = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="CREATED", db_index=True)
    payee_id = models.CharField(max_length=128)
    currency = models.CharField(max_length=3, default="USD")

    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    base_amount = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    create_idempotency_key = models.CharField(max_length=64, unique=True)
    capture_idempotency_key = models.CharField(max_length=64, unique=True)
    paypal_approval_url = models.URLField(max_length=512, blank=True)

    audit_log = models.JSONField(default=list, blank=True, encoder=DjangoJSONEncoder)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Payment Order"
        verbose_name_plural = "Payment Orders"

    def __str__(self) -> str:
        return f"PaymentOrder {self.paypal_order_id} [{self.status}] ${self.total_amount} {self.currency}"

    def append_audit_event(self, event_type: str, details: str) -> None:
        """Record an audit trail event for payment state transitions."""
        self.audit_log.append(
            {
                "timestamp": timezone.now().isoformat(),
                "event": event_type,
                "details": details,
                "status": self.status,
            }
        )


class PaymentCaptureRecord(models.Model):
    """Authoritative capture record returned by PayPal upon successful or failed server-side capture."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        PaymentOrder,
        on_delete=models.CASCADE,
        related_name="captures",
    )
    capture_id = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(max_length=32, db_index=True)  # COMPLETED, DENIED, etc.
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    seller_receivable_breakdown = models.JSONField(default=dict, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    captured_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-captured_at"]
        verbose_name = "Payment Capture Record"
        verbose_name_plural = "Payment Capture Records"

    def __str__(self) -> str:
        return f"Capture {self.capture_id} [{self.status}] ${self.amount} {self.currency}"


class WebhookEventRecord(models.Model):
    """Immutable log of incoming PayPal webhook notifications."""

    STATUS_CHOICES = [
        ("VERIFIED", "Signature Verified"),
        ("REJECTED", "Invalid Signature / Untrusted"),
        ("DUPLICATE", "Duplicate Event Skipped"),
        ("PROCESSED", "Processed State Transition"),
        ("FAILED", "Processing Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.CharField(max_length=64, unique=True, db_index=True)
    event_type = models.CharField(max_length=64, db_index=True)
    resource_type = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="VERIFIED", db_index=True)
    summary = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict)
    received_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-received_at"]
        verbose_name = "Webhook Event Record"
        verbose_name_plural = "Webhook Event Records"

    def __str__(self) -> str:
        return f"Webhook {self.event_id} [{self.event_type}] ({self.status})"
