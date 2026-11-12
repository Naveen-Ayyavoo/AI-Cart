"""Unit tests for the Deterministic Policy Engine.

Covers:
- POL-01 (Deterministic Python rule evaluation)
- POL-02 (Budget ceiling enforcement, unit price * quantity, $0.01 boundary, Decimal precision)
- POL-03 (Excluded terms, stock status, currency, variant matching)
- POL-04 (Auditable rule evaluation reports, preference scoring, UNKNOWN handling)
"""

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from catalog.models import ProductEvidence
from contracts.models import PurchaseContract
from policies.engine import PolicyEngine


class PolicyEngineUnitTests(TestCase):
    """Test policy engine rules, boundary conditions, and unknown handling."""

    def setUp(self):
        self.engine = PolicyEngine()
        self.base_contract = PurchaseContract.objects.create(
            raw_prompt="Tenkeyless mechanical keyboard with red linear switches under $50",
            category="Mechanical Keyboards",
            product_description="Tenkeyless mechanical keyboard with red linear switches",
            max_budget=Decimal("50.00"),
            currency="USD",
            quantity=1,
            required_specs={"layout": "Tenkeyless", "switch_type": "Linear Red"},
            preferred_specs={"backlight": "RGB", "connection": "Detachable USB-C"},
            excluded_terms=["Clicky", "Blue Switch"],
            state="CONFIRMED",
            confirmed_at=timezone.now(),
        )

        self.conforming_product = ProductEvidence.objects.create(
            product_id="test_keychron_c3",
            brand="Keychron",
            title="Keychron C3 Pro TKL Mechanical Keyboard",
            description="Tenkeyless programmable mechanical keyboard with red linear switches and detachable USB-C cable.",
            price=Decimal("36.99"),
            currency="USD",
            source_merchant="Amazon",
            merchant_id="amzn_us",
            variant_id="C3P-A1",
            sku="B0CBWJ945C",
            stock_status="IN_STOCK",
            raw_evidence={"features": {"switch_type": "Linear Red", "layout": "Tenkeyless"}},
        )

    def test_conforming_product_is_eligible(self):
        """Conforming product meeting all constraints evaluates to ELIGIBLE."""
        result = self.engine.evaluate(self.base_contract, self.conforming_product)
        self.assertEqual(result.outcome, "ELIGIBLE")
        self.assertEqual(result.total_item_price, Decimal("36.99"))
        self.assertGreater(result.preference_score, 0)
        self.assertIn("Eligible", result.summary)

    def test_budget_exact_match_passes(self):
        """Total price exactly matching budget ceiling passes."""
        self.conforming_product.price = Decimal("50.00")
        self.conforming_product.save()

        result = self.engine.evaluate(self.base_contract, self.conforming_product)
        self.assertEqual(result.outcome, "ELIGIBLE")
        budget_rule = next(r for r in result.rule_results if r.rule_name == "BudgetCeiling")
        self.assertEqual(budget_rule.outcome, "PASS")

    def test_budget_one_cent_over_fails_closed(self):
        """Total price exactly 1 cent ($0.01) over budget fails closed to INELIGIBLE."""
        self.conforming_product.price = Decimal("50.01")
        self.conforming_product.save()

        result = self.engine.evaluate(self.base_contract, self.conforming_product)
        self.assertEqual(result.outcome, "INELIGIBLE")
        budget_rule = next(r for r in result.rule_results if r.rule_name == "BudgetCeiling")
        self.assertEqual(budget_rule.outcome, "FAIL")
        self.assertIn("exceeds maximum budget ceiling", budget_rule.message)

    def test_quantity_multiplication(self):
        """Unit price must be multiplied by quantity; total compared against budget."""
        # Contract requesting quantity of 2 with $100 budget
        self.base_contract.quantity = 2
        self.base_contract.max_budget = Decimal("100.00")
        self.base_contract.save()

        # Unit price $45 -> total $90 <= $100 -> PASS
        self.conforming_product.price = Decimal("45.00")
        self.conforming_product.save()
        result_pass = self.engine.evaluate(self.base_contract, self.conforming_product)
        self.assertEqual(result_pass.total_item_price, Decimal("90.00"))
        self.assertEqual(result_pass.outcome, "ELIGIBLE")

        # Unit price $55 -> total $110 > $100 -> FAIL
        self.conforming_product.price = Decimal("55.00")
        self.conforming_product.save()
        result_fail = self.engine.evaluate(self.base_contract, self.conforming_product)
        self.assertEqual(result_fail.total_item_price, Decimal("110.00"))
        self.assertEqual(result_fail.outcome, "INELIGIBLE")

    def test_strict_decimal_precision_no_float_drift(self):
        """Ensure monetary calculations have zero binary float drift."""
        # 19.99 * 3 = 59.97 in Decimal
        self.base_contract.quantity = 3
        self.base_contract.max_budget = Decimal("60.00")
        self.base_contract.save()

        self.conforming_product.price = Decimal("19.99")
        self.conforming_product.save()

        result = self.engine.evaluate(self.base_contract, self.conforming_product)
        self.assertEqual(result.total_item_price, Decimal("59.97"))
        self.assertIsInstance(result.total_item_price, Decimal)

    def test_excluded_terms_fails_closed(self):
        """Product mentioning an excluded term in title or description evaluates to INELIGIBLE."""
        self.conforming_product.description += " Features loud clicky tactile feedback."
        self.conforming_product.save()

        result = self.engine.evaluate(self.base_contract, self.conforming_product)
        self.assertEqual(result.outcome, "INELIGIBLE")
        excluded_rule = next(r for r in result.rule_results if r.rule_name == "ExcludedTerms")
        self.assertEqual(excluded_rule.outcome, "FAIL")
        self.assertIn("Clicky", excluded_rule.message)

    def test_missing_critical_spec_produces_unknown_never_eligible(self):
        """Missing or unverifiable required specification yields UNKNOWN, never ELIGIBLE."""
        # Add required spec that does not exist in product evidence
        self.base_contract.required_specs["hot_swappable"] = "Hot-Swappable PCB"
        self.base_contract.save()

        result = self.engine.evaluate(self.base_contract, self.conforming_product)
        self.assertEqual(result.outcome, "UNKNOWN")
        spec_rule = next(r for r in result.rule_results if r.rule_name == "RequiredSpec:hot_swappable")
        self.assertEqual(spec_rule.outcome, "UNKNOWN")
        self.assertIn("could not be verified", spec_rule.message)

    def test_out_of_stock_evaluates_to_ineligible(self):
        """Out of stock product evaluates to INELIGIBLE."""
        self.conforming_product.stock_status = "OUT_OF_STOCK"
        self.conforming_product.save()

        result = self.engine.evaluate(self.base_contract, self.conforming_product)
        self.assertEqual(result.outcome, "INELIGIBLE")
        stock_rule = next(r for r in result.rule_results if r.rule_name == "StockAvailability")
        self.assertEqual(stock_rule.outcome, "FAIL")

    def test_unknown_stock_evaluates_to_unknown(self):
        """Unverified stock status evaluates to UNKNOWN, never ELIGIBLE."""
        self.conforming_product.stock_status = "UNKNOWN"
        self.conforming_product.save()

        result = self.engine.evaluate(self.base_contract, self.conforming_product)
        self.assertEqual(result.outcome, "UNKNOWN")
        stock_rule = next(r for r in result.rule_results if r.rule_name == "StockAvailability")
        self.assertEqual(stock_rule.outcome, "UNKNOWN")

    def test_currency_mismatch_evaluates_to_ineligible(self):
        """Non-USD currency evaluates to INELIGIBLE."""
        self.conforming_product.currency = "EUR"
        self.conforming_product.save()

        result = self.engine.evaluate(self.base_contract, self.conforming_product)
        self.assertEqual(result.outcome, "INELIGIBLE")
        currency_rule = next(r for r in result.rule_results if r.rule_name == "CurrencyMatch")
        self.assertEqual(currency_rule.outcome, "FAIL")

    def test_preference_scoring_cannot_override_mandatory_failure(self):
        """High preference score cannot convert an INELIGIBLE item into ELIGIBLE."""
        # Product matches 100% of preferences ("RGB" and "USB-C")
        self.conforming_product.description += " RGB backlight and detachable USB-C."
        # But violates budget ceiling
        self.conforming_product.price = Decimal("999.00")
        self.conforming_product.save()

        result = self.engine.evaluate(self.base_contract, self.conforming_product)
        self.assertEqual(result.outcome, "INELIGIBLE")
        self.assertGreater(result.preference_score, 0)
        self.assertIn("Ineligible", result.summary)

    def test_rule_evaluation_record_provenance(self):
        """Every rule record must record rule name, outcome, expected, observed, and source."""
        result = self.engine.evaluate(self.base_contract, self.conforming_product)
        self.assertGreaterEqual(len(result.rule_results), 6)

        for record in result.rule_results:
            self.assertIn(record.outcome, ["PASS", "FAIL", "UNKNOWN"])
            self.assertTrue(bool(record.rule_name))
            self.assertIsNotNone(record.expected_value)
            self.assertIsNotNone(record.observed_value)
            self.assertEqual(record.evidence_source, "Amazon")
            self.assertTrue(bool(record.retrieval_timestamp))

    def test_shipping_tax_disclosure_present(self):
        """Result must contain disclosure that shipping and taxes are not confirmed."""
        result = self.engine.evaluate(self.base_contract, self.conforming_product)
        self.assertIn("shipping", result.shipping_tax_disclosure.lower())
        self.assertIn("affordability cannot be guaranteed", result.shipping_tax_disclosure.lower())
