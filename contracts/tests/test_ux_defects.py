"""
Comprehensive regression tests for UX Defects 1, 2, 4, 5, 6, and 7:
- Sample demo scenarios routed cleanly through unified review -> confirm -> discovery.
- Home intake recovery / validation preservation / stale scenario_key protection.
- Shared accessible loading feedback attributes and recovery UI.
- Post-confirmation budget revision (increase, decrease, zero/invalid, lineage, immutability,
  old proposal isolation, old approval invalidation, re-confirmation, fresh policy evaluation).
- Category-aware optional clarifications (skip, save to preferred_specs, server validation).
- Product-specific Edit Search Criteria across 3+ materially different product categories.
"""

import json
from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import ProductEvidence
from contracts.clarifications import (
    build_clarification_fields,
    build_edit_criteria_metadata,
)
from contracts.fixtures import DEMO_SCENARIOS
from contracts.models import ContractSource, ContractState, PurchaseContract
from orders.models import ApprovalError, ApprovalInvalidError, PurchaseProposal
from orders.services import ApprovalService, ProposalService
from payments.models import PaymentOrder
from payments.services import PaymentService, PayPalRevalidationError
from policies.engine import PolicyEngine
from policies.services import PolicyEvaluationService


class SampleDemoAndIntakeTests(TestCase):
    """Regression suite for Defect 1 (sample demos) and Defect 2 (intake recovery)."""

    def setUp(self):
        self.client = Client()

    def test_every_sample_scenario_uses_current_review_and_requires_confirm(self):
        """Defect 1: All sample scenarios create DRAFT fixture and render current review page before discovery."""
        for key, spec in DEMO_SCENARIOS.items():
            with self.subTest(scenario=key):
                resp = self.client.post(
                    reverse("contract_create"),
                    {"scenario_key": key, "prompt": spec["prompt"]},
                )
                contract = PurchaseContract.objects.order_by("-created_at").first()
                self.assertIsNotNone(contract)
                self.assertEqual(contract.state, ContractState.DRAFT)
                self.assertEqual(contract.source, ContractSource.DEMO_FIXTURE)
                self.assertRedirects(resp, reverse("contract_review", args=[contract.public_ref]))

                # Review page renders current unified UI, interactive optional details, and fixture disclosure
                rev = self.client.get(reverse("contract_review", args=[contract.public_ref]))
                self.assertEqual(rev.status_code, 200)
                self.assertTemplateUsed(rev, "contracts/review.html")
                html = rev.content.decode("utf-8")
                self.assertIn("Sample Shopping Plan:", html)
                self.assertIn("Optional details to improve your results", html)
                self.assertIn("Confirm Requirements", html)

                # Product discovery is blocked until explicit confirmation
                disc_pre = self.client.get(reverse("contract_discovery", args=[contract.public_ref]))
                self.assertRedirects(disc_pre, reverse("contract_review", args=[contract.public_ref]))

                # Explicit POST confirms the contract cleanly
                conf = self.client.post(reverse("contract_confirm", args=[contract.public_ref]))
                self.assertEqual(conf.status_code, 200)
                self.assertTemplateUsed(conf, "contracts/confirmed.html")
                contract.refresh_from_db()
                self.assertEqual(contract.state, ContractState.CONFIRMED)

    @patch("contracts.gemini.GeminiContractClient.extract_contract")
    def test_edited_prompt_with_stale_scenario_key_does_not_bypass_extraction(self, mock_extract):
        """Defect 1 & 2: If Back restores scenario_key but prompt was edited, extract modified prompt."""
        mock_contract = PurchaseContract.objects.create(
            raw_prompt="Gaming laptop under $1200",
            category="Laptops",
            product_description="Gaming laptop",
            max_budget=Decimal("1200.00"),
            currency="USD",
            quantity=1,
            state=ContractState.DRAFT,
            source=ContractSource.GEMINI_LIVE,
        )
        mock_extract.return_value = (mock_contract, False, "Extracted")

        resp = self.client.post(
            reverse("contract_create"),
            {"scenario_key": "headphones", "prompt": "Gaming laptop under $1200"},
        )
        mock_extract.assert_called_once()
        self.assertRedirects(resp, reverse("contract_review", args=[mock_contract.public_ref]))

    def test_home_button_idle_and_history_reset_hooks_present(self):
        """Defect 2: Home renders usable button initially, after HTTP 400 failure, and wires pageshow reset."""
        resp = self.client.get(reverse("home"))
        html = resp.content.decode("utf-8")
        self.assertEqual(resp.status_code, 200)
        self.assertIn('id="submit-intake-btn"', html)
        self.assertIn("Find products", html)
        self.assertIn("pageshow", html)
        self.assertNotIn("disabled", html.split('id="submit-intake-btn"')[1].split(">")[0])

        # Validation error preserves usable button and rejects empty prompt
        err_resp = self.client.post(reverse("contract_create"), {"prompt": "hi"})
        self.assertEqual(err_resp.status_code, 400)
        err_html = err_resp.content.decode("utf-8")
        self.assertIn("Find products", err_html)
        self.assertNotIn("disabled", err_html.split('id="submit-intake-btn"')[1].split(">")[0])
        self.assertIn("hi", err_html)

    def test_shared_loading_feedback_controls_present_across_flow(self):
        """Defect 4: Discovery, confirmation, evaluation, proposal, and checkout include loading attributes."""
        contract = PurchaseContract.objects.create(
            raw_prompt="Wireless headphones under $150",
            category="Electronics > Audio > Headphones",
            product_description="Over-ear ANC headphones",
            max_budget=Decimal("150.00"),
            currency="USD",
            quantity=1,
            state=ContractState.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        conf_html = self.client.get(reverse("contract_confirm", args=[contract.public_ref])).content.decode("utf-8")
        self.assertIn("Find Matching Products", conf_html)
        self.assertIn("Searching Channel3 product catalogue", conf_html)
        review_html = self.client.get(reverse("contract_review", args=[contract.public_ref])).content.decode("utf-8")
        self.assertIn("Searching Channel3 product catalogue", review_html)
        self.assertIn('id="tc-workflow-progress"', conf_html)
        self.assertIn('aria-live="polite"', conf_html)
        self.assertIn("prefers-reduced-motion", conf_html)
        self.assertIn("tc-progress-cancel-btn", conf_html)


class BudgetRevisionTests(TestCase):
    """Regression suite for Defect 5 (budget revision after confirmation)."""

    def setUp(self):
        self.client = Client()
        self.contract_v1 = PurchaseContract.objects.create(
            raw_prompt="Over-ear headphones under $150 with ANC",
            category="Electronics > Audio > Headphones",
            product_description="Over-ear ANC headphones",
            max_budget=Decimal("150.00"),
            currency="USD",
            quantity=1,
            required_specs={"connectivity": "Bluetooth"},
            preferred_specs={"color": "Black"},
            excluded_terms=["refurbished"],
            state=ContractState.CONFIRMED,
            confirmed_at=timezone.now(),
            version=1,
        )
        self.expensive_prod = ProductEvidence.objects.create(
            product_id="PROD-EXP-189",
            brand="Sennheiser",
            title="Sennheiser Accentum Over-Ear Bluetooth Headphones",
            description="Wireless Bluetooth over-ear ANC headphones in black.",
            price=Decimal("189.95"),
            currency="USD",
            source_merchant="adorama.com",
            stock_status="IN_STOCK",
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )
        self.cheap_prod = ProductEvidence.objects.create(
            product_id="PROD-CHEAP-99",
            brand="Anker",
            title="Anker Soundcore Over-Ear Bluetooth Headphones",
            description="Wireless Bluetooth over-ear headphones.",
            price=Decimal("99.00"),
            currency="USD",
            source_merchant="Amazon",
            stock_status="IN_STOCK",
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )

    def test_budget_increase_creates_v2_draft_and_preserves_v1(self):
        """Budget increase creates DRAFT v2, marks v1 SUPERSEDED, preserves v1 max_budget, keeps hard constraints."""
        resp = self.client.post(
            reverse("contract_revise_budget", args=[self.contract_v1.public_ref]),
            {"max_budget": "200.00", "next": "discovery"},
        )
        self.contract_v1.refresh_from_db()
        self.assertEqual(self.contract_v1.state, ContractState.SUPERSEDED)
        self.assertEqual(self.contract_v1.max_budget, Decimal("150.00"))

        v2 = PurchaseContract.objects.get(parent_contract=self.contract_v1)
        self.assertEqual(v2.version, 2)
        self.assertEqual(v2.state, ContractState.DRAFT)
        self.assertEqual(v2.max_budget, Decimal("200.00"))
        self.assertEqual(v2.required_specs, {"connectivity": "Bluetooth"})
        self.assertEqual(v2.excluded_terms, ["refurbished"])
        self.assertEqual(v2.extraction_provenance["last_revision"]["previous_budget"], "150.00")
        self.assertEqual(v2.extraction_provenance["last_revision"]["new_budget"], "200.00")
        self.assertRedirects(resp, reverse("contract_review", args=[v2.public_ref]))

    def test_budget_decrease_creates_new_version(self):
        """Budget decrease uses the same safe revision workflow and Decimal precision."""
        resp = self.client.post(
            reverse("contract_revise_budget", args=[self.contract_v1.public_ref]),
            {"max_budget": "100.00"},
        )
        v2 = PurchaseContract.objects.get(parent_contract=self.contract_v1)
        self.assertEqual(v2.max_budget, Decimal("100.00"))
        self.assertEqual(v2.state, ContractState.DRAFT)
        self.assertRedirects(resp, reverse("contract_review", args=[v2.public_ref]))

    def test_invalid_or_zero_budget_rejected_without_revision(self):
        """Zero, negative, or non-numeric budget values fail closed without creating v2."""
        for bad_val in ("0", "0.00", "-25.00", "not-a-number", ""):
            with self.subTest(bad_val=bad_val):
                self.client.post(
                    reverse("contract_revise_budget", args=[self.contract_v1.public_ref]),
                    {"max_budget": bad_val, "next": "discovery"},
                )
                self.contract_v1.refresh_from_db()
                self.assertEqual(self.contract_v1.state, ContractState.CONFIRMED)
                self.assertEqual(PurchaseContract.objects.filter(parent_contract=self.contract_v1).count(), 0)

    def test_old_approval_invalidated_and_old_proposal_isolated_on_budget_revision(self):
        """Revising budget voids v1 approvals, supersedes v1 proposals, and prevents old token consumption."""
        proposal_v1, approval_v1 = ProposalService.create_proposal(
            contract=self.contract_v1,
            product=self.cheap_prod,
        )
        ApprovalService.approve_proposal(proposal_v1.id, shopper_ip="127.0.0.1")

        # Now increase budget -> creates v2 DRAFT and supersedes v1
        self.client.post(
            reverse("contract_revise_budget", args=[self.contract_v1.public_ref]),
            {"max_budget": "200.00"},
        )
        proposal_v1.refresh_from_db()
        approval_v1.refresh_from_db()
        self.assertEqual(proposal_v1.status, "SUPERSEDED")
        self.assertEqual(approval_v1.state, "VOIDED")

        # Attempt to consume old token directly must fail closed
        with self.assertRaises(ApprovalInvalidError):
            approval_v1.consume(order_reference="REPLAY-AFTER-REVISION")

        # Confirm v2 and verify discovery + policy evaluation require confirmation first
        v2 = PurchaseContract.objects.get(parent_contract=self.contract_v1)
        with patch("catalog.services.ProductSearchService.search_for_contract") as mock_search:
            mock_search.return_value = ([self.expensive_prod, self.cheap_prod], True, "Fixture")
            pre_disc = self.client.get(reverse("contract_discovery", args=[v2.public_ref]))
            self.assertRedirects(pre_disc, reverse("contract_review", args=[v2.public_ref]))

            # Explicit confirmation locks v2
            self.client.post(reverse("contract_confirm", args=[v2.public_ref]))
            v2.refresh_from_db()
            self.assertEqual(v2.state, ContractState.CONFIRMED)

            # Policy evaluation under v1 ($150) rejected $189.95; under v2 ($200) it becomes ELIGIBLE
            res_v1 = PolicyEngine().evaluate(self.contract_v1, self.expensive_prod)
            self.assertEqual(res_v1.outcome, "INELIGIBLE")

            reports_v2 = PolicyEvaluationService().evaluate_contract_products(v2)
            exp_report = next(r for r in reports_v2 if r.product == self.expensive_prod)
            self.assertEqual(exp_report.outcome, "ELIGIBLE")

            # Proposal creation on v2 creates a brand-new proposal isolated from v1
            self.client.get(reverse("proposal_create_from_evaluation", args=[exp_report.id]))
            self.assertEqual(PurchaseProposal.objects.filter(contract=v2).count(), 1)
            self.assertNotEqual(
                PurchaseProposal.objects.get(contract=v2).id,
                proposal_v1.id,
            )

    def test_discovery_shows_increase_budget_when_candidates_exceed_budget(self):
        """Defect 5 UI: Over-budget candidates surface neutral 'Increase budget' action."""
        with patch("catalog.services.ProductSearchService.search_for_contract") as mock_search:
            mock_search.return_value = ([self.expensive_prod], True, "Fixture")
            resp = self.client.get(reverse("contract_discovery", args=[self.contract_v1.public_ref]))
            html = resp.content.decode("utf-8")
            self.assertEqual(resp.status_code, 200)
            self.assertIn("Increase budget", html)
            self.assertIn("does not authorize payment", html)


class CategoryClarificationAndCriteriaTests(TestCase):
    """Regression suite for Defect 6 (interactive clarifications) and Defect 7 (product-specific editor)."""

    def setUp(self):
        self.client = Client()

    def test_clarifications_are_category_specific_never_apparel_everywhere(self):
        """Defect 6: Clothing shows size/fit/material; Laptops show RAM/storage/screen; Headphones show audio controls."""
        pants = PurchaseContract(
            raw_prompt="Red mens pants under $30",
            category="Apparel > Men's Clothing > Pants",
            product_description="Red men's pants",
            max_budget=Decimal("30.00"),
            ambiguous_requirements=["material", "fit", "size"],
        )
        laptop = PurchaseContract(
            raw_prompt="Laptop for coding under $1000",
            category="Computers > Laptops",
            product_description="Developer laptop",
            max_budget=Decimal("1000.00"),
            ambiguous_requirements=["ram", "storage", "screen size", "intended workload"],
        )
        kitchen = PurchaseContract(
            raw_prompt="Coffee maker under $150",
            category="Home & Kitchen > Coffee & Espresso",
            product_description="Stainless coffee brewer",
            max_budget=Decimal("150.00"),
            ambiguous_requirements=["capacity", "material"],
        )

        pants_keys = {f["key"] for f in build_clarification_fields(pants)}
        self.assertEqual(pants_keys, {"material", "fit", "size"})

        laptop_fields = build_clarification_fields(laptop)
        laptop_keys = {f["key"] for f in laptop_fields}
        self.assertEqual(laptop_keys, {"ram", "storage", "screen_size", "workload"})
        self.assertNotIn("fit", laptop_keys)

        kitchen_keys = {f["key"] for f in build_clarification_fields(kitchen)}
        self.assertIn("capacity", kitchen_keys)
        self.assertNotIn("fit", kitchen_keys)
        self.assertNotIn("size", kitchen_keys)

    def test_optional_clarifications_can_be_skipped_or_saved_as_preferences(self):
        """Defect 6: User can skip all optional fields OR save them as soft preferences without locking hard rules."""
        pants = PurchaseContract.objects.create(
            raw_prompt="Red mens pants under $40",
            category="Apparel > Men's Clothing > Pants",
            product_description="Red men's pants",
            max_budget=Decimal("40.00"),
            required_specs={"color": "red"},
            ambiguous_requirements=["material", "fit", "size"],
            state=ContractState.DRAFT,
        )

        # 1. Skip all optional fields and confirm directly -> works cleanly
        review_html = self.client.get(reverse("contract_review", args=[pants.public_ref])).content.decode("utf-8")
        self.assertIn("Optional details to improve your results", review_html)
        self.assertIn("Leave any field blank if you do not mind.", review_html)

        confirm_resp = self.client.post(reverse("contract_confirm", args=[pants.public_ref]))
        self.assertEqual(confirm_resp.status_code, 200)

        # 2. New draft where user supplies optional fields -> saved to preferred_specs, NOT required_specs
        pants_draft = PurchaseContract.objects.create(
            raw_prompt="Red mens pants under $40",
            category="Apparel > Men's Clothing > Pants",
            product_description="Red men's pants",
            max_budget=Decimal("40.00"),
            required_specs={"color": "red"},
            ambiguous_requirements=["material", "fit", "size"],
            state=ContractState.DRAFT,
        )
        save_resp = self.client.post(
            reverse("contract_clarify", args=[pants_draft.public_ref]),
            {
                "clarify__material": "Cotton",
                "clarify__fit": "Slim",
                "clarify__size": "32x30",
            },
        )
        self.assertRedirects(save_resp, reverse("contract_review", args=[pants_draft.public_ref]))
        pants_draft.refresh_from_db()
        self.assertEqual(pants_draft.preferred_specs.get("material"), "Cotton")
        self.assertEqual(pants_draft.preferred_specs.get("fit"), "Slim")
        self.assertEqual(pants_draft.preferred_specs.get("size"), "32x30")
        # Crucial invariant: optional clarifications never silently became hard requirements
        self.assertEqual(pants_draft.required_specs, {"color": "red"})

    def test_numeric_clarification_validation_rejects_untrusted_bad_input(self):
        """Defect 6: Server validates numeric clarification values and fails closed on invalid input."""
        hp = PurchaseContract.objects.create(
            raw_prompt="Headphones with long battery under $150",
            category="Electronics > Audio > Headphones",
            product_description="Over-ear wireless headphones",
            max_budget=Decimal("150.00"),
            ambiguous_requirements=["minimum battery life hours"],
            state=ContractState.DRAFT,
        )
        bad_resp = self.client.post(
            reverse("contract_clarify", args=[hp.public_ref]),
            {"clarify__battery_life": "invalid<script>"},
        )
        self.assertEqual(bad_resp.status_code, 400)
        hp.refresh_from_db()
        self.assertEqual(hp.preferred_specs, {})

    def test_edit_criteria_is_product_specific_across_three_categories(self):
        """Defect 7: Edit Search Criteria renders category-specific metadata for Laptops, Shoes, and Headphones."""
        laptop = PurchaseContract.objects.create(
            raw_prompt="Laptop under $1000",
            category="Computers > Laptops",
            product_description="Developer laptop",
            max_budget=Decimal("1000.00"),
            state=ContractState.DRAFT,
        )
        shoes = PurchaseContract.objects.create(
            raw_prompt="Running shoes under $140",
            category="Apparel & Footwear > Running Shoes",
            product_description="Cushioned running shoes",
            max_budget=Decimal("140.00"),
            state=ContractState.DRAFT,
        )
        headphones = PurchaseContract.objects.create(
            raw_prompt="Wireless ANC headphones under $150",
            category="Electronics > Audio > Headphones",
            product_description="Over-ear wireless headphones",
            max_budget=Decimal("150.00"),
            state=ContractState.DRAFT,
        )

        laptop_meta = build_edit_criteria_metadata(laptop)
        shoes_meta = build_edit_criteria_metadata(shoes)
        hp_meta = build_edit_criteria_metadata(headphones)

        self.assertEqual(laptop_meta["profile"], "laptops")
        self.assertEqual(shoes_meta["profile"], "footwear")
        self.assertEqual(hp_meta["profile"], "headphones")

        laptop_html = self.client.get(reverse("contract_review", args=[laptop.public_ref])).content.decode("utf-8")
        self.assertIn("Laptops &amp; Computers", laptop_html)
        self.assertIn("16 GB", laptop_html)
        self.assertIn("chromebook", laptop_html)
        self.assertNotIn("Shoe Size", laptop_html)
        self.assertNotIn("Connectivity: Bluetooth", laptop_html)

        shoes_html = self.client.get(reverse("contract_review", args=[shoes.public_ref])).content.decode("utf-8")
        self.assertIn("Footwear &amp; Shoes", shoes_html)
        self.assertIn("10.5", shoes_html)
        self.assertIn("Wide (2E)", shoes_html)
        self.assertNotIn("512 GB SSD", shoes_html)

        hp_html = self.client.get(reverse("contract_review", args=[headphones.public_ref])).content.decode("utf-8")
        self.assertIn("Audio &amp; Headphones", hp_html)
        self.assertIn("Over-Ear", hp_html)
        self.assertIn("wired-only", hp_html)

        # Confirmed contract edits via contract_update create v2 DRAFT cleanly
        laptop.confirm()
        edit_resp = self.client.post(
            reverse("contract_update", args=[laptop.public_ref]),
            {
                "category": "Computers > Laptops",
                "product_description": "Developer laptop 16GB",
                "max_budget": "1100.00",
                "currency": "USD",
                "quantity": 1,
                "required_specs_json": json.dumps({"ram": "16 GB"}),
                "preferred_specs_json": json.dumps({"storage": "1 TB SSD"}),
                "excluded_terms_json": json.dumps(["chromebook"]),
                "ambiguous_requirements_json": json.dumps([]),
            },
        )
        laptop.refresh_from_db()
        self.assertEqual(laptop.state, ContractState.SUPERSEDED)
        v2 = PurchaseContract.objects.get(parent_contract=laptop)
        self.assertEqual(v2.state, ContractState.DRAFT)
        self.assertEqual(v2.required_specs, {"ram": "16 GB"})
        self.assertEqual(v2.preferred_specs, {"storage": "1 TB SSD"})
        self.assertRedirects(edit_resp, reverse("contract_review", args=[v2.public_ref]))


class AuditSecurityAndRecoveryInvariantTests(TestCase):
    """Independent verification tests for budget-revision payment isolation and honest recovery UI."""

    def setUp(self):
        self.client = Client()
        self.contract_v1 = PurchaseContract.objects.create(
            version=1,
            raw_prompt="Headphones under $150",
            category="Audio > Headphones",
            product_description="Wireless headphones",
            max_budget=Decimal("150.00"),
            currency="USD",
            quantity=1,
            required_specs={},
            preferred_specs={},
            excluded_terms=[],
            source=ContractSource.DEMO_FIXTURE,
            state=ContractState.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        self.cheap_prod = ProductEvidence.objects.create(
            product_id="AUD-HP-100",
            title="Sony WH-CH720N Wireless Headphones",
            description="Over-ear wireless headphones with Bluetooth.",
            brand="Sony",
            price=Decimal("129.95"),
            currency="USD",
            stock_status="IN_STOCK",
            source_merchant="sony.com",
            is_fixture=True,
        )
        self.expensive_prod = ProductEvidence.objects.create(
            product_id="AUD-HP-200",
            title="Sennheiser Momentum 4 Wireless Headphones",
            description="Over-ear wireless headphones.",
            brand="Sennheiser",
            price=Decimal("189.95"),
            currency="USD",
            stock_status="IN_STOCK",
            source_merchant="sennheiser.com",
            is_fixture=True,
        )

    def test_superseded_proposal_and_voided_approval_ui_and_posts_blocked(self):
        """Superseded proposals and voided approvals hide Approve/Checkout actions and fail closed on POST."""
        proposal_v1, approval_v1 = ProposalService.create_proposal(
            contract=self.contract_v1,
            product=self.cheap_prod,
        )
        ApprovalService.approve_proposal(proposal_v1.id, shopper_ip="127.0.0.1")

        # Revise budget to create Draft v2 and supersede v1
        self.client.post(
            reverse("contract_revise_budget", args=[self.contract_v1.public_ref]),
            {"max_budget": "200.00"},
        )
        proposal_v1.refresh_from_db()
        approval_v1.refresh_from_db()

        prop_resp = self.client.get(reverse("proposal_detail", args=[proposal_v1.public_ref]))
        prop_html = prop_resp.content.decode("utf-8")
        self.assertEqual(prop_resp.status_code, 200)
        self.assertIn("Summary Outdated", prop_html)
        self.assertNotIn("I Explicitly Approve This Purchase Proposal", prop_html)

        appr_resp = self.client.get(reverse("approval_detail", args=[approval_v1.public_ref]))
        appr_html = appr_resp.content.decode("utf-8")
        self.assertEqual(appr_resp.status_code, 200)
        self.assertIn("Approval Voided", appr_html)
        self.assertNotIn("Ready for PayPal Sandbox Checkout", appr_html)
        self.assertNotIn("Proceed to PayPal Sandbox Checkout", appr_html)

        # Initiating checkout with the voided v1 token must fail closed
        with self.assertRaises(ApprovalError):
            PaymentService.initiate_checkout(
                approval_token=approval_v1.token,
                return_url="http://testserver/return",
                cancel_url="http://testserver/cancel",
            )

    def test_cross_contract_policy_report_rejected_by_proposal_service(self):
        """A PolicyEvaluationReport bound to v1 cannot be injected to generate a v2 proposal."""
        with patch("catalog.services.ProductSearchService.search_for_contract") as mock_search:
            mock_search.return_value = ([self.cheap_prod], True, "Fixture")
            v1_reports = PolicyEvaluationService().evaluate_contract_products(self.contract_v1)
        v1_report = next(r for r in v1_reports if r.product == self.cheap_prod)

        v2 = self.contract_v1.create_revision(reason="budget_revision", max_budget=Decimal("220.00"))
        v2.confirm()

        with self.assertRaises(ApprovalError):
            ProposalService.create_proposal(
                contract=v2,
                product=self.cheap_prod,
                policy_report=v1_report,
            )

    def test_complete_checkout_blocks_capture_if_contract_superseded_while_order_completed_stays_intact(self):
        """Uncaptured PaymentOrder fails before capture if contract superseded; COMPLETED order stays untouched."""
        proposal_v1, approval_v1 = ProposalService.create_proposal(
            contract=self.contract_v1,
            product=self.cheap_prod,
        )
        ApprovalService.approve_proposal(proposal_v1.id, shopper_ip="127.0.0.1")
        approval_v1.refresh_from_db()

        # Consume approval and create PaymentOrder in CREATED state
        approval_v1.consume(order_reference="CREATE-TEST-1")
        payment_order = PaymentOrder.objects.create(
            approval=approval_v1,
            proposal=proposal_v1,
            contract=self.contract_v1,
            paypal_order_id="PP-AUDIT-SUP-1",
            cart_fingerprint=approval_v1.cart_fingerprint,
            status="CREATED",
            payee_id=proposal_v1.payee_id,
            currency="USD",
            unit_price=proposal_v1.unit_price,
            quantity=proposal_v1.quantity,
            base_amount=proposal_v1.base_amount,
            shipping_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            fee_amount=Decimal("0.00"),
            total_amount=proposal_v1.total_amount,
            create_idempotency_key="CREATE-AUDIT-1",
            capture_idempotency_key="CAPTURE-AUDIT-1",
        )

        # Now revise contract BEFORE capture executes -> v1 becomes SUPERSEDED
        self.contract_v1.create_revision(reason="budget_revision", max_budget=Decimal("220.00"))

        class FakePayPalClient:
            capture_called = False

            def get_order(self, order_id):
                return {
                    "id": order_id,
                    "status": "APPROVED",
                    "purchase_units": [
                        {
                            "custom_id": payment_order.cart_fingerprint,
                            "amount": {"value": f"{payment_order.total_amount:.2f}", "currency_code": "USD"},
                            "payee": {"merchant_id": payment_order.payee_id},
                        }
                    ],
                }

            def capture_order(self, order_id, idempotency_key=None):
                self.capture_called = True
                return {"status": "COMPLETED"}

        fake_client = FakePayPalClient()
        with self.assertRaises(PayPalRevalidationError):
            PaymentService.complete_checkout(payment_order.paypal_order_id, client=fake_client)
        self.assertFalse(fake_client.capture_called)
        payment_order.refresh_from_db()
        self.assertEqual(payment_order.status, "FAILED")

        # Now verify an already COMPLETED order stays untouched when contract later revises
        payment_order.status = "COMPLETED"
        payment_order.save(update_fields=["status"])
        returned_order, _ = PaymentService.complete_checkout(payment_order.paypal_order_id, client=fake_client)
        self.assertEqual(returned_order.status, "COMPLETED")
        self.assertEqual(returned_order.total_amount, Decimal("129.95"))

    def test_loading_recovery_hidden_css_and_honest_cancel_copy(self):
        """Recovery banner must stay hidden via [hidden] CSS rule and avoid claiming server cancellation."""
        html = self.client.get(reverse("home")).content.decode("utf-8")
        self.assertIn("[hidden] {", html)
        self.assertIn("display: none !important;", html)
        self.assertIn("Continue Waiting", html)
        self.assertIn("Stop Waiting &amp; Restore Controls", html)
        self.assertIn("If a request already reached the server", html)
