"""Cryptographic cart fingerprinting for AI Cart (formerly TrustCart).

Implements APPR-01 and APPR-03:
- Canonical JSON encoding of exact purchase parameters.
- SHA-256 cryptographic binding over product, variant, payee, prices, and contract version.
- Any modification (even $0.01) produces a different hash, invalidating approvals.
"""

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CartFingerprintParams:
    """Parameters bound immutably into the cart fingerprint."""

    product_id: str
    variant_id: str
    sku: str
    source_merchant: str
    payee_id: str
    quantity: int
    unit_price: Decimal
    base_amount: Decimal
    shipping_amount: Decimal
    tax_amount: Decimal
    fee_amount: Decimal
    total_amount: Decimal
    currency: str
    contract_id: str
    contract_version: int

    def to_canonical_dict(self) -> dict:
        return {
            "base_amount": f"{self.base_amount:.2f}",
            "contract_id": str(self.contract_id),
            "contract_version": int(self.contract_version),
            "currency": str(self.currency).upper(),
            "fee_amount": f"{self.fee_amount:.2f}",
            "payee_id": str(self.payee_id).strip(),
            "product_id": str(self.product_id).strip(),
            "quantity": int(self.quantity),
            "shipping_amount": f"{self.shipping_amount:.2f}",
            "sku": str(self.sku).strip(),
            "source_merchant": str(self.source_merchant).strip(),
            "tax_amount": f"{self.tax_amount:.2f}",
            "total_amount": f"{self.total_amount:.2f}",
            "unit_price": f"{self.unit_price:.2f}",
            "variant_id": str(self.variant_id).strip(),
        }


def compute_cart_fingerprint(params: CartFingerprintParams) -> str:
    """Compute the deterministic SHA-256 hash of canonical cart parameters."""
    canonical_dict = params.to_canonical_dict()
    # Serialize with sorted keys and compact separators to ensure deterministic byte representation
    canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
