"""
Regression tests for Defect 3: Discovery image normalization, validation,
shortlist vs expanded 'Show more candidate products' rendering, and fallback handling.
"""

from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.client import (
    Channel3Client,
    extract_valid_image_url,
    is_valid_http_image_url,
)
from catalog.models import ProductEvidence
from contracts.models import ContractSource, ContractState, PurchaseContract


class DiscoveryImagePipelineTests(TestCase):
    """Verify images work cleanly across Channel3 payloads, shortlist cards, and expanded cards."""

    def setUp(self):
        self.client = Client()
        self.contract = PurchaseContract.objects.create(
            raw_prompt="Wireless ANC headphones under $200",
            category="Electronics > Audio > Headphones",
            product_description="Over-ear wireless headphones",
            max_budget=Decimal("200.00"),
            currency="USD",
            quantity=1,
            state=ContractState.CONFIRMED,
            confirmed_at=timezone.now(),
            source=ContractSource.DEMO_FIXTURE,
        )

    def test_image_url_validation_and_normalization(self):
        """Payload normalizer extracts main image dicts/strings and rejects unsafe/relative URLs."""
        self.assertTrue(is_valid_http_image_url("https://cdn.trychannel3.com/abc.jpg"))
        self.assertFalse(is_valid_http_image_url("/relative/image.jpg"))
        self.assertFalse(is_valid_http_image_url("javascript:alert(1)"))
        self.assertFalse(is_valid_http_image_url(""))

        # Nested images array prefers is_main_image=True
        payload_list = {
            "images": [
                {"url": "https://example.com/side.jpg", "is_main_image": False},
                {"url": "https://example.com/main.jpg", "is_main_image": True},
            ]
        }
        self.assertEqual(extract_valid_image_url(payload_list), "https://example.com/main.jpg")

        # Nested dict under `image`
        payload_dict = {"image": {"cleaned_url": "https://example.com/cleaned.jpg"}}
        self.assertEqual(extract_valid_image_url(payload_dict), "https://example.com/cleaned.jpg")

        # String array under `images`
        self.assertEqual(
            extract_valid_image_url({"images": ["https://example.com/str.jpg"]}),
            "https://example.com/str.jpg",
        )

        # Channel3 client normalizes nested dict image cleanly instead of stringifying dict
        c3 = Channel3Client(api_key="dummy")
        norm = c3._normalize_product_payload(
            {
                "product_id": "P-1",
                "title": "Test Headphones",
                "price": "99.00",
                "image": {"url": "https://example.com/dict_img.jpg"},
            }
        )
        self.assertEqual(norm["image_url"], "https://example.com/dict_img.jpg")

    def test_shortlist_and_expanded_cards_render_images_and_placeholders(self):
        """Defect 3: Both top-3 shortlist and 'Show more (+)' cards render valid images & placeholders safely."""
        products = []
        for idx in range(6):
            # 0..3 have valid images; 4 has invalid relative URL; 5 has missing image URL
            if idx < 4:
                img = f"https://cdn.example.com/prod_{idx}.jpg"
            elif idx == 4:
                img = "/invalid/relative/path.png"
            else:
                img = ""

            p = ProductEvidence.objects.create(
                product_id=f"IMG-TEST-{idx}",
                brand="BrandCo",
                title=f"Over-Ear Headphones Model {idx}",
                description="Wireless over-ear headphones.",
                price=Decimal(f"{60 + idx * 10}.00"),
                currency="USD",
                source_merchant="MerchantShop",
                stock_status="IN_STOCK",
                image_url=img,
                retrieval_timestamp=timezone.now(),
                is_fixture=True,
            )
            products.append(p)

        with patch("catalog.services.ProductSearchService.search_for_contract") as mock_search:
            mock_search.return_value = (products, True, "Using fixture")
            resp = self.client.get(reverse("contract_discovery", args=[self.contract.public_ref]))
            self.assertEqual(resp.status_code, 200)
            html = resp.content.decode("utf-8")

            # Shortlist has items 0, 1, 2; Show more (+3) has items 3, 4, 5
            self.assertIn("Show more candidate products (+3)", html)
            # Expanded valid image #3 MUST appear inside the Show more section with lazy loading
            show_more_section = html.split('id="more-results-details"')[1]
            self.assertIn("https://cdn.example.com/prod_3.jpg", show_more_section)
            self.assertIn('loading="lazy"', show_more_section)
            self.assertIn("tcHandleImgError(this)", show_more_section)

            # Invalid relative URL & missing image MUST NOT render broken <img src="/invalid/...">
            self.assertNotIn('/invalid/relative/path.png', show_more_section)
            self.assertIn("No Product Image", show_more_section)

    def test_eligible_candidates_prioritized_in_shortlist_and_ineligible_disabled(self):
        """Eligible items lead the Top 3 Shortlist; ineligible expanded cards cannot be selected."""
        ineligible_cheap = ProductEvidence.objects.create(
            product_id="INELIG-1",
            brand="CheapCo",
            title="Cheap Over-Budget or Wrong Currency",
            description="Wireless headphones",
            price=Decimal("250.00"),
            currency="USD",
            source_merchant="ShopA",
            stock_status="IN_STOCK",
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )
        extra_inelig = [
            ProductEvidence.objects.create(
                product_id=f"INELIG-X-{i}",
                brand="CostlyCo",
                title=f"Expensive Headphones {i}",
                description="Wireless headphones",
                price=Decimal(f"{260 + i * 10}.00"),
                currency="USD",
                source_merchant="ShopB",
                stock_status="IN_STOCK",
                retrieval_timestamp=timezone.now(),
                is_fixture=True,
            )
            for i in range(4)
        ]
        eligible_item = ProductEvidence.objects.create(
            product_id="ELIG-99",
            brand="AudioCo",
            title="Eligible Over-Ear Wireless Headphones",
            description="Wireless over-ear headphones",
            price=Decimal("120.00"),
            currency="USD",
            source_merchant="AudioShop",
            stock_status="IN_STOCK",
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )

        # Deliberately pass ineligible items BEFORE eligible item from search_for_contract
        all_prods = [ineligible_cheap, *extra_inelig, eligible_item]
        with patch("catalog.services.ProductSearchService.search_for_contract") as mock_search:
            mock_search.return_value = (all_prods, True, "Using fixture")
            resp = self.client.get(reverse("contract_discovery", args=[self.contract.public_ref]))
            self.assertEqual(resp.status_code, 200)

            shortlist = resp.context["shortlist_items"]
            self.assertEqual(shortlist[0]["product"].product_id, "ELIG-99")
            self.assertTrue(shortlist[0]["is_eligible"])

            # Expanded cards are ineligible and must not expose green 'Why It Matches'
            html = resp.content.decode("utf-8")
            show_more_section = html.split('id="more-results-details"')[1]
            self.assertIn("Does Not Match Criteria", show_more_section)
            self.assertNotIn("Why It Matches", show_more_section)
