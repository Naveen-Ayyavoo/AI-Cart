"""Integration tests for Channel3Client, ProductSearchService, and Discovery Views.

Covers:
- CAT-01 (Channel3 client)
- CAT-02 (Provenance tracking)
- CAT-03 (Decimal price conversion, zero float)
- CAT-04 (Query-to-ID caching & fresh live details)
- CAT-05 (Credit ledger budget enforcement)
- CAT-06 (Fail-closed filtering)
"""

import io
import os
import urllib.error
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.client import Channel3Client
from catalog.models import Channel3CreditLedger, ProductEvidence, ProductSearchCache
from catalog.services import ProductSearchService
from contracts.models import PurchaseContract


class Channel3ClientIntegrationTests(TestCase):
    """Test Channel3Client credit enforcement, response parsing, and fallback behavior."""

    def setUp(self):
        self.ledger = Channel3CreditLedger.objects.create(
            month_key="2026-11",
            monthly_allowance=1000,
            monthly_used=0,
            bonus_remaining=1000,
            bonus_used=0,
        )

    def test_client_fallback_when_api_key_missing(self):
        """When CHANNEL3_API_KEY is not set, client seamlessly falls back to labeled demo fixtures."""
        client = Channel3Client(api_key="")
        products, is_fallback, msg = client.search(query="wireless noise cancelling headphones")
        self.assertTrue(is_fallback)
        self.assertIn("Sandbox Demo Fixture", msg)
        self.assertGreaterEqual(len(products), 1)
        # Verify Decimal prices
        for p in products:
            self.assertIsInstance(p["price"], Decimal)
            self.assertEqual(p["currency"], "USD")
            self.assertTrue(p["is_fixture"])

    def test_client_halts_and_falls_back_when_credits_exhausted(self):
        """When credit ledger is exhausted, search refuses outbound calls and falls back to fixtures."""
        # Exhaust ledger
        self.ledger.monthly_used = 1000
        self.ledger.bonus_remaining = 0
        self.ledger.bonus_used = 1000
        self.ledger.save()

        client = Channel3Client(api_key="mock_key_123")
        products, is_fallback, msg = client.search(query="ergonomic office chair")
        self.assertTrue(is_fallback)
        self.assertIn("credit allowance exhausted", msg.lower())
        self.assertGreaterEqual(len(products), 1)

    def test_client_free_detail_call_does_not_consume_credits(self):
        """Product detail retrieval (GET /v1/products/{id}) is free and does not debit ledger."""
        client = Channel3Client(api_key="")
        detail, is_fallback, _msg = client.get_product("ch3_demo_whch720n")
        self.assertTrue(is_fallback)
        self.assertIsNotNone(detail)
        self.assertEqual(detail["brand"], "Sony")
        self.assertIsInstance(detail["price"], Decimal)

        # Confirm ledger was NOT debited
        self.ledger.refresh_from_db()
        self.assertEqual(self.ledger.monthly_used, 0)
        self.assertEqual(self.ledger.bonus_used, 0)

    def test_client_converts_prices_to_decimal(self):
        """Verify price parsing strictly yields Decimal with 2 decimal places and no float drift."""
        client = Channel3Client()
        self.assertEqual(client._parse_decimal_price("148.00"), Decimal("148.00"))
        self.assertEqual(client._parse_decimal_price(36.99), Decimal("36.99"))
        self.assertEqual(client._parse_decimal_price("0.10"), Decimal("0.10"))
        self.assertIsNone(client._parse_decimal_price("invalid_price"))
        self.assertIsNone(client._parse_decimal_price(None))

    @patch("urllib.request.urlopen")
    def test_client_http_429_falls_back_to_fixtures(self, mock_urlopen):
        """Channel3 HTTP 429 error falls back gracefully to labeled demo fixtures."""
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://api.trychannel3.com/v1/search",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=io.BytesIO(b'{"error": "Rate limit exceeded"}'),
        )
        client = Channel3Client(api_key="mock_key_live")
        products, is_fallback, msg = client.search("ergonomic keyboard")
        self.assertTrue(is_fallback)
        self.assertIn("HTTP 429", msg)
        self.assertGreaterEqual(len(products), 1)

    @patch("urllib.request.urlopen")
    def test_client_timeout_falls_back_to_fixtures(self, mock_urlopen):
        """Network timeout while querying Channel3 falls back cleanly to labeled demo fixtures."""
        mock_urlopen.side_effect = urllib.error.URLError(TimeoutError("Connection timed out."))
        client = Channel3Client(api_key="mock_key_live")
        products, is_fallback, msg = client.search("wireless headphones")
        self.assertTrue(is_fallback)
        self.assertIn("connection failed", msg.lower())
        self.assertGreaterEqual(len(products), 1)

    def test_ledger_sequential_consumption_monthly_then_bonus(self):
        """Ledger strictly consumes monthly allowance first, then bonus credits, then halts."""
        # Initial: 1000 monthly, 1000 bonus
        self.assertEqual(self.ledger.monthly_available, 1000)
        self.assertEqual(self.ledger.bonus_remaining, 1000)

        # 1. Consume 600 credits -> from monthly allowance
        success, msg = self.ledger.consume(600)
        self.assertTrue(success)
        self.assertEqual(self.ledger.monthly_used, 600)
        self.assertEqual(self.ledger.monthly_available, 400)
        self.assertEqual(self.ledger.bonus_remaining, 1000)

        # 2. Consume 500 credits -> takes remaining 400 monthly + 100 from bonus
        success, msg = self.ledger.consume(500)
        self.assertTrue(success)
        self.assertEqual(self.ledger.monthly_used, 1000)
        self.assertEqual(self.ledger.monthly_available, 0)
        self.assertEqual(self.ledger.bonus_remaining, 900)
        self.assertEqual(self.ledger.bonus_used, 100)

        # 3. Attempting to consume 901 credits fails closed without altering state
        self.assertFalse(self.ledger.can_consume(901))
        success, msg = self.ledger.consume(901)
        self.assertFalse(success)
        self.assertIn("Credit ceiling reached", msg)
        self.assertEqual(self.ledger.bonus_remaining, 900)

        # 4. Consume remaining 900 credits -> exhausts bonus
        success, msg = self.ledger.consume(900)
        self.assertTrue(success)
        self.assertEqual(self.ledger.bonus_remaining, 0)
        self.assertEqual(self.ledger.total_available, 0)

        # 5. Total exhaustion: can_consume is False, further consume fails
        self.assertFalse(self.ledger.can_consume(1))
        success, msg = self.ledger.consume(1)
        self.assertFalse(success)

    def test_client_safe_fallback_for_unmatched_query(self):
        """Unmatched or obscure query falls back safely to default fixture without crashing."""
        client = Channel3Client(api_key="")
        products, is_fallback, _msg = client.search(query="completely obscure antique item 12345")
        self.assertTrue(is_fallback)
        self.assertGreaterEqual(len(products), 1)
        self.assertEqual(products[0]["currency"], "USD")
        self.assertIsInstance(products[0]["price"], Decimal)


