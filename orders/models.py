"""Domain models for AI Cart (formerly TrustCart) Phase P5: Purchase Proposals, Cryptographic Binding, and Approval Tokens.

Implements APPR-01, APPR-02, APPR-03, APPR-04, APPR-05:
- Exact SHA-256 cart fingerprinting.
- Separation of Channel3 source merchant from PayPal demo payee.
- Complete known payable breakdown with unknown charges blocking.
- Time-limited (15-minute TTL), single-use approval token.
- Atomic state transitions protecting against replay and race conditions.
"""

import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, models, transaction
from django.urls import reverse
from django.utils import timezone

from catalog.models import ProductEvidence
from contracts.access import generate_unique_public_ref
from contracts.models import PurchaseContract
from orders.fingerprint import CartFingerprintParams, compute_cart_fingerprint
from policies.models import PolicyEvaluationReport

DEFAULT_DEMO_PAYEE_ID = getattr(
    settings, "PAYPAL_DEMO_MERCHANT_ID", "sb-merchant-trustcart@business.example.com"
)
APPROVAL_TTL_MINUTES = 15
DEMO_PAYEE_DISCLOSURE = (
    "Controlled Demo Payee Boundary: In accordance with PayPal Sandbox rules, payment will "
    "settle with AI Cart's (formerly TrustCart) controlled demo merchant account, not external retail settlement."
)


class ApprovalError(Exception):
    """Base exception for approval domain errors."""


class ApprovalAlreadyConsumedError(ApprovalError):
    """Raised when an approval token has already been consumed (replay / double-spend attempt)."""


class ApprovalExpiredError(ApprovalError):
    """Raised when an approval token has expired beyond its 15-minute TTL."""


class ApprovalInvalidError(ApprovalError):
    """Raised when an approval token is invalid, tampered with, or not approved."""


class ApprovalLockError(ApprovalError):
    """Raised when database lock contention prevents atomic consumption (fails closed)."""


