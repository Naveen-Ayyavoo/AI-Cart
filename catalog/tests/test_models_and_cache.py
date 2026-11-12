"""Unit tests for Catalog models, Credit Ledger, Cache, and Fixtures.

Covers: CAT-02, CAT-03, CAT-04, CAT-05, and Zero-Spend / Fail-Closed invariants.
"""

import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from catalog.fixtures import FALLBACK_DISCLOSURE, get_product_fixtures
from catalog.models import Channel3CreditLedger, ProductEvidence, ProductSearchCache


class Channel3CreditLedgerTests(TestCase):
    """Test credit accounting: 1,000 monthly allowance and 1,000 bonus credits."""

    def setUp(self):
        self.ledger = Channel3CreditLedger.objects.create(
            month_key="2026-11",
            monthly_allowance=1000,
            monthly_used=0,
            bonus_remaining=1000,
            bonus_used=0,
        )

    def test_credit_ledger_monthly_and_bonus_consumption(self):
        """Monthly credits must be consumed before bonus credits; both exhaustion halts calls."""
        # 1. Consume 600 from monthly
        success, msg = self.ledger.consume(600)
        self.assertTrue(success)
        self.ledger.refresh_from_db()
        self.assertEqual(self.ledger.monthly_used, 600)
        self.assertEqual(self.ledger.monthly_available, 400)
        self.assertEqual(self.ledger.bonus_remaining, 1000)
        self.assertEqual(self.ledger.bonus_used, 0)
        self.assertEqual(self.ledger.total_available, 1400)

        # 2. Consume remaining 400 monthly + 100 bonus (total 500)
        success, msg = self.ledger.consume(500)
        self.assertTrue(success)
        self.ledger.refresh_from_db()
        self.assertEqual(self.ledger.monthly_used, 1000)
        self.assertEqual(self.ledger.monthly_available, 0)
        self.assertEqual(self.ledger.bonus_remaining, 900)
        self.assertEqual(self.ledger.bonus_used, 100)
        self.assertEqual(self.ledger.total_available, 900)

        # 3. Exhaust all remaining 900 bonus credits
        success, msg = self.ledger.consume(900)
        self.assertTrue(success)
        self.ledger.refresh_from_db()
        self.assertEqual(self.ledger.bonus_remaining, 0)
        self.assertEqual(self.ledger.bonus_used, 1000)
        self.assertEqual(self.ledger.total_available, 0)

        # 4. Attempt to consume when exhausted: must refuse and return False
        success, msg = self.ledger.consume(1)
        self.assertFalse(success)
        self.assertIn("Credit ceiling reached", msg)
        self.assertFalse(self.ledger.can_consume(1))

    def test_credit_ledger_separate_accounting(self):
        """Monthly and bonus accounts are tracked independently and never conflated."""
        balance = self.ledger.get_balance()
        self.assertEqual(balance["monthly_allowance"], 1000)
        self.assertEqual(balance["monthly_used"], 0)
        self.assertEqual(balance["monthly_available"], 1000)
        self.assertEqual(balance["bonus_remaining"], 1000)
        self.assertEqual(balance["bonus_used"], 0)
        self.assertEqual(balance["total_available"], 2000)

    def test_credit_ledger_free_operations_do_not_debit(self):
        """Free operations (e.g. credits=0) do not debit the ledger."""
        success, _ = self.ledger.consume(0)
        self.assertTrue(success)
        self.ledger.refresh_from_db()
        self.assertEqual(self.ledger.monthly_used, 0)
        self.assertEqual(self.ledger.bonus_used, 0)