@patch.dict(os.environ, {"CHANNEL3_API_KEY": ""})
class ProductSearchServiceTests(TestCase):
    """Test ProductSearchService query-ID caching, live details, and fail-closed filtering."""

    def setUp(self):
        self.contract = PurchaseContract.objects.create(
            raw_prompt="Looking for a tenkeyless mechanical keyboard under $50 with red linear switches",
            category="Mechanical Keyboards",
            product_description="Tenkeyless mechanical keyboard with red linear switches",
            max_budget=Decimal("50.00"),
            currency="USD",
            quantity=1,
            required_specs={"layout": "Tenkeyless", "switch_type": "Linear Red"},
            preferred_specs={"backlight": "RGB"},
            state="CONFIRMED",
            confirmed_at=timezone.now(),
        )

    def test_search_service_populates_query_cache_and_products(self):
        """First search executes search, caches query-to-ID mapping, and saves product evidence."""
        service = ProductSearchService()
        products, is_fallback, _msg = service.search_for_contract(self.contract)
        self.assertTrue(is_fallback)  # Because no live API key is set
        self.assertGreaterEqual(len(products), 1)

        # Check that ProductSearchCache was populated
        cache_count = ProductSearchCache.objects.count()
        self.assertGreaterEqual(cache_count, 1)

        # Check ProductEvidence in database
        for p in products:
            self.assertIsInstance(p, ProductEvidence)
            self.assertIsInstance(p.price, Decimal)
            self.assertEqual(p.currency, "USD")
            self.assertNotEqual(p.stock_status, "OUT_OF_STOCK")

    def test_search_service_cache_hit_bypasses_search_endpoint(self):
        """Second search uses cached query-to-ID mapping without repeating search endpoint call."""
        service = ProductSearchService()
        # 1. First run creates cache
        products_1, _, _ = service.search_for_contract(self.contract)

        # Mock the client.search method to verify it is NOT called on second run
        service.client.search = MagicMock(side_effect=Exception("Should not be called on cache hit"))

        # 2. Second run should hit cache
        products_2, _, msg = service.search_for_contract(self.contract)
        self.assertIn("cache", msg.lower())
        self.assertEqual(len(products_1), len(products_2))
        service.client.search.assert_not_called()

    def test_search_service_fail_closed_on_out_of_stock(self):
        """Items marked OUT_OF_STOCK must be discarded by fail-closed filter."""
        service = ProductSearchService()
        raw_out_of_stock = {
            "product_id": "test_oos_1",
            "title": "Out of Stock Keyboard",
            "price": Decimal("40.00"),
            "currency": "USD",
            "stock_status": "OUT_OF_STOCK",
            "source_merchant": "Best Buy",
        }
        evidence, rejection = service._apply_fail_closed_validation(raw_out_of_stock)
        self.assertIsNone(evidence)
        self.assertIn("out of stock", rejection.lower())

    def test_search_service_fail_closed_on_non_usd_currency(self):
        """Items with currency other than USD must be discarded by fail-closed filter."""
        service = ProductSearchService()
        raw_eur = {
            "product_id": "test_eur_1",
            "title": "Euro Keyboard",
            "price": Decimal("40.00"),
            "currency": "EUR",
            "stock_status": "IN_STOCK",
            "source_merchant": "Amazon DE",
        }
        evidence, rejection = service._apply_fail_closed_validation(raw_eur)
        self.assertIsNone(evidence)
        self.assertIn("non-usd", rejection.lower())

    def test_search_service_fail_closed_on_missing_price(self):
        """Items with missing or non-positive price must be discarded by fail-closed filter."""
        service = ProductSearchService()
        raw_no_price = {
            "product_id": "test_noprice_1",
            "title": "Unpriced Keyboard",
            "price": None,
            "currency": "USD",
            "stock_status": "IN_STOCK",
            "source_merchant": "Target",
        }
        evidence, rejection = service._apply_fail_closed_validation(raw_no_price)
        self.assertIsNone(evidence)
        self.assertIn("invalid or missing price", rejection.lower())


