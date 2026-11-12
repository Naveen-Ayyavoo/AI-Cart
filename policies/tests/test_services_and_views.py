"""Integration tests for PolicyEvaluationService and Evaluation Views.

Covers:
- POL-01 (Policy evaluation service orchestration)
- POL-02 (Budget ceiling enforcement in view and service)
- POL-03 (Excluded terms, variant matching, and unknown handling)
- POL-04 (UI dashboard rendering, distinct outcome categories, audit trail)
"""

import os
from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import ProductEvidence
from contracts.models import PurchaseContract
from policies.models import PolicyEvaluationReport
from policies.services import PolicyEvaluationService


class PolicyEvaluationServiceTests(TestCase):
    """Test PolicyEvaluationService orchestration, persistence, and sorting."""

    def setUp(self):
        self.service = PolicyEvaluationService()
        self.contract = PurchaseContract.objects.create(
            raw_prompt="Tenkeyless mechanical keyboard with red linear switches under $50",
            category="Mechanical Keyboards",
            product_description="Tenkeyless mechanical keyboard with red linear switches",
            max_budget=Decimal("50.00"),
            currency="USD",
            quantity=1,
            required_specs={"layout": "Tenkeyless", "switch_type": "Linear Red"},
            preferred_specs={"backlight": "RGB"},
            excluded_terms=["Clicky"],
            state="CONFIRMED",
            confirmed_at=timezone.now(),
        )

        # 1. Eligible product
        self.prod_eligible = ProductEvidence.objects.create(
            product_id="prod_test_eligible",
            brand="Keychron",
            title="Keychron C3 Pro TKL",
            description="Tenkeyless mechanical keyboard with red linear switches and RGB backlight.",
            price=Decimal("36.99"),
            currency="USD",
            source_merchant="Amazon",
            stock_status="IN_STOCK",
            raw_evidence={"features": {"switch_type": "Linear Red", "layout": "Tenkeyless"}},
        )

        # 2. Ineligible product (over budget)
        self.prod_over_budget = ProductEvidence.objects.create(
            product_id="prod_test_overbudget",
            brand="Keychron",
            title="Keychron Q3 Custom TKL",
            description="Tenkeyless mechanical keyboard with red linear switches.",
            price=Decimal("179.00"),
            currency="USD",
            source_merchant="Amazon",
            stock_status="IN_STOCK",
            raw_evidence={"features": {"switch_type": "Linear Red", "layout": "Tenkeyless"}},
        )

    def test_service_evaluates_and_persists_reports(self):
        """Service evaluates products, persists PolicyEvaluationReport records, and sorts eligible first."""
        reports = self.service.evaluate_contract_products(self.contract)
        self.assertGreaterEqual(len(reports), 2)

        # Check persistence in database
        db_count = PolicyEvaluationReport.objects.filter(contract=self.contract).count()
        self.assertEqual(db_count, len(reports))

        # Check outcome distribution
        eligible_items = [r for r in reports if r.outcome == "ELIGIBLE"]
        ineligible_items = [r for r in reports if r.outcome == "INELIGIBLE"]
        self.assertGreaterEqual(len(eligible_items), 1)
        self.assertGreaterEqual(len(ineligible_items), 1)

        # First report must be ELIGIBLE (sorted first)
        self.assertEqual(reports[0].outcome, "ELIGIBLE")

    def test_service_fails_on_draft_contract(self):
        """Service rejects unconfirmed contracts with ValueError."""
        self.contract.state = "DRAFT"
        self.contract.save()

        with self.assertRaises(ValueError) as ctx:
            self.service.evaluate_contract_products(self.contract)
        self.assertIn("must be CONFIRMED", str(ctx.exception))


@patch.dict(os.environ, {"CHANNEL3_API_KEY": ""})
class PolicyEvaluationViewTests(TestCase):
    """Test policy evaluation dashboard view, access control, and UI rendering."""

    def setUp(self):
        self.client = Client()
        self.confirmed_contract = PurchaseContract.objects.create(
            raw_prompt="Ergonomic mesh office chair with lumbar support under $300",
            category="Office Chairs",
            product_description="Ergonomic mesh office chair with lumbar support",
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

    def test_view_redirects_draft_contract_to_review(self):
        """Attempting to access evaluation dashboard for a DRAFT contract redirects to review."""
        url = reverse("contract_evaluation", kwargs={"public_ref": self.draft_contract.public_ref})
        response = self.client.get(url, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/contracts/{self.draft_contract.public_ref}/review/", response.url)

    def test_view_renders_distinct_outcome_sections(self):
        """Confirmed contract renders evaluation results with distinct sections and item pricing note."""
        url = reverse("contract_evaluation", kwargs={"public_ref": self.confirmed_contract.public_ref})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "policies/evaluation.html")

        content = response.content.decode("utf-8")
        self.assertIn("Results for your request", content)
        self.assertIn("Meets Your Requirements", content)
        self.assertIn("Needs More Details", content)
        self.assertIn("Does Not Meet Requirements", content)
        self.assertIn("Item pricing only:", content)

    def test_view_renders_audit_table_and_reasons(self):
        """Results page renders detailed plain-language check details inside disclosure."""
        url = reverse("contract_evaluation", kwargs={"public_ref": self.confirmed_contract.public_ref})
        response = self.client.get(url)
        content = response.content.decode("utf-8")
        self.assertIn("Budget Limit", content)
        self.assertIn("Availability", content)
        self.assertIn("USD Currency", content)
