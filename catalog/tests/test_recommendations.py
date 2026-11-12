"""Regression tests for deterministic product recommendation, ranking semantics, and budget integrity.

Verifies:
1. Lowest item subtotal gets the correct distinction ("Lowest Item Subtotal").
2. Highest preference score gets the correct distinction ("Best Preference Match").
3. The same product can qualify for both distinctions.
4. The second-lowest-priced product never receives an undeserved distinction.
5. Equal-price candidates have deterministic tie handling.
6. Quantity is correctly included in item subtotal (unit_price * quantity).
7. Budget remaining is not described as savings.
8. Unknown shipping and tax do not imply an affordable final checkout total.
9. Ineligible and UNKNOWN candidates do not receive eligible-only recommendation badges.
10. Decimal arithmetic is maintained throughout (zero float drift).
"""

from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import ProductEvidence
from catalog.views import _extract_product_highlights
from contracts.models import ContractSource, ContractState, PurchaseContract
from policies.engine import PolicyEngine


class RecommendationSemanticsTests(TestCase):
    """Test suite for deterministic recommendation labels, budget terminology, and ranking semantics."""

    def setUp(self):
        self.client = Client()
        self.policy_engine = PolicyEngine()
        self.contract = PurchaseContract.objects.create(
            raw_prompt="Ergonomic mechanical keyboard under $100 with tactile switches",
            category="Keyboards",
            product_description="Ergonomic mechanical keyboard",
            max_budget=Decimal("100.00"),
            currency="USD",
            quantity=1,
            required_specs={"switches": "tactile"},
            preferred_specs={"backlight": "RGB"},
            state=ContractState.CONFIRMED,
            source=ContractSource.DEMO_FIXTURE,
            version=1,
        )

        # Candidate 1: Lowest price ($49.99) AND highest preference score (RGB backlight -> score 100)
        self.prod_best_both = ProductEvidence.objects.create(
            product_id="PROD-KB-BOTH",
            title="Redragon Antonium K745 Pro Mechanical Keyboard",
            brand="Redragon",
            description="Ergonomic mechanical keyboard with tactile quiet switches and RGB backlight.",
            price=Decimal("49.99"),
            currency="USD",
            stock_status="IN_STOCK",
            source_merchant="Redragon Shop",
            retrieval_timestamp=timezone.now(),
            is_fixture=False,
            raw_evidence={
                "features": {
                    "switch_type": "Tactile Quiet",
                    "backlight": "RGB Multi-color",
                }
            },
        )

        # Candidate 2: Second-lowest price ($79.99), preference score 0 (lacks RGB)
        self.prod_second = ProductEvidence.objects.create(
            product_id="PROD-KB-SECOND",
            title="ErgoPro Wireless Mechanical Keyboard",
            brand="ErgoPro",
            description="Ergonomic mechanical keyboard with tactile brown switches.",
            price=Decimal("79.99"),
            currency="USD",
            stock_status="IN_STOCK",
            source_merchant="Keyboards Co",
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
            raw_evidence={
                "features": {
                    "switch_type": "Tactile Brown",
                }
            },
        )

        # Candidate 3: Over budget ($129.99) -> INELIGIBLE
        self.prod_ineligible = ProductEvidence.objects.create(
            product_id="PROD-KB-OVER",
            title="Over Budget Custom Mechanical Keyboard",
            brand="CustomCo",
            description="Custom mechanical keyboard over budget limit.",
            price=Decimal("129.99"),
            currency="USD",
            stock_status="IN_STOCK",
            source_merchant="Custom Shop",
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
            raw_evidence={"features": {"switch_type": "Tactile", "backlight": "RGB"}},
        )

    def test_item_subtotal_and_budget_remaining_calculated_with_decimal_and_quantity(self):
        """Invariant 6 & 10: item_subtotal = unit_price * quantity; budget_remaining = max_budget - item_subtotal (Decimal)."""
        # Quantity = 1
        h1 = _extract_product_highlights(self.prod_best_both, self.contract, self.policy_engine)
        self.assertIsInstance(h1["unit_price"], Decimal)
        self.assertIsInstance(h1["item_subtotal"], Decimal)
        self.assertIsInstance(h1["budget_remaining"], Decimal)
        self.assertEqual(h1["item_subtotal"], Decimal("49.99"))
        self.assertEqual(h1["budget_remaining"], Decimal("50.01"))

        # Quantity = 2: unit price $49.99 * 2 = $99.98 subtotal; max_budget $100 -> remaining $0.02
        self.contract.quantity = 2
        self.contract.save()
        h2 = _extract_product_highlights(self.prod_best_both, self.contract, self.policy_engine)
        self.assertEqual(h2["quantity"], 2)
        self.assertEqual(h2["item_subtotal"], Decimal("99.98"))
        self.assertEqual(h2["budget_remaining"], Decimal("0.02"))

    def test_budget_remaining_not_described_as_savings(self):
        """Invariant 7: Match reason describes 'item budget remaining' rather than 'savings'."""
        h1 = _extract_product_highlights(self.prod_best_both, self.contract, self.policy_engine)
        self.assertIn("item budget remaining", h1["match_reason"].lower())
        self.assertNotIn("savings", h1["match_reason"].lower())

    def test_unknown_shipping_and_tax_do_not_imply_affordable_final_checkout(self):
        """Invariant 8: Shipping and tax remain explicitly UNCONFIRMED without zero-cost assumptions."""
        h1 = _extract_product_highlights(self.prod_best_both, self.contract, self.policy_engine)
        self.assertEqual(h1["shipping_status"], "UNCONFIRMED")
        self.assertEqual(h1["tax_status"], "UNCONFIRMED")
        self.assertIn("shipping & tax unconfirmed", h1["tradeoff"].lower())

    def test_single_product_can_qualify_for_both_distinctions(self):
        """Invariant 1, 2, 3: The same product can legitimately earn both Lowest Item Subtotal and Best Preference Match."""
        with patch("catalog.services.ProductSearchService.search_for_contract") as mock_search:
            mock_search.return_value = ([self.prod_best_both, self.prod_second], True, "Using test mock")
            resp = self.client.get(reverse("contract_discovery", args=[self.contract.public_ref]))
            self.assertEqual(resp.status_code, 200)

            items = resp.context["decorated_items"]
            item1 = items[0]  # prod_best_both ($49.99, score 100)
            self.assertIn("Lowest Item Subtotal", item1["distinctions"])
            self.assertIn("Best Preference Match", item1["distinctions"])

    def test_second_lowest_priced_product_never_receives_undeserved_distinction(self):
        """Invariant 4: When lowest price item is also best preference match, second item receives NO fake badge."""
        with patch("catalog.services.ProductSearchService.search_for_contract") as mock_search:
            mock_search.return_value = ([self.prod_best_both, self.prod_second], True, "Using test mock")
            resp = self.client.get(reverse("contract_discovery", args=[self.contract.public_ref]))
            self.assertEqual(resp.status_code, 200)

            items = resp.context["decorated_items"]
            item2 = items[1]  # prod_second ($79.99, score 0)
            # Must NOT receive Best Value or any manufactured distinction
            self.assertEqual(item2["distinctions"], [])
            self.assertEqual(item2["badge"], "")

    def test_equal_price_candidates_deterministic_tie_handling(self):
        """Invariant 5: Candidates with identical lowest item subtotal both transparently receive Lowest Item Subtotal."""
        prod_tied = ProductEvidence.objects.create(
            product_id="PROD-KB-TIED",
            title="Tied Price Mechanical Keyboard",
            brand="TiedBrand",
            description="Ergonomic mechanical keyboard with tactile switches.",
            price=Decimal("49.99"),
            currency="USD",
            stock_status="IN_STOCK",
            source_merchant="Tied Shop",
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
            raw_evidence={"features": {"switch_type": "Tactile"}},
        )

        with patch("catalog.services.ProductSearchService.search_for_contract") as mock_search:
            mock_search.return_value = ([self.prod_best_both, prod_tied], True, "Using test mock")
            resp = self.client.get(reverse("contract_discovery", args=[self.contract.public_ref]))
            self.assertEqual(resp.status_code, 200)

            items = resp.context["decorated_items"]
            # Both $49.99 candidates must receive Lowest Item Subtotal
            self.assertIn("Lowest Item Subtotal", items[0]["distinctions"])
            self.assertIn("Lowest Item Subtotal", items[1]["distinctions"])

    def test_ineligible_candidates_never_receive_eligible_distinctions(self):
        """Invariant 9: Ineligible candidate receives Ineligible status, never Lowest Item Subtotal or Best Preference Match."""
        with patch("catalog.services.ProductSearchService.search_for_contract") as mock_search:
            mock_search.return_value = ([self.prod_ineligible], True, "Using test mock")
            resp = self.client.get(reverse("contract_discovery", args=[self.contract.public_ref]))
            self.assertEqual(resp.status_code, 200)

            items = resp.context["decorated_items"]
            ineligible_item = items[0]
            self.assertFalse(ineligible_item["is_eligible"])
            self.assertIn("Ineligible", ineligible_item["distinctions"])
            self.assertNotIn("Lowest Item Subtotal", ineligible_item["distinctions"])
            self.assertNotIn("Best Preference Match", ineligible_item["distinctions"])

    def test_tradeoffs_grounded_in_actual_evidence(self):
        """Trade-offs cite actual missed preferences or budget boundaries."""
        h2 = _extract_product_highlights(self.prod_second, self.contract, self.policy_engine)
        self.assertIn("Lacks preferred: backlight", h2["tradeoff"])
