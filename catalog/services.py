"""Product search and catalog orchestration service for AI Cart (formerly TrustCart).

Implements CAT-01, CAT-02, CAT-03, CAT-04, CAT-06:
- 24-hour cache for query-to-product-ID identity mappings only.
- Mandatory live detail retrieval via GET /v1/products/{product_id} to ensure fresh prices and availability.
- Strict Decimal price validation and fail-closed filters.
- Seamless zero-spend fallback to labeled fixtures.
"""

import hashlib
import logging
from decimal import Decimal

from catalog.client import Channel3Client, extract_valid_image_url
from catalog.models import ProductEvidence, ProductSearchCache
from contracts.models import PurchaseContract

logger = logging.getLogger(__name__)


class ProductSearchService:
    """Orchestrates product discovery, query-to-ID caching, live detail verification, and fail-closed filtering."""

    def __init__(self, client: Channel3Client | None = None):
        self.client = client or Channel3Client()

    def _compute_query_hash(self, contract: PurchaseContract) -> str:
        key = f"{contract.category.strip().lower()}:{contract.product_description.strip().lower()}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def _apply_fail_closed_validation(self, raw_prod: dict) -> tuple[ProductEvidence | None, str | None]:
        """Validate raw product payload against fail-closed rules.

        Discards unpriced, non-USD, or out-of-stock items.
        Returns (product_evidence, rejection_reason).
        """
        product_id = raw_prod.get("product_id")
        if not product_id:
            return None, "Missing product_id identifier."

        price = raw_prod.get("price")
        if price is None or not isinstance(price, Decimal) or price <= Decimal("0.00"):
            return None, f"Item {product_id} has invalid or missing price: {price}."

        currency = raw_prod.get("currency", "USD")
        if currency != "USD":
            return None, f"Item {product_id} has non-USD currency: {currency}."

        stock_status = raw_prod.get("stock_status", "IN_STOCK")
        if stock_status == "OUT_OF_STOCK":
            return None, f"Item {product_id} is out of stock."

        source_merchant = raw_prod.get("source_merchant", "").strip()
        if not source_merchant:
            return None, f"Item {product_id} missing source merchant provenance."

        product_evidence, _ = ProductEvidence.objects.update_or_create(
            product_id=product_id,
            defaults={
                "brand": raw_prod.get("brand", ""),
                "title": raw_prod.get("title", ""),
                "description": raw_prod.get("description", ""),
                "price": price,
                "currency": currency,
                "source_merchant": source_merchant,
                "merchant_id": raw_prod.get("merchant_id", ""),
                "variant_id": raw_prod.get("variant_id", ""),
                "sku": raw_prod.get("sku", ""),
                "stock_status": stock_status,
                "product_url": raw_prod.get("product_url", ""),
                "image_url": extract_valid_image_url(
                    raw_prod if raw_prod.get("image_url") or raw_prod.get("images") or raw_prod.get("image")
                    else raw_prod.get("raw_evidence", {})
                ),
                "retrieval_timestamp": raw_prod.get("retrieval_timestamp"),
                "offers": raw_prod.get("offers", []),
                "raw_evidence": raw_prod.get("raw_evidence", {}),
                "is_fixture": raw_prod.get("is_fixture", False),
            },
        )
        return product_evidence, None

    def search_for_contract(
        self,
        contract: PurchaseContract,
        force_refresh: bool = False,
    ) -> tuple[list[ProductEvidence], bool, str]:
        """Search products for a confirmed PurchaseContract.

        1. Checks ProductSearchCache for query-to-product-ID identity mapping.
        2. If cached, fetches latest fresh details for each ID via GET /v1/products/{id}.
        3. If cache miss, performs POST /v1/search, caches product IDs, and fetches latest details.
        4. Applies fail-closed filtering.
        """
        query_hash = self._compute_query_hash(contract)
        query = contract.product_description or contract.category
        scenario_hint = contract.raw_prompt

        cached_entry = ProductSearchCache.objects.filter(query_hash=query_hash).first()
        is_fallback = False
        status_message = ""
        candidate_ids: list[str] = []

        if cached_entry and not cached_entry.is_expired() and not force_refresh:
            candidate_ids = cached_entry.product_ids
            status_message = f"Found {len(candidate_ids)} candidate IDs in query cache. Verifying fresh details."
        else:
            search_items, is_fb, msg = self.client.search(
                query=query,
                category=contract.category,
                limit=10,
            )
            is_fallback = is_fb
            status_message = msg
            candidate_ids = [item["product_id"] for item in search_items if item.get("product_id")]

            # Update 24h query-to-ID cache
            if candidate_ids:
                ProductSearchCache.set_mapping(query_hash, candidate_ids, ttl_hours=24)

        # Fresh Details Retrieval: For each product ID, retrieve current facts
        validated_products: list[ProductEvidence] = []
        for pid in candidate_ids:
            prod_detail, detail_fb, _ = self.client.get_product(pid, scenario_hint=scenario_hint)
            if detail_fb:
                is_fallback = True

            if prod_detail:
                evidence, rejection = self._apply_fail_closed_validation(prod_detail)
                if evidence:
                    validated_products.append(evidence)
                else:
                    logger.info("Product candidate %s rejected by fail-closed filter: %s", pid, rejection)

        # Sort candidate products by price ascending
        validated_products.sort(key=lambda p: p.price)

        return validated_products, is_fallback, status_message