class PurchaseProposal(models.Model):
    """Structured proposal representing an exact candidate purchase ready for explicit buyer confirmation.

    Separates Channel3 source_merchant from PayPal payee_id.
    Includes complete known payable breakdown: base, shipping, tax, fees, and total.
    """

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("PROPOSED", "Proposed"),
        ("APPROVED", "Approved"),
        ("SUPERSEDED", "Superseded"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_ref = models.SlugField(max_length=96, unique=True, db_index=True, blank=True)
    contract = models.ForeignKey(
        PurchaseContract,
        on_delete=models.PROTECT,
        related_name="proposals",
    )
    product = models.ForeignKey(
        ProductEvidence,
        on_delete=models.PROTECT,
        related_name="proposals",
    )
    policy_report = models.ForeignKey(
        PolicyEvaluationReport,
        on_delete=models.PROTECT,
        related_name="proposals",
        null=True,
        blank=True,
    )

    # Merchant & Payee Separation
    source_merchant = models.CharField(max_length=255)
    payee_id = models.CharField(max_length=255, default=DEFAULT_DEMO_PAYEE_ID)

    # Variant and SKU
    variant_id = models.CharField(max_length=255, blank=True)
    sku = models.CharField(max_length=255, blank=True)

    # Quantity and Complete Known Payable Amounts (Decimal only)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    base_amount = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")

    # Critical Charge Confirmation Gate
    charges_confirmed = models.BooleanField(
        default=True,
        help_text="True if shipping, taxes, and fees are confirmed; False if unknown.",
    )

    # SHA-256 Cryptographic Cart Fingerprint
    cart_fingerprint = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="PROPOSED", db_index=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Purchase Proposal"
        verbose_name_plural = "Purchase Proposals"

    def __str__(self) -> str:
        return f"Proposal [{self.id}] for {self.product.title} (${self.total_amount} {self.currency})"

    def clean(self) -> None:
        """Validate monetary calculations and bounds."""
        expected_base = self.unit_price * Decimal(self.quantity)
        if self.base_amount != expected_base:
            raise ValidationError({"base_amount": f"Base amount must equal unit_price * quantity ({expected_base})."})

        expected_total = self.base_amount + self.shipping_amount + self.tax_amount + self.fee_amount
        if self.total_amount != expected_total:
            raise ValidationError({"total_amount": f"Total amount must equal base + shipping + tax + fees ({expected_total})."})

        if self.currency != "USD":
            raise ValidationError({"currency": "Currency must be USD."})

        if self.total_amount > self.contract.max_budget:
            raise ValidationError({"total_amount": f"Total amount (${self.total_amount}) exceeds contract budget ceiling (${self.contract.max_budget})."})

    def get_fingerprint_params(self) -> CartFingerprintParams:
        """Construct the canonical fingerprint parameter block."""
        return CartFingerprintParams(
            product_id=self.product.product_id,
            variant_id=self.variant_id or self.product.variant_id or "",
            sku=self.sku or self.product.sku or "",
            source_merchant=self.source_merchant or self.product.source_merchant,
            payee_id=self.payee_id,
            quantity=self.quantity,
            unit_price=self.unit_price,
            base_amount=self.base_amount,
            shipping_amount=self.shipping_amount,
            tax_amount=self.tax_amount,
            fee_amount=self.fee_amount,
            total_amount=self.total_amount,
            currency=self.currency,
            contract_id=str(self.contract.id),
            contract_version=self.contract.version,
        )

    def calculate_fingerprint(self) -> str:
        return compute_cart_fingerprint(self.get_fingerprint_params())

    def save(self, *args, **kwargs):
        if not self.public_ref:
            label = self.contract.category if self.contract_id else "purchase-item"
            self.public_ref = generate_unique_public_ref(
                "PP",
                label,
                PurchaseProposal,
                fallback="purchase-item",
            )
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("proposal_detail", kwargs={"public_ref": self.public_ref})

    def verify_fingerprint(self) -> bool:
        """Recompute and verify that the cart fingerprint matches current database values."""
        return self.cart_fingerprint == self.calculate_fingerprint()


def _default_approval_expiry():
    return timezone.now() + timedelta(minutes=APPROVAL_TTL_MINUTES)


class PurchaseApproval(models.Model):
    """Single-use, time-limited, cryptographically bound purchase approval token.

    Invariant:
    - Sits strictly between Phase P4 policy verification and Phase P6 PayPal checkout.
    - Does NOT execute or capture PayPal payments directly.
    - Single-use: Consumed atomically exactly once via select_for_update().
    - Expiring: 15-minute strict TTL.
    """

    STATE_CHOICES = [
        ("PENDING", "Pending Buyer Approval"),
        ("APPROVED", "Approved by Buyer"),
        ("CONSUMED", "Consumed (Payment Initiated)"),
        ("EXPIRED", "Expired"),
        ("VOIDED", "Voided (Cart Mutated)"),
        ("REJECTED", "Rejected by Buyer"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_ref = models.SlugField(max_length=96, unique=True, db_index=True, blank=True)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    proposal = models.OneToOneField(
        PurchaseProposal,
        on_delete=models.PROTECT,
        related_name="approval",
    )
    cart_fingerprint = models.CharField(max_length=64, db_index=True)
    state = models.CharField(max_length=32, choices=STATE_CHOICES, default="PENDING", db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(default=_default_approval_expiry)
    approved_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    shopper_ip = models.GenericIPAddressField(null=True, blank=True)
    audit_log = models.JSONField(default=list, blank=True, encoder=DjangoJSONEncoder)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Purchase Approval"
        verbose_name_plural = "Purchase Approvals"

    def save(self, *args, **kwargs):
        if not self.public_ref:
            label = (
                self.proposal.contract.category
                if self.proposal_id and self.proposal.contract_id
                else "purchase-approval"
            )
            self.public_ref = generate_unique_public_ref(
                "PA",
                label,
                PurchaseApproval,
                fallback="purchase-approval",
            )
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("approval_detail", kwargs={"public_ref": self.public_ref})

    def __str__(self) -> str:
        return f"Approval [{self.token[:8]}] - {self.state} (expires {self.expires_at})"

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def append_audit_event(self, event_type: str, details: str) -> None:
        self.audit_log.append(
            {
                "timestamp": timezone.now().isoformat(),
                "event": event_type,
                "details": details,
                "state": self.state,
            }
        )

    def is_valid_for_consumption(self) -> tuple[bool, str]:
        """Validate all cryptographic invariants before consumption."""
        if self.state == "CONSUMED":
            return False, "Approval token has already been consumed."
        if self.state != "APPROVED":
            return False, f"Approval token is in '{self.state}' state (must be APPROVED)."
        if self.is_expired():
            return False, "Approval token has expired (15-minute TTL exceeded)."
        if self.proposal.contract.state != "CONFIRMED":
            return False, f"Underlying Purchase Contract is no longer confirmed ({self.proposal.contract.state})."
        if not self.proposal.verify_fingerprint():
            return False, "Cart fingerprint mismatch: purchase parameters have been altered."
        if self.cart_fingerprint != self.proposal.cart_fingerprint:
            return False, "Approval token fingerprint mismatch."
        return True, "Approval is valid."

    @classmethod
    def create_pending_approval(cls, proposal: PurchaseProposal, shopper_ip: str | None = None) -> "PurchaseApproval":
        """Generate a pending approval token bound to the proposal's cart fingerprint."""
        token = uuid.uuid4().hex
        approval = cls.objects.create(
            token=token,
            proposal=proposal,
            cart_fingerprint=proposal.cart_fingerprint,
            state="PENDING",
            shopper_ip=shopper_ip,
            audit_log=[
                {
                    "timestamp": timezone.now().isoformat(),
                    "event": "CREATED",
                    "details": f"Pending approval created for Proposal {proposal.id}",
                    "state": "PENDING",
                }
            ],
        )
        return approval

    def approve(self, shopper_ip: str | None = None) -> None:
        """Buyer explicitly grants purchase approval."""
        if self.state != "PENDING":
            raise ApprovalInvalidError(f"Cannot approve token in state '{self.state}'.")
        if self.is_expired():
            self.state = "EXPIRED"
            self.save()
            raise ApprovalExpiredError("Cannot approve expired token.")

        self.state = "APPROVED"
        self.approved_at = timezone.now()
        if shopper_ip:
            self.shopper_ip = shopper_ip
        self.append_audit_event("APPROVED", "Explicit positive buyer confirmation recorded.")
        self.save()

        # Update proposal status
        self.proposal.status = "APPROVED"
        self.proposal.save()

    def consume(self, order_reference: str = "") -> None:
        """Atomically consume the approval token using a conditional database UPDATE.

        Guarantees single-use; replay attempts fail immediately.
        Invariants enforced:
        - Matches exact approval record (id=self.id, token=self.token).
        - Requires state == 'APPROVED'.
        - Requires expires_at > current time.
        - Requires consumed_at IS NULL.
        - Verifies expected cart fingerprint.
        - Changes state to 'CONSUMED' and records consumed_at.
        - Checks that exactly one row was updated.
        - Keeps select_for_update only where supported and useful.
        """
        now = timezone.now()

        # Quick in-memory state check
        if self.state == "CONSUMED":
            raise ApprovalAlreadyConsumedError("Approval token has already been consumed.")
        if self.is_expired():
            self.state = "EXPIRED"
            self.save(update_fields=["state"])
            raise ApprovalExpiredError("Approval token has expired.")

        # Ensure fresh proposal and contract data from database
        self.proposal.refresh_from_db()
        self.proposal.contract.refresh_from_db()

        if self.proposal.contract.state != "CONFIRMED":
            self.state = "VOIDED"
            self.append_audit_event(
                "VOIDED",
                f"Token voided: Contract v{self.proposal.contract.version} is {self.proposal.contract.state}.",
            )
            self.save(update_fields=["state", "audit_log"])
            raise ApprovalInvalidError("Underlying Purchase Contract is no longer confirmed.")

        # Recompute expected cart fingerprint from proposal
        expected_fingerprint = self.proposal.calculate_fingerprint()

        # Preliminary integrity check: if tampered or invalid, mark VOIDED immediately
        if not self.proposal.verify_fingerprint() or self.cart_fingerprint != expected_fingerprint:
            self.state = "VOIDED"
            self.append_audit_event("VOIDED", "Token voided: Cart parameters altered.")
            self.save(update_fields=["state", "audit_log"])
            raise ApprovalInvalidError("Cart fingerprint mismatch: purchase parameters have been altered.")

        if self.state != "APPROVED":
            raise ApprovalInvalidError(f"Cannot consume token in state '{self.state}'.")

        with transaction.atomic():
            # Keep select_for_update only where supported and useful (PostgreSQL, MySQL, etc.)
            if connection.features.has_select_for_update:
                try:
                    PurchaseApproval.objects.select_for_update().get(id=self.id)
                except PurchaseApproval.DoesNotExist:
                    raise ApprovalInvalidError(f"Approval token '{self.token}' not found.")

            # Conditional atomic database UPDATE
            rows_updated = PurchaseApproval.objects.filter(
                id=self.id,
                token=self.token,
                cart_fingerprint=expected_fingerprint,
                state="APPROVED",
                expires_at__gt=now,
                consumed_at__isnull=True,
            ).update(
                state="CONSUMED",
                consumed_at=now,
            )

            if rows_updated != 1:
                # Inspect database state to determine exact cause and fail closed
                current = PurchaseApproval.objects.filter(id=self.id).first()
                if not current:
                    raise ApprovalInvalidError("Approval token record not found.")
                if current.state == "CONSUMED" or current.consumed_at is not None:
                    raise ApprovalAlreadyConsumedError("Approval token has already been consumed.")
                if current.expires_at <= now:
                    PurchaseApproval.objects.filter(id=self.id).update(state="EXPIRED")
                    raise ApprovalExpiredError("Approval token has expired.")
                if current.cart_fingerprint != expected_fingerprint:
                    PurchaseApproval.objects.filter(id=self.id).update(state="VOIDED")
                    raise ApprovalInvalidError("Cart fingerprint mismatch: purchase parameters have been altered.")
                if current.state != "APPROVED":
                    raise ApprovalInvalidError(f"Cannot consume token in state '{current.state}'.")
                raise ApprovalInvalidError("Approval consumption failed: conditional transition matched 0 rows.")

            # Exactly one row was updated! Reload from DB and record audit log entry
            self.refresh_from_db()
            self.append_audit_event(
                "CONSUMED",
                f"Token atomically consumed for checkout order reference: {order_reference}",
            )
            self.save(update_fields=["audit_log"])
