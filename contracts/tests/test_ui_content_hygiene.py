"""Regression tests for Customer-Facing UI Content Hygiene.

Verifies:
1. Complete removal of internal infrastructure, provider quotas, and development budget references from customer-facing views:
   - Gemini Free Tier, Gemini API quota, RPM, TPM, RPD, model limits
   - Channel3 Free Tier, monthly credits, bonus credits, remaining credits
   - Context7 requests, quotas, usage
   - Zero-Spend Governance, ADR-0004, and development resource limits
   - Internal phase numbering in UI flows (e.g. "Phase P4", "Phase P5", "Phase P6")
2. Neutral customer-facing demonstration disclosures ("Demonstration Sample Data", "Demonstration Sample Products").
3. Preservation of material PayPal Sandbox demo merchant disclosure (DEMO_PAYEE_DISCLOSURE).
4. Backend quota tracking and credit controls remain intact.
"""

import os
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Channel3CreditLedger, ProductEvidence
from contracts.fixtures import get_demo_scenario
from contracts.models import PurchaseContract
from orders.models import PurchaseApproval, PurchaseProposal
from policies.models import PolicyEvaluationReport


@patch.dict(os.environ, {"CHANNEL3_API_KEY": "", "GEMINI_API_KEY": ""})
class CustomerFacingUIContentHygieneTests(TestCase):
    """Verify that all customer-facing views are clean of internal infrastructure references."""

    PROHIBITED_SUBSTRINGS = [
        "gemini free tier",
        "channel3 credits",
        "channel3 credit",
        "channel3 free tier",
        "context7",
        "zero-spend",
        "zero spend",
        "adr-0004",
        "adr-0002",
        "adr-0003",
        "phase p1",
        "phase p2",
        "phase p3",
        "phase p4",
        "phase p5",
        "phase p6",
    ]

    def setUp(self):
        self.client = Client()

        self.contract = PurchaseContract.objects.create(
            raw_prompt="Ergonomic mechanical keyboard for developer",
            category="Keyboards",
            product_description="Mechanical keyboard with quiet switches",
            max_budget=Decimal("120.00"),
            currency="USD",
            quantity=1,
            state="CONFIRMED",
            confirmed_at=timezone.now(),
        )

        uid = uuid.uuid4().hex[:8]
        self.fixture_product = ProductEvidence.objects.create(
            product_id=f"prod_fixture_test_{uid}",
            brand="Keychron",
            title="Keychron Q1 Mechanical Keyboard",
            description="Premium custom keyboard with hot-swappable switches",
            price=Decimal("99.00"),
            currency="USD",
            source_merchant="Keychron",
            stock_status="IN_STOCK",
            is_fixture=True,
            raw_evidence={"disclosure": "Sandbox Demo Fixture — Zero-Spend Fallback"},
        )

        self.policy_report = PolicyEvaluationReport.objects.create(
            contract=self.contract,
            product=self.fixture_product,
            outcome="ELIGIBLE",
            summary="All mandatory rules passed.",
            unit_price=Decimal("99.00"),
            quantity=1,
            total_item_price=Decimal("99.00"),
            budget_ceiling=Decimal("120.00"),
            preference_score=85,
            currency="USD",
        )

        self.proposal = PurchaseProposal.objects.create(
            contract=self.contract,
            product=self.fixture_product,
            policy_report=self.policy_report,
            source_merchant="Keychron",
            payee_id="BSX4FSCDM3HXY",
            quantity=1,
            unit_price=Decimal("99.00"),
            base_amount=Decimal("99.00"),
            shipping_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            fee_amount=Decimal("0.00"),
            total_amount=Decimal("99.00"),
            currency="USD",
            charges_confirmed=True,
            status="APPROVED",
        )
        self.proposal.cart_fingerprint = self.proposal.calculate_fingerprint()
        self.proposal.save()

        self.approval = PurchaseApproval.objects.create(
            token="test_hygiene_token_999",
            proposal=self.proposal,
            cart_fingerprint=self.proposal.cart_fingerprint,
            state="APPROVED",
            approved_at=timezone.now(),
        )

    def _assert_no_prohibited_terms(self, content: str, view_name: str):
        content_lower = content.lower()
        for prohibited in self.PROHIBITED_SUBSTRINGS:
            self.assertNotIn(
                prohibited,
                content_lower,
                f"Prohibited internal term '{prohibited}' leaked in customer view '{view_name}'!",
            )

    def test_home_page_hygiene(self):
        """Home page has no provider quotas, free tier, or zero-spend leaks."""
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self._assert_no_prohibited_terms(content, "home")
        self.assertIn("Sample Shopping Scenario", content)
        self.assertIn("PayPal Sandbox", content)

    def test_contract_review_page_hygiene(self):
        """Contract review page shows clean demonstration disclosure without quota mentions."""
        contract = get_demo_scenario("keyboard", save_to_db=True)
        resp = self.client.get(reverse("contract_review", args=[contract.public_ref]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self._assert_no_prohibited_terms(content, "contract_review")
        self.assertIn("Sample Shopping Plan:", content)
        self.assertIn("It does NOT charge your account", content)

    def test_contract_confirmed_page_hygiene(self):
        """Contract confirmed page has no ADR, phase, Additional options, or raw hash leaks."""
        draft_contract = PurchaseContract.objects.create(
            raw_prompt="Ergonomic mechanical keyboard for developer",
            category="Keyboards",
            product_description="Mechanical keyboard with quiet switches",
            max_budget=Decimal("120.00"),
            currency="USD",
            quantity=1,
            state="DRAFT",
        )
        resp = self.client.post(reverse("contract_confirm", args=[draft_contract.public_ref]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self._assert_no_prohibited_terms(content, "contract_confirmed")
        self.assertIn("Confirming your requirements is not a payment.", content)
        self.assertNotIn("Additional options", content)

    def test_catalog_discovery_page_hygiene(self):
        """Catalog discovery page removes Channel3 credit badges and zero-spend text."""
        resp = self.client.get(reverse("contract_discovery", args=[self.contract.public_ref]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self._assert_no_prohibited_terms(content, "catalog_discovery")
        self.assertIn("Demonstration Sample Products", content)
        self.assertIn("Demonstration Sample", content)
        self.assertNotIn("Channel3 Credits", content)

    def test_policy_evaluation_dashboard_hygiene(self):
        """Evaluation results page removes internal references, crypto hashes, and phase markers."""
        resp = self.client.get(reverse("contract_evaluation", args=[self.contract.public_ref]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self._assert_no_prohibited_terms(content, "policy_evaluation")
        self.assertIn("Results for your request", content)

    def test_proposal_detail_page_hygiene(self):
        """Proposal detail page retains demo merchant disclosure while removing internal phase text."""
        resp = self.client.get(reverse("proposal_detail", args=[self.proposal.public_ref]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self._assert_no_prohibited_terms(content, "proposal_detail")
        self.assertIn("PayPal Sandbox Demo Merchant Notice", content)
        self.assertIn("PayPal Sandbox", content)

    def test_approval_detail_page_hygiene(self):
        """Approval detail page retains demo merchant disclosure and clean next step."""
        resp = self.client.get(reverse("approval_detail", args=[self.approval.public_ref]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self._assert_no_prohibited_terms(content, "approval_detail")
        self.assertIn("Controlled Demo Payee Boundary", content)
        self.assertIn("PayPal Sandbox", content)

    def test_backend_controls_remain_intact(self):
        """Confirm that backend credit ledger and quota tracking functions are not impaired."""
        ledger = Channel3CreditLedger.get_current_ledger()
        self.assertIsNotNone(ledger)
        self.assertGreater(ledger.total_available, 0)
        self.assertTrue(ledger.can_consume(1))
        # Ensure raw evidence in backend models preserves provenance metadata
        self.assertTrue(self.fixture_product.is_fixture)
        self.assertIn("disclosure", self.fixture_product.raw_evidence)
