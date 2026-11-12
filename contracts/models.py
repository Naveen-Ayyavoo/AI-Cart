"""
Purchase Contract domain models.
Phase P2: Purchase Contract Creation & Confirmation.
Invariants:
- Deterministic backend authority over state machine and validation.
- Decimal precision for monetary amounts (no float).
- Versioning and immutability: material edits create a new draft version.
- Contract confirmation is NOT payment authorization.
"""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from contracts.access import generate_unique_public_ref


class ContractState(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    CONFIRMED = "CONFIRMED", "Confirmed"
    SUPERSEDED = "SUPERSEDED", "Superseded"


class ContractSource(models.TextChoices):
    GEMINI_LIVE = "GEMINI_LIVE", "Gemini Live"
    FALLBACK_PARSER = "FALLBACK_PARSER", "Direct Request Parser"
    DEMO_FIXTURE = "DEMO_FIXTURE", "Demo Fixture"


class PurchaseContract(models.Model):
    """
    Structured Purchase Contract capturing shopper requirements.
    Advisory parsing by Gemini; authoritative validation and lifecycle by deterministic backend.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_ref = models.SlugField(max_length=96, unique=True, db_index=True, blank=True)
    owner_session_key = models.CharField(max_length=64, blank=True, default="", db_index=True)
    version = models.PositiveIntegerField(default=1)
    parent_contract = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revisions",
    )

    # Shopper Input (max 2,000 characters)
    raw_prompt = models.TextField(max_length=2000)

    # Core Requirements
    category = models.CharField(max_length=255)
    product_description = models.TextField()
    max_budget = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    quantity = models.PositiveIntegerField(default=1)

    # Structured Specifications and Negative Constraints
    required_specs = models.JSONField(default=dict, blank=True)
    preferred_specs = models.JSONField(default=dict, blank=True)
    excluded_terms = models.JSONField(default=list, blank=True)
    ambiguous_requirements = models.JSONField(default=list, blank=True)

    # Provenance and Audit
    source = models.CharField(
        max_length=32,
        choices=ContractSource.choices,
        default=ContractSource.GEMINI_LIVE,
    )
    model_used = models.CharField(max_length=64, blank=True)
    extraction_provenance = models.JSONField(default=dict, blank=True)

    # State Machine
    state = models.CharField(
        max_length=16,
        choices=ContractState.choices,
        default=ContractState.DRAFT,
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["state"]),
            models.Index(fields=["source"]),
        ]

    def clean(self):
        """
        Deterministic backend validation enforcing business invariants.
        Valid JSON is NOT proof of valid business requirements.
        """
        super().clean()

        if self.max_budget is None or self.max_budget <= Decimal("0.00"):
            raise ValidationError(
                {"max_budget": "Maximum budget must be greater than $0.00."}
            )

        if self.quantity is None or self.quantity < 1:
            raise ValidationError(
                {"quantity": "Quantity must be an integer of at least 1."}
            )

        if self.currency != "USD":
            raise ValidationError(
                {"currency": "Currency must strictly be USD for US market demo."}
            )

        if self.raw_prompt and len(self.raw_prompt) > 2000:
            raise ValidationError(
                {"raw_prompt": "Raw prompt exceeds maximum limit of 2,000 characters."}
            )

        if not isinstance(self.required_specs, dict):
            raise ValidationError({"required_specs": "Required specs must be a dictionary."})

        if not isinstance(self.preferred_specs, dict):
            raise ValidationError({"preferred_specs": "Preferred specs must be a dictionary."})

        if not isinstance(self.excluded_terms, list):
            raise ValidationError({"excluded_terms": "Excluded terms must be a list."})

        if not isinstance(self.ambiguous_requirements, list):
            raise ValidationError(
                {"ambiguous_requirements": "Ambiguous requirements must be a list."}
            )

    def confirm(self):
        """
        Explicitly confirms the Purchase Contract.
        Locks requirements for product discovery.
        Does NOT constitute purchase approval or payment authorization.
        """
        if self.state == ContractState.CONFIRMED:
            raise ValidationError("This contract has already been confirmed.")
        if self.state == ContractState.SUPERSEDED:
            raise ValidationError("Cannot confirm a superseded contract version.")

        from contracts.interpreter import detect_contract_contradictions

        contradictions = detect_contract_contradictions(self)
        if contradictions:
            raise ValidationError(
                "Shopping requirements conflict with your original request: "
                + " ".join(contradictions)
            )

        self.full_clean()
        self.state = ContractState.CONFIRMED
        self.confirmed_at = timezone.now()
        self.save(update_fields=["state", "confirmed_at", "updated_at"])

    def create_revision(self, reason: str = "", **overrides):
        """
        Creates a new draft version linked to this contract.
        If self is CONFIRMED, marks self as SUPERSEDED and voids any unconsumed
        proposals/approvals bound to this version so old approvals cannot be reused.
        Preserves the original contract record and records revision lineage.
        """
        from django.db import transaction
        from django.utils import timezone as dj_tz

        with transaction.atomic():
            was_confirmed = self.state == ContractState.CONFIRMED
            if was_confirmed:
                self.state = ContractState.SUPERSEDED
                self.save(update_fields=["state", "updated_at"])

            provenance = dict(self.extraction_provenance or {})
            new_budget = overrides.get("max_budget", self.max_budget)
            new_qty = overrides.get("quantity", self.quantity)

            changed_fields = []
            for field_name in (
                "category",
                "product_description",
                "max_budget",
                "currency",
                "quantity",
                "required_specs",
                "preferred_specs",
                "excluded_terms",
                "ambiguous_requirements",
            ):
                if field_name in overrides and overrides[field_name] != getattr(self, field_name):
                    changed_fields.append(field_name)

            provenance["last_revision"] = {
                "previous_contract_id": str(self.id),
                "previous_version": self.version,
                "previous_budget": str(self.max_budget),
                "new_budget": str(new_budget),
                "previous_quantity": self.quantity,
                "new_quantity": new_qty,
                "changed_fields": changed_fields,
                "reason": reason or "criteria_revision",
                "revised_at": dj_tz.now().isoformat(),
            }

            new_data = {
                "version": self.version + 1,
                "parent_contract": self,
                "owner_session_key": self.owner_session_key,
                "raw_prompt": self.raw_prompt,
                "category": self.category,
                "product_description": self.product_description,
                "max_budget": self.max_budget,
                "currency": self.currency,
                "quantity": self.quantity,
                "required_specs": dict(self.required_specs),
                "preferred_specs": dict(self.preferred_specs),
                "excluded_terms": list(self.excluded_terms),
                "ambiguous_requirements": list(self.ambiguous_requirements),
                "source": self.source,
                "model_used": self.model_used,
                "extraction_provenance": provenance,
                "state": ContractState.DRAFT,
                "confirmed_at": None,
            }
            new_data.update(overrides)

            new_contract = PurchaseContract.objects.create(**new_data)

            # Explicitly invalidate any unconsumed proposals & approvals tied to superseded version
            if was_confirmed:
                from orders.models import PurchaseApproval, PurchaseProposal

                PurchaseProposal.objects.filter(
                    contract=self,
                    status__in=["DRAFT", "PROPOSED", "APPROVED"],
                ).exclude(
                    approval__state="CONSUMED"
                ).update(status="SUPERSEDED")

                for old_approval in PurchaseApproval.objects.filter(
                    proposal__contract=self,
                    state__in=["PENDING", "APPROVED"],
                ):
                    old_approval.state = "VOIDED"
                    old_approval.append_audit_event(
                        "VOIDED",
                        f"Contract v{self.version} superseded by Contract v{new_contract.version}.",
                    )
                    old_approval.save(update_fields=["state", "audit_log"])

            return new_contract

    def save(self, *args, **kwargs):
        if not self.public_ref:
            # Never derive public_ref from raw_prompt (no PII in URLs)
            self.public_ref = generate_unique_public_ref(
                "PC",
                self.category,
                PurchaseContract,
                fallback="shopping-request",
            )
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("contract_review", kwargs={"public_ref": self.public_ref})

    def __str__(self):
        return (
            f"Contract {self.id.hex[:8]} v{self.version} "
            f"[{self.category}] ${self.max_budget} ({self.state})"
        )
