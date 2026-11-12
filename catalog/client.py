"""Channel3 API client for AI Cart (formerly TrustCart).

Interacts with https://api.trychannel3.com (US / USD):
- POST /v1/search (billable: debits 1 credit from Channel3CreditLedger)
- GET /v1/products/{product_id} (free: does not debit credit ledger)
- POST /v1/lookup (merchant product URL lookup)

Enforces:
- Server-side x-api-key authentication (never exposed to client).
- Credit budget enforcement before billable calls; halts on exhaustion.
- Exact Decimal monetary parsing (zero float).
- Seamless fallback to labeled local fixtures: "Sandbox Demo Fixture — Zero-Spend Fallback".
"""

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from catalog.fixtures import DEMO_PRODUCTS, FALLBACK_DISCLOSURE, get_product_fixtures
from catalog.models import Channel3CreditLedger

logger = logging.getLogger(__name__)

CHANNEL3_DEFAULT_BASE_URL = "https://api.trychannel3.com"


def is_valid_http_image_url(raw_url: object) -> bool:
    """Validate that an external image URL uses http/https with a valid host."""
    if not isinstance(raw_url, str):
        return False
    candidate = raw_url.strip()
    if not candidate or any(ch.isspace() for ch in candidate):
        return False
    try:
        parsed = urllib.parse.urlparse(candidate)
        return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)
    except ValueError:
        return False


def extract_valid_image_url(payload: object) -> str:
    """Normalize and validate an image URL from heterogeneous catalog payloads.

    Supports:
    - direct `image_url` / `image` string
    - nested dict `image`: {'url': ...} or {'cleaned_url': ...}
    - `images`: list of dicts (preferring `is_main_image=True`) or list of strings
    - `image_urls`: list of strings
    Returns a verified http/https URL string, or '' if missing/invalid.
    """
    if not isinstance(payload, dict):
        return ""

    candidates: list[object] = []

    for direct_key in ("image_url", "image", "thumbnail_url", "thumbnail"):
        val = payload.get(direct_key)
        if isinstance(val, dict):
            candidates.extend([val.get("url"), val.get("cleaned_url"), val.get("src")])
        elif val:
            candidates.append(val)

    raw_images = payload.get("images")
    if isinstance(raw_images, list):
        # Prefer explicit main images first, then remaining items in order
        prioritized = sorted(
            raw_images,
            key=lambda x: 0 if isinstance(x, dict) and x.get("is_main_image") else 1,
        )
        for entry in prioritized:
            if isinstance(entry, dict):
                candidates.extend([entry.get("url"), entry.get("cleaned_url"), entry.get("src")])
            elif isinstance(entry, str):
                candidates.append(entry)

    raw_image_urls = payload.get("image_urls")
    if isinstance(raw_image_urls, list):
        candidates.extend(raw_image_urls)

    for cand in candidates:
        if is_valid_http_image_url(cand):
            return str(cand).strip()
    return ""


