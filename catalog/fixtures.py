"""Deterministic local product evidence fixtures for AI Cart (formerly TrustCart) zero-spend testing and offline demonstration.

Preserves full external provenance and exact Decimal monetary precision.
Prominently labeled with:
"Sandbox Demo Fixture — Zero-Spend Fallback"
"""

from decimal import Decimal

from django.utils import timezone

from catalog.models import ProductEvidence

FALLBACK_DISCLOSURE = "Sandbox Demo Fixture — Zero-Spend Fallback"

DEMO_PRODUCTS = {
    "headphones": [
        {
            "product_id": "ch3_demo_whch720n",
            "brand": "Sony",
            "title": "Sony WH-CH720N Wireless Noise Canceling Headphones",
            "description": "Lightweight wireless noise canceling headphones with Integrated Processor V1, up to 35 hours battery life, and multipoint Bluetooth connection.",
            "price": Decimal("148.00"),
            "currency": "USD",
            "source_merchant": "Amazon",
            "merchant_id": "amzn_us",
            "variant_id": "WHCH720N/B",
            "sku": "B0BS1PR858",
            "stock_status": "IN_STOCK",
            "product_url": "https://www.amazon.com/dp/B0BS1PR858",
            "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&q=80",
            "offers": [
                {
                    "merchant": "Amazon",
                    "price": "148.00",
                    "currency": "USD",
                    "availability": "in_stock",
                    "condition": "new",
                }
            ],
            "raw_evidence": {
                "source": "Channel3 Simulated Fixture",
                "disclosure": FALLBACK_DISCLOSURE,
                "category": "Electronics > Audio > Headphones",
                "features": {
                    "noise_canceling": "Active",
                    "battery_life": "35 hours",
                    "connectivity": "Bluetooth 5.2",
                    "weight": "192g",
                    "color": "Black",
                },
            },
        },
        {
            "product_id": "ch3_demo_anker_q30",
            "brand": "Anker Soundcore",
            "title": "Anker Soundcore Life Q30 Hybrid Active Noise Cancelling Headphones",
            "description": "Hi-Res Audio with custom EQ, 40-hour battery life in ANC mode, ultra-soft protein leather earcups.",
            "price": Decimal("79.99"),
            "currency": "USD",
            "source_merchant": "Amazon",
            "merchant_id": "amzn_us",
            "variant_id": "A3028011",
            "sku": "B08HMWZBXC",
            "stock_status": "IN_STOCK",
            "product_url": "https://www.amazon.com/dp/B08HMWZBXC",
            "image_url": "https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=500&q=80",
            "offers": [
                {
                    "merchant": "Amazon",
                    "price": "79.99",
                    "currency": "USD",
                    "availability": "in_stock",
                    "condition": "new",
                }
            ],
            "raw_evidence": {
                "source": "Channel3 Simulated Fixture",
                "disclosure": FALLBACK_DISCLOSURE,
                "category": "Electronics > Audio > Headphones",
                "features": {
                    "noise_canceling": "Hybrid Active",
                    "battery_life": "40 hours",
                    "connectivity": "Bluetooth 5.0",
                    "color": "Black",
                },
            },
        },
    ],
    "keyboard": [
        {
            "product_id": "ch3_demo_keychron_c3_pro",
            "brand": "Keychron",
            "title": "Keychron C3 Pro TKL Mechanical Gaming Keyboard",
            "description": "Tenkeyless QMK/VIA programmable mechanical keyboard with red linear switches, gasket mount feel, and sound absorbing foam.",
            "price": Decimal("36.99"),
            "currency": "USD",
            "source_merchant": "Amazon",
            "merchant_id": "amzn_us",
            "variant_id": "C3P-A1",
            "sku": "B0CBWJ945C",
            "stock_status": "IN_STOCK",
            "product_url": "https://www.amazon.com/dp/B0CBWJ945C",
            "image_url": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=500&q=80",
            "offers": [
                {
                    "merchant": "Amazon",
                    "price": "36.99",
                    "currency": "USD",
                    "availability": "in_stock",
                    "condition": "new",
                }
            ],
            "raw_evidence": {
                "source": "Channel3 Simulated Fixture",
                "disclosure": FALLBACK_DISCLOSURE,
                "category": "Electronics > Computer Accessories > Keyboards",
                "features": {
                    "layout": "Tenkeyless (87 keys)",
                    "switch_type": "Red Mechanical (Linear)",
                    "programmable": "QMK/VIA",
                    "backlight": "Red LED",
                    "connection": "Detachable USB-C",
                },
            },
        },
        {
            "product_id": "ch3_demo_keychron_k2",
            "brand": "Keychron",
            "title": "Keychron K2 Wireless Bluetooth/USB Mechanical Keyboard",
            "description": "75% compact wireless mechanical keyboard for Mac and Windows with Gateron G Pro Brown switches.",
            "price": Decimal("79.99"),
            "currency": "USD",
            "source_merchant": "Amazon",
            "merchant_id": "amzn_us",
            "variant_id": "K2-V2-BROWN",
            "sku": "B07YB32H52",
            "stock_status": "IN_STOCK",
            "product_url": "https://www.amazon.com/dp/B07YB32H52",
            "image_url": "https://images.unsplash.com/photo-1618384887929-16ec33fab9ef?w=500&q=80",
            "offers": [
                {
                    "merchant": "Amazon",
                    "price": "79.99",
                    "currency": "USD",
                    "availability": "in_stock",
                    "condition": "new",
                }
            ],
            "raw_evidence": {
                "source": "Channel3 Simulated Fixture",
                "disclosure": FALLBACK_DISCLOSURE,
                "category": "Electronics > Computer Accessories > Keyboards",
                "features": {
                    "layout": "75% (84 keys)",
                    "switch_type": "Gateron Brown (Tactile)",
                    "connection": "Bluetooth / USB-C",
                    "battery": "4000mAh",
                },
            },
        },
    ],
    "chair": [
        {
            "product_id": "ch3_demo_branch_ergo",
            "brand": "Branch",
            "title": "Branch Ergonomic Chair",
            "description": "Daily-use ergonomic task chair with 8 points of adjustment, breathable double-woven nylon mesh, and active lumbar support.",
            "price": Decimal("249.00"),
            "currency": "USD",
            "source_merchant": "Branch Furniture",
            "merchant_id": "branch_direct",
            "variant_id": "BE-CHR-01",
            "sku": "BRN-ERG-GRY",
            "stock_status": "IN_STOCK",
            "product_url": "https://www.branchfurniture.com/products/ergonomic-chair",
            "image_url": "https://images.unsplash.com/photo-1580481077195-c9f13e73111f?w=500&q=80",
            "offers": [
                {
                    "merchant": "Branch Furniture",
                    "price": "249.00",
                    "currency": "USD",
                    "availability": "in_stock",
                    "condition": "new",
                }
            ],
            "raw_evidence": {
                "source": "Channel3 Simulated Fixture",
                "disclosure": FALLBACK_DISCLOSURE,
                "category": "Furniture > Office Furniture > Office Chairs",
                "features": {
                    "material": "Double-layered Nylon Mesh",
                    "adjustments": "8 points of adjustment",
                    "lumbar": "Active ergonomic lumbar support",
                    "weight_capacity": "300 lbs",
                    "warranty": "7 years",
                },
            },
        }
    ],
}


def get_product_fixtures(scenario_key: str = "") -> list[ProductEvidence]:
    """Return populated, clean ProductEvidence model instances for a scenario.

    If scenario_key is empty or unknown, returns all demo fixtures across scenarios.
    """
    now = timezone.now()
    results = []

    target_keys = [scenario_key] if scenario_key in DEMO_PRODUCTS else list(DEMO_PRODUCTS.keys())

    for key in target_keys:
        for item in DEMO_PRODUCTS[key]:
            product = ProductEvidence(
                product_id=item["product_id"],
                brand=item.get("brand", ""),
                title=item["title"],
                description=item["description"],
                price=item["price"],
                currency=item["currency"],
                source_merchant=item["source_merchant"],
                merchant_id=item.get("merchant_id", ""),
                variant_id=item.get("variant_id", ""),
                sku=item.get("sku", ""),
                stock_status=item.get("stock_status", "IN_STOCK"),
                product_url=item.get("product_url", ""),
                image_url=item.get("image_url", ""),
                retrieval_timestamp=now,
                offers=item.get("offers", []),
                raw_evidence=item.get("raw_evidence", {}),
                is_fixture=True,
            )
            results.append(product)

    return results