@patch.dict(os.environ, {"CHANNEL3_API_KEY": ""})
class ProductDiscoveryViewTests(TestCase):
    """Test product discovery UI and contract status validation."""

    def setUp(self):
        self.client = Client()
        self.confirmed_contract = PurchaseContract.objects.create(
            raw_prompt="Ergonomic mesh office chair with lumbar support under $300",
            category="Office Chairs",
            product_description="Ergonomic mesh office chair with adjustable lumbar support",
            max_budget=Decimal("300.00"),
            currency="USD",
            quantity=1,
            state="CONFIRMED",
            confirmed_at=timezone.now(),
        )
        self.draft_contract = PurchaseContract.objects.create(
            raw_prompt="Wireless gaming mouse",
            category="Computer Mice",
            product_description="Wireless gaming mouse",
            max_budget=Decimal("60.00"),
            currency="USD",
            quantity=1,
            state="DRAFT",
        )

    def test_discovery_view_requires_confirmed_contract(self):
        """Attempting to access discovery for a DRAFT contract redirects to review."""
        url = reverse("contract_discovery", kwargs={"public_ref": self.draft_contract.public_ref})
        response = self.client.get(url, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/contracts/{self.draft_contract.public_ref}/review/", response.url)

    def test_discovery_view_renders_provenance_and_fixtures(self):
        """Confirmed contract renders discovery UI with product evidence, provenance, and fallback banner."""
        url = reverse("contract_discovery", kwargs={"public_ref": self.confirmed_contract.public_ref})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "catalog/product_list.html")

        content = response.content.decode("utf-8")
        self.assertIn("Matching Products", content)
        self.assertIn("Office Chairs", content)
        self.assertIn("$300.00 USD", content)
        # Must show customer demonstration disclosure
        self.assertIn("Demonstration Sample Products", content)
        # Must show merchant provenance
        self.assertIn("Source Merchant", content)
        # Must NOT leak internal credit ledger, quotas, or zero-spend policies to customer UI
        self.assertNotIn("Channel3 Credits", content)
        self.assertNotIn("Zero-Spend", content)
