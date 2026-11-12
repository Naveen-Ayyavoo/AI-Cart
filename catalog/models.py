"""Catalog models for AI Cart (formerly TrustCart): Credit Ledger, Product Evidence, and Query-ID Cache.

Implements CAT-02, CAT-03, CAT-04, CAT-05, and enforces Zero-Spend / Fail-Closed invariants.
"""

import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone


def _current_month_key() -> str:
    now = timezone.now()
    return now.strftime("%Y-%m")


class Channel3CreditLedger(models.Model):
    """Tracks Channel3 API credits with strict separation of monthly allowance vs. bonus credits.

    Invariant:
    - Monthly recurring allowance: 1,000 credits/mo.
    - One-time bonus credits: 1,000 credits remaining.
    - Monthly credits are consumed first; bonus credits are consumed only after monthly is exhausted.
    - When both are exhausted, refuses outbound billable requests and halts calls.
    - Non-billable operations (such as GET /v1/products/{id}) do not consume credits.
    """

    month_key = models.CharField(max_length=7, default=_current_month_key, unique=True, db_index=True)
    monthly_allowance = models.PositiveIntegerField(default=1000)
    monthly_used = models.PositiveIntegerField(default=0)
    bonus_remaining = models.PositiveIntegerField(default=1000)
    bonus_used = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Channel3 Credit Ledger"
        verbose_name_plural = "Channel3 Credit Ledgers"

    def __str__(self) -> str:
        return f"Credit Ledger [{self.month_key}]: {self.monthly_available} monthly, {self.bonus_remaining} bonus"

    @classmethod
    def get_current_ledger(cls) -> "Channel3CreditLedger":
        """Get or create the singleton ledger record for the current calendar month."""
        month_key = _current_month_key()
        ledger, _ = cls.objects.get_or_create(
            month_key=month_key,
            defaults={
                "monthly_allowance": 1000,
                "monthly_used": 0,
                "bonus_remaining": 1000,
                "bonus_used": 0,
            },
        )
        return ledger

    @property
    def monthly_available(self) -> int:
        return max(0, self.monthly_allowance - self.monthly_used)

    @property
    def total_available(self) -> int:
        return self.monthly_available + self.bonus_remaining

    def can_consume(self, credits: int = 1) -> bool:
        """Check whether sufficient credits exist without mutating state."""
        if credits <= 0:
            return True
        return self.total_available >= credits

    def consume(self, credits: int = 1) -> tuple[bool, str]:
        """Consume credits enforcing monthly-first order.

        Returns (success: bool, message: str).
        """
        if credits <= 0:
            return True, "No credits consumed"

        if not self.can_consume(credits):
            return False, "Credit ceiling reached: Channel3 allowance and bonus exhausted. Halting billable calls."

        monthly_avail = self.monthly_available
        if monthly_avail >= credits:
            self.monthly_used += credits
        else:
            from_monthly = monthly_avail
            from_bonus = credits - from_monthly
            self.monthly_used += from_monthly
            self.bonus_remaining -= from_bonus
            self.bonus_used += from_bonus

        self.save()
        return True, f"Consumed {credits} credit(s) (remaining monthly: {self.monthly_available}, bonus: {self.bonus_remaining})"

    def get_balance(self) -> dict:
        """Return a structured breakdown of credit balances."""
        return {
            "month_key": self.month_key,
            "monthly_allowance": self.monthly_allowance,
            "monthly_used": self.monthly_used,
            "monthly_available": self.monthly_available,
            "bonus_remaining": self.bonus_remaining,
            "bonus_used": self.bonus_used,
            "total_available": self.total_available,
        }


class ProductEvidence(models.Model):
    """External product evidence retrieved from Channel3 or zero-spend fallback fixtures.

    Preserves full provenance: source merchant, retrieval timestamp, currency (USD),
    variant identity, brand, offers, and raw evidence.
    Monetary precision: price is strictly Decimal, zero float.
    """

    STOCK_CHOICES = [
        ("IN_STOCK", "In Stock"),
        ("OUT_OF_STOCK", "Out of Stock"),
        ("UNKNOWN", "Unknown"),
    ]

    product_id = models.CharField(max_length=255, unique=True, db_index=True)
    brand = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    source_merchant = models.CharField(max_length=255)
    merchant_id = models.CharField(max_length=255, blank=True)
    variant_id = models.CharField(max_length=255, blank=True)
    sku = models.CharField(max_length=255, blank=True)
    stock_status = models.CharField(max_length=32, choices=STOCK_CHOICES, default="IN_STOCK")
    product_url = models.URLField(max_length=1000, blank=True)
    image_url = models.URLField(max_length=1000, blank=True)
    retrieval_timestamp = models.DateTimeField(default=timezone.now)
    offers = models.JSONField(default=list, blank=True, encoder=DjangoJSONEncoder)
    raw_evidence = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)
    is_fixture = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price"]
        verbose_name = "Product Evidence"
        verbose_name_plural = "Product Evidence"

    def __str__(self) -> str:
        return f"{self.title} (${self.price} {self.currency}) [{self.source_merchant}]"

    def clean(self) -> None:
        """Validate critical product facts. Fail-closed on missing or invalid data."""
        if self.price is None or self.price <= Decimal("0.00"):
            raise ValidationError({"price": "Product price must be a positive Decimal value greater than zero."})

        if self.currency != "USD":
            raise ValidationError({"currency": f"Currency must be USD, got '{self.currency}'."})

        if not self.source_merchant or not self.source_merchant.strip():
            raise ValidationError({"source_merchant": "Source merchant is required for provenance tracking."})

        if not self.product_id or not self.product_id.strip():
            raise ValidationError({"product_id": "Product ID is required for identity binding."})


class ProductSearchCache(models.Model):
    """Caches search query-to-product-ID identity mappings only.

    Invariant:
    - 24-hour cache for query -> [product_id_1, product_id_2, ...] mappings.
    - NEVER caches prices, availability, offers, or short-lived buy URLs.
    - Live details must be retrieved fresh via GET /v1/products/{id}.
    """

    query_hash = models.CharField(max_length=64, primary_key=True)
    product_ids = models.JSONField(default=list)
    cached_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = "Product Search Cache"
        verbose_name_plural = "Product Search Caches"

    def __str__(self) -> str:
        return f"Cache {self.query_hash[:12]} ({len(self.product_ids)} items, expires {self.expires_at})"

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @classmethod
    def set_mapping(cls, query_hash: str, product_ids: list[str], ttl_hours: int = 24) -> "ProductSearchCache":
        expires = timezone.now() + datetime.timedelta(hours=ttl_hours)
        cache_entry, _ = cls.objects.update_or_create(
            query_hash=query_hash,
            defaults={
                "product_ids": product_ids,
                "expires_at": expires,
            },
        )
        return cache_entry