class Channel3Client:
    """Client for interacting with Channel3 external product catalog API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 10,
    ):
        self.api_key = (
            api_key.strip() if api_key is not None else os.environ.get("CHANNEL3_API_KEY", "").strip()
        )
        self.base_url = (base_url or os.environ.get("CHANNEL3_BASE_URL", CHANNEL3_DEFAULT_BASE_URL)).rstrip("/")
        self.timeout = timeout

    @staticmethod
    def _detect_scenario_key(query: str) -> str:
        q = query.lower()
        if any(w in q for w in ["headphone", "audio", "sound", "earphone", "sony", "anker"]):
            return "headphones"
        if any(w in q for w in ["keyboard", "keychron", "mechanical", "switch", "tkl"]):
            return "keyboard"
        if any(w in q for w in ["chair", "ergonomic", "seat", "desk chair", "branch"]):
            return "chair"
        return "headphones"

    def _get_fallback_products(self, query: str = "", scenario_key: str = "") -> list[dict]:
        key = scenario_key or self._detect_scenario_key(query)
        fixtures = get_product_fixtures(key)
        results = []
        for f in fixtures:
            results.append(
                {
                    "product_id": f.product_id,
                    "brand": f.brand,
                    "title": f.title,
                    "description": f.description,
                    "price": f.price,
                    "currency": f.currency,
                    "source_merchant": f.source_merchant,
                    "merchant_id": f.merchant_id,
                    "variant_id": f.variant_id,
                    "sku": f.sku,
                    "stock_status": f.stock_status,
                    "product_url": f.product_url,
                    "image_url": f.image_url,
                    "retrieval_timestamp": f.retrieval_timestamp,
                    "offers": f.offers,
                    "raw_evidence": f.raw_evidence,
                    "is_fixture": True,
                }
            )
        return results

    def _parse_decimal_price(self, raw_price: object) -> Decimal | None:
        """Parse raw price string or number into Decimal with 2 decimal places. Never uses float math."""
        if raw_price is None:
            return None
        try:
            return Decimal(str(raw_price)).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            return None

    def _normalize_product_payload(self, item: dict, is_fixture: bool = False) -> dict:
        """Convert external or raw payload into normalized product dictionary."""
        price = self._parse_decimal_price(item.get("price"))
        raw_offers = item.get("offers", [])
        offers = []
        source_merchant = str(item.get("source_merchant") or item.get("merchant") or "")
        
        if isinstance(raw_offers, list):
            for off in raw_offers:
                off_price_raw = off.get("price")
                if isinstance(off_price_raw, dict):
                    off_currency = str(off_price_raw.get("currency", "USD"))
                    off_price_raw = off_price_raw.get("price")
                else:
                    off_currency = str(off.get("currency", "USD"))

                off_price = self._parse_decimal_price(off_price_raw)
                off_merchant = str(off.get("merchant") or off.get("domain") or source_merchant or "Channel3 Partner")
                if not source_merchant and off_merchant:
                    source_merchant = off_merchant
                if price is None and off_price is not None:
                    price = off_price

                offers.append(
                    {
                        "merchant": off_merchant,
                        "price": str(off_price) if off_price is not None else "",
                        "currency": off_currency,
                        "availability": str(off.get("availability", "in_stock")),
                        "condition": str(off.get("condition", "new")),
                    }
                )

        if not source_merchant:
            source_merchant = "Channel3 Partner"

        # Brand extraction (handles string or list of dicts from Channel3 API)
        brand = str(item.get("brand", ""))
        if not brand and item.get("brands") and isinstance(item.get("brands"), list):
            first_b = item["brands"][0]
            if isinstance(first_b, dict):
                brand = str(first_b.get("name", ""))
            elif isinstance(first_b, str):
                brand = first_b

        # URL extraction
        product_url = str(item.get("product_url") or item.get("url") or "")
        if not product_url and raw_offers and isinstance(raw_offers, list) and isinstance(raw_offers[0], dict):
            product_url = str(raw_offers[0].get("url", ""))

        # Image extraction (supports string, nested image dict, images list of dicts/strings, URL validation)
        image_url = extract_valid_image_url(item)

        return {
            "product_id": str(item.get("product_id") or item.get("id") or ""),
            "brand": brand,
            "title": str(item.get("title") or item.get("name") or ""),
            "description": str(item.get("description", "")),
            "price": price,
            "currency": str(item.get("currency", "USD")).upper(),
            "source_merchant": source_merchant,
            "merchant_id": str(item.get("merchant_id", "")),
            "variant_id": str(item.get("variant_id", "")),
            "sku": str(item.get("sku", "")),
            "stock_status": str(item.get("stock_status", "IN_STOCK")),
            "product_url": product_url,
            "image_url": image_url,
            "retrieval_timestamp": timezone.now(),
            "offers": offers,
            "raw_evidence": item,
            "is_fixture": is_fixture,
        }

    def search(
        self,
        query: str,
        category: str = "",
        limit: int = 10,
    ) -> tuple[list[dict], bool, str]:
        """Search products via POST /v1/search.

        Billable operation: requires and debits 1 credit from Channel3CreditLedger upon success.
        Returns: (product_dicts: list[dict], is_fallback: bool, status_message: str)
        """
        # If API key not set, return local fallback fixtures
        if not self.api_key:
            fallback = self._get_fallback_products(query)
            return (
                fallback,
                True,
                f"Channel3 API key not configured. Using local fixture ({FALLBACK_DISCLOSURE}).",
            )

        # Check credit budget
        ledger = Channel3CreditLedger.get_current_ledger()
        if not ledger.can_consume(1):
            logger.warning("Channel3 credit allowance exhausted. Halting search calls.")
            fallback = self._get_fallback_products(query)
            return (
                fallback,
                True,
                f"Channel3 credit allowance exhausted. Halting billable calls. Using fixture ({FALLBACK_DISCLOSURE}).",
            )

        url = f"{self.base_url}/v1/search"
        payload = {
            "query": query,
            "limit": limit,
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "User-Agent": "AI-Cart/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                # Debit 1 credit on successful API search
                ledger.consume(1)

                raw_items = resp_data.get("products", resp_data if isinstance(resp_data, list) else [])
                products = [self._normalize_product_payload(it, is_fixture=False) for it in raw_items]
                return products, False, "Live Channel3 product search successful."

        except urllib.error.HTTPError as e:
            logger.error("Channel3 HTTP error %s: %s", e.code, e.reason)
            fallback = self._get_fallback_products(query)
            return (
                fallback,
                True,
                f"Channel3 API error (HTTP {e.code}). Using local fixture ({FALLBACK_DISCLOSURE}).",
            )
        except Exception as e:  # noqa: BLE001
            logger.error("Channel3 request failed: %s", str(e))
            fallback = self._get_fallback_products(query)
            return (
                fallback,
                True,
                f"Channel3 connection failed. Using local fixture ({FALLBACK_DISCLOSURE}).",
            )

    def get_product(self, product_id: str, scenario_hint: str = "") -> tuple[dict | None, bool, str]:
        """Retrieve live product details via GET /v1/products/{product_id}.

        Free operation: does NOT debit credits from Channel3CreditLedger.
        Returns: (product_dict: dict | None, is_fallback: bool, status_message: str)
        """
        # If product_id belongs to demo fixtures or API key not set
        if not self.api_key or product_id.startswith("ch3_demo_"):
            for items in DEMO_PRODUCTS.values():
                for item in items:
                    if item["product_id"] == product_id:
                        normalized = self._normalize_product_payload(item, is_fixture=True)
                        normalized["price"] = item["price"]
                        return normalized, True, f"Loaded from demo fixture ({FALLBACK_DISCLOSURE})."
            # If scenario hint or search query provided, return first fixture
            fixtures = self._get_fallback_products(scenario_hint)
            if fixtures:
                return fixtures[0], True, f"Loaded from demo fixture ({FALLBACK_DISCLOSURE})."
            return None, True, "Fixture not found."

        url = f"{self.base_url}/v1/products/{urllib.parse.quote(product_id)}"
        req = urllib.request.Request(
            url,
            headers={
                "x-api-key": self.api_key,
                "User-Agent": "AI-Cart/1.0",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                item = resp_data.get("product", resp_data)
                normalized = self._normalize_product_payload(item, is_fixture=False)
                return normalized, False, "Live Channel3 product details retrieved."
        except Exception as e:  # noqa: BLE001
            logger.error("Channel3 get_product failed for %s: %s", product_id, str(e))
            # Fallback
            fixtures = self._get_fallback_products(scenario_hint)
            return (
                fixtures[0] if fixtures else None,
                True,
                f"Channel3 details error. Using local fixture ({FALLBACK_DISCLOSURE}).",
            )

    def lookup_url(self, url: str, scenario_hint: str = "") -> tuple[dict | None, bool, str]:
        """Look up product details for a direct merchant URL via POST /v1/lookup."""
        if not self.api_key:
            fixtures = self._get_fallback_products(scenario_hint)
            return fixtures[0] if fixtures else None, True, f"Using local fixture ({FALLBACK_DISCLOSURE})."

        ledger = Channel3CreditLedger.get_current_ledger()
        if not ledger.can_consume(1):
            fixtures = self._get_fallback_products(scenario_hint)
            return (
                fixtures[0] if fixtures else None,
                True,
                f"Channel3 credits exhausted. Using fixture ({FALLBACK_DISCLOSURE}).",
            )

        api_url = f"{self.base_url}/v1/lookup"
        data_bytes = json.dumps({"url": url}).encode("utf-8")
        req = urllib.request.Request(
            api_url,
            data=data_bytes,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "User-Agent": "AI-Cart/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                ledger.consume(1)
                item = resp_data.get("product", resp_data)
                return self._normalize_product_payload(item, is_fixture=False), False, "Live URL lookup successful."
        except Exception as e:  # noqa: BLE001
            logger.error("Channel3 lookup_url failed: %s", str(e))
            fixtures = self._get_fallback_products(scenario_hint)
            return (
                fixtures[0] if fixtures else None,
                True,
                f"Lookup failed. Using local fixture ({FALLBACK_DISCLOSURE}).",
            )