class ProductEvidenceModelTests(TestCase):
    """Test product evidence validation, provenance tracking, and Decimal precision."""

    def test_product_evidence_creation_and_clean(self):
        """Valid product evidence with exact Decimal and USD passes clean."""
        product = ProductEvidence(
            product_id="test_sku_101",
            brand="Sony",
            title="Sony WH-1000XM5",
            description="Premium wireless noise cancelling headphones.",
            price=Decimal("348.00"),
            currency="USD",
            source_merchant="Amazon",
            merchant_id="amzn_us",
            variant_id="XM5-BLK",
            sku="B09XS7JWHH",
            stock_status="IN_STOCK",
            product_url="https://www.amazon.com/dp/B09XS7JWHH",
            retrieval_timestamp=timezone.now(),
            offers=[{"merchant": "Amazon", "price": "348.00", "currency": "USD"}],
        )
        product.full_clean()
        product.save()
        self.assertIsInstance(product.price, Decimal)
        self.assertEqual(product.price, Decimal("348.00"))

    def test_product_evidence_rejects_negative_or_zero_price(self):
        """Zero or negative price must fail closed with ValidationError."""
        product_zero = ProductEvidence(
            product_id="test_zero",
            title="Zero Price Item",
            price=Decimal("0.00"),
            currency="USD",
            source_merchant="Best Buy",
        )
        with self.assertRaises(ValidationError) as ctx:
            product_zero.full_clean()
        self.assertIn("price", ctx.exception.message_dict)

        product_neg = ProductEvidence(
            product_id="test_neg",
            title="Negative Price Item",
            price=Decimal("-10.00"),
            currency="USD",
            source_merchant="Best Buy",
        )
        with self.assertRaises(ValidationError) as ctx:
            product_neg.full_clean()
        self.assertIn("price", ctx.exception.message_dict)

    def test_product_evidence_rejects_non_usd_currency(self):
        """Non-USD currency must fail closed with ValidationError."""
        product_eur = ProductEvidence(
            product_id="test_eur",
            title="Euro Item",
            price=Decimal("50.00"),
            currency="EUR",
            source_merchant="Amazon UK",
        )
        with self.assertRaises(ValidationError) as ctx:
            product_eur.full_clean()
        self.assertIn("currency", ctx.exception.message_dict)

    def test_product_evidence_requires_source_merchant(self):
        """Missing source merchant must fail closed."""
        product_no_merchant = ProductEvidence(
            product_id="test_no_merchant",
            title="No Merchant Item",
            price=Decimal("50.00"),
            currency="USD",
            source_merchant="",
        )
        with self.assertRaises(ValidationError) as ctx:
            product_no_merchant.full_clean()
        self.assertIn("source_merchant", ctx.exception.message_dict)


class ProductSearchCacheTests(TestCase):
    """Test 24-hour query-to-product-ID cache logic."""

    def test_search_cache_expiry_logic(self):
        now = timezone.now()
        # Unexpired entry
        valid_cache = ProductSearchCache.objects.create(
            query_hash="hash_unexpired",
            product_ids=["prod_1", "prod_2"],
            expires_at=now + datetime.timedelta(hours=24),
        )
        self.assertFalse(valid_cache.is_expired())

        # Expired entry
        expired_cache = ProductSearchCache.objects.create(
            query_hash="hash_expired",
            product_ids=["prod_3"],
            expires_at=now - datetime.timedelta(seconds=1),
        )
        self.assertTrue(expired_cache.is_expired())

    def test_search_cache_set_mapping_helper(self):
        entry = ProductSearchCache.set_mapping("hash_test", ["id_a", "id_b"], ttl_hours=24)
        self.assertEqual(entry.query_hash, "hash_test")
        self.assertEqual(entry.product_ids, ["id_a", "id_b"])
        self.assertFalse(entry.is_expired())


class ProductFixturesTests(TestCase):
    """Test pre-packaged demo product fixtures."""

    def test_product_fixtures_provenance_integrity(self):
        fixtures = get_product_fixtures()
        self.assertGreaterEqual(len(fixtures), 5)

        for product in fixtures:
            # Must pass model validation cleanly
            product.full_clean()
            self.assertTrue(product.is_fixture)
            self.assertIsInstance(product.price, Decimal)
            self.assertGreater(product.price, Decimal("0.00"))
            self.assertEqual(product.currency, "USD")
            self.assertTrue(bool(product.source_merchant))
            self.assertTrue(bool(product.product_id))
            # Raw evidence must have disclosure
            self.assertEqual(product.raw_evidence.get("disclosure"), FALLBACK_DISCLOSURE)

    def test_product_fixtures_scenario_filtering(self):
        headphones = get_product_fixtures("headphones")
        self.assertGreaterEqual(len(headphones), 1)
        for p in headphones:
            self.assertIn("WH-CH720N", p.title) if "whch720n" in p.product_id else None

        keyboards = get_product_fixtures("keyboard")
        self.assertGreaterEqual(len(keyboards), 1)

        chairs = get_product_fixtures("chair")
        self.assertGreaterEqual(len(chairs), 1)
