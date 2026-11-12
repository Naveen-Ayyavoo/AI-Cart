"""Models for AI Cart (formerly TrustCart) deterministic policy evaluation and audit reports.

Implements POL-01, POL-02, POL-03, POL-04.
"""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone

from catalog.models import ProductEvidence
from contracts.models import PurchaseContract


class PolicyEvaluationReport(models.Model):
    """Persistent audit report of deterministic policy evaluation for a product against a PurchaseContract."""

    OUTCOME_CHOICES = [
        ("ELIGIBLE", "Eligible"),
        ("INELIGIBLE", "Ineligible"),
        ("UNKNOWN", "Unknown"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(
        PurchaseContract,
        on_delete=models.CASCADE,
        related_name="policy_reports",
    )
    product = models.ForeignKey(
        ProductEvidence,
        on_delete=models.CASCADE,
        related_name="policy_reports",
    )
    outcome = models.CharField(max_length=32, choices=OUTCOME_CHOICES, db_index=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    total_item_price = models.DecimalField(max_digits=10, decimal_places=2)
    budget_ceiling = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    preference_score = models.PositiveIntegerField(default=0)
    rule_results = models.JSONField(default=list, blank=True, encoder=DjangoJSONEncoder)
    matched_preferences = models.JSONField(default=list, blank=True, encoder=DjangoJSONEncoder)
    missed_preferences = models.JSONField(default=list, blank=True, encoder=DjangoJSONEncoder)
    summary = models.TextField(blank=True)
    shipping_tax_disclosure = models.TextField(blank=True)
    evaluated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-preference_score", "total_item_price"]
        verbose_name = "Policy Evaluation Report"
        verbose_name_plural = "Policy Evaluation Reports"
        unique_together = ("contract", "product")

    def __str__(self) -> str:
        return f"[{self.outcome}] {self.product.title} for Contract v{self.contract.version} (${self.total_item_price} / ${self.budget_ceiling})"

    def clean(self) -> None:
        if self.total_item_price is None or self.total_item_price <= Decimal("0.00"):
            raise ValidationError({"total_item_price": "Total item price must be positive Decimal."})
        if self.currency != "USD":
            raise ValidationError({"currency": "Currency must be USD."})
