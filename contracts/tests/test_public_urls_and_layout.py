"""
Regression tests for readable public_ref URLs, UUID 302 redirects, session
ownership enforcement (HTTP 403 before redirect), custom error pages,
header/wide-container structure, simplified confirmation cards, and
evaluation product images + fallback behavior.
"""

from decimal import Decimal
from unittest.mock import patch

from django.template.loader import render_to_string
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import ProductEvidence
from contracts.models import ContractState, PurchaseContract
from orders.models import PurchaseApproval, PurchaseProposal
from policies.models import PolicyEvaluationReport


class PublicRefGenerationAndSecurityTests(TestCase):
    def test_public_ref_uses_structured_category_never_raw_prompt_pii(self):
        contract = PurchaseContract.objects.create(
            raw_prompt="Order for Jane Doe jane.doe@example.com phone 555-867-5309 wireless headphones",
            category="Electronics > Audio > Headphones",
            product_description="Over-ear wireless headphones",
            max_budget=Decimal("150.00"),
            currency="USD",
            quantity=1,
            state=ContractState.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        self.assertRegex(contract.public_ref, r"^[a-z0-9-]+-PC-[A-Z0-9]{6}$")
        self.assertIn("headphones", contract.public_ref)
        for pii in ("jane", "doe", "example", "555", "867", "5309"):
            self.assertNotIn(pii, contract.public_ref.lower())

    def test_revision_gets_distinct_public_ref_and_preserves_session_owner(self):
        v1 = PurchaseContract.objects.create(
            raw_prompt="Mechanical keyboard under $100",
            category="Computers > Keyboards",
            product_description="TKL mechanical keyboard",
            max_budget=Decimal("100.00"),
            currency="USD",
            quantity=1,
            owner_session_key="sess-owner-123",
            state=ContractState.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        v2 = v1.create_revision(reason="budget_revision", max_budget=Decimal("130.00"))
        self.assertNotEqual(v1.public_ref, v2.public_ref)
        self.assertRegex(v2.public_ref, r"-PC-[A-Z0-9]{6}$")
        self.assertEqual(v2.owner_session_key, "sess-owner-123")

    def test_uuid_urls_redirect_302_preserving_query_for_owning_session(self):
        client = Client()
        create_resp = client.post(reverse("contract_create"), {"scenario_key": "headphones"})
        self.assertEqual(create_resp.status_code, 302)
        contract = PurchaseContract.objects.latest("created_at")
        self.assertTrue(contract.owner_session_key)

        # Confirm contract so discovery & evaluation routes don't redirect for DRAFT
        client.post(reverse("contract_confirm", args=[contract.public_ref]))

        prod = ProductEvidence.objects.create(
            product_id="PUBREF-HP-1",
            title="Sony WH-1000XM5 Wireless Headphones",
            description="Wireless ANC headphones",
            price=Decimal("140.00"),
            currency="USD",
            source_merchant="AudioShop",
            stock_status="IN_STOCK",
            image_url="https://cdn.example.com/sony-hp.jpg",
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )
        report = PolicyEvaluationReport.objects.create(
            contract=contract,
            product=prod,
            outcome="ELIGIBLE",
            summary="Eligible",
            unit_price=Decimal("140.00"),
            quantity=1,
            total_item_price=Decimal("140.00"),
            budget_ceiling=Decimal("150.00"),
            preference_score=95,
            currency="USD",
        )
        proposal = PurchaseProposal.objects.create(
            contract=contract,
            product=prod,
            policy_report=report,
            source_merchant="AudioShop",
            payee_id="PU7K3F65AAQ8U",
            quantity=1,
            unit_price=Decimal("140.00"),
            base_amount=Decimal("140.00"),
            shipping_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            fee_amount=Decimal("0.00"),
            total_amount=Decimal("140.00"),
            currency="USD",
            charges_confirmed=True,
            status="PROPOSED",
            cart_fingerprint="fp-pubref-test-1",
        )
        approval = PurchaseApproval.objects.create(
            token="tok_pubref_test_1",
            proposal=proposal,
            cart_fingerprint="fp-pubref-test-1",
            state="APPROVED",
            approved_at=timezone.now(),
        )
        self.assertRegex(proposal.public_ref, r"-PP-[A-Z0-9]{6}$")
        self.assertRegex(approval.public_ref, r"-PA-[A-Z0-9]{6}$")

        # Verify GET on legacy UUID routes redirects cleanly (302) with query string intact
        r1 = client.get(f"/contracts/{contract.id}/review/", follow=False)
        self.assertEqual(r1.status_code, 302)
        self.assertEqual(r1.url, reverse("contract_review", args=[contract.public_ref]))

        r2 = client.get(f"/contracts/{contract.id}/confirm/", follow=False)
        self.assertEqual(r2.status_code, 302)
        self.assertEqual(r2.url, reverse("contract_confirm", args=[contract.public_ref]))

        r3 = client.get(f"/contracts/{contract.id}/discovery/?refresh=1", follow=False)
        self.assertEqual(r3.status_code, 302)
        self.assertEqual(r3.url, f"{reverse('contract_discovery', args=[contract.public_ref])}?refresh=1")

        r4 = client.get(f"/contracts/{contract.id}/evaluation/?refresh=1", follow=False)
        self.assertEqual(r4.status_code, 302)
        self.assertEqual(r4.url, f"{reverse('contract_evaluation', args=[contract.public_ref])}?refresh=1")

        r5 = client.get(f"/orders/proposals/{proposal.id}/", follow=False)
        self.assertEqual(r5.status_code, 302)
        self.assertEqual(r5.url, reverse("proposal_detail", args=[proposal.public_ref]))

        r6 = client.get(f"/orders/approvals/{approval.id}/", follow=False)
        self.assertEqual(r6.status_code, 302)
        self.assertEqual(r6.url, reverse("approval_detail", args=[approval.public_ref]))

    def test_cross_session_access_blocked_403_before_uuid_redirect(self):
        owner = Client()
        attacker = Client()
        owner.post(reverse("contract_create"), {"scenario_key": "keyboard"})
        contract = PurchaseContract.objects.latest("created_at")
        owner.post(reverse("contract_confirm", args=[contract.public_ref]))

        prod = ProductEvidence.objects.create(
            product_id="PUBREF-KB-1",
            title="Keychron K2 Keyboard",
            description="TKL Keyboard",
            price=Decimal("89.00"),
            currency="USD",
            source_merchant="Keychron",
            stock_status="IN_STOCK",
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )
        report = PolicyEvaluationReport.objects.create(
            contract=contract,
            product=prod,
            outcome="ELIGIBLE",
            summary="Eligible",
            unit_price=Decimal("89.00"),
            quantity=1,
            total_item_price=Decimal("89.00"),
            budget_ceiling=Decimal("100.00"),
            preference_score=90,
            currency="USD",
        )
        proposal = PurchaseProposal.objects.create(
            contract=contract,
            product=prod,
            policy_report=report,
            source_merchant="Keychron",
            payee_id="PU7K3F65AAQ8U",
            quantity=1,
            unit_price=Decimal("89.00"),
            base_amount=Decimal("89.00"),
            shipping_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            fee_amount=Decimal("0.00"),
            total_amount=Decimal("89.00"),
            currency="USD",
            charges_confirmed=True,
            status="PROPOSED",
            cart_fingerprint="fp-kb-403",
        )

        # Ensure attacker session exists before cross-session checks
        attacker.get(reverse("home"))
        for url in (
            f"/contracts/{contract.public_ref}/review/",
            f"/contracts/{contract.id}/review/",
            f"/contracts/{contract.public_ref}/confirm/",
            f"/contracts/{contract.id}/confirm/",
            f"/contracts/{contract.public_ref}/discovery/",
            f"/contracts/{contract.id}/discovery/",
            f"/contracts/{contract.public_ref}/evaluation/",
            f"/contracts/{contract.id}/evaluation/",
            f"/orders/proposals/{proposal.public_ref}/",
            f"/orders/proposals/{proposal.id}/",
        ):
            resp = attacker.get(url, follow=False)
            self.assertEqual(resp.status_code, 403, f"Expected 403 on cross-session GET {url}, got {resp.status_code}")

        # Unknown references fail cleanly with 404
        self.assertEqual(attacker.get("/contracts/nonexistent-PC-999999/review/").status_code, 404)
        self.assertEqual(attacker.get("/orders/proposals/nonexistent-PP-999999/").status_code, 404)


class SimplifiedLayoutAndEvaluationTests(TestCase):
    def test_header_wide_container_and_error_templates(self):
        html = self.client.get(reverse("home")).content.decode("utf-8")
        self.assertIn("max-width: 1560px;", html)
        self.assertNotIn('href="/health/"', html)
        self.assertNotIn("tc-stage-bar", html.split("</style>")[1])
        self.assertIn("Sandbox", html)

        err403 = render_to_string("403.html", {})
        self.assertIn("This shopping session cannot be opened here", err403)
        self.assertIn("Return to Search", err403)

        err404 = render_to_string("404.html", {})
        self.assertIn("Page not found", err404)
        self.assertIn("Start New Shopping Search", err404)
        self.assertIn("Go Back", err404)

    def test_confirmed_page_hierarchy_and_evaluation_images_and_price_rendering(self):
        client = Client()
        apparel_contract = PurchaseContract.objects.create(
            raw_prompt="Men's black joggers under $45",
            category="Apparel > Men's Clothing > Pants",
            product_description="Men's slim black joggers",
            max_budget=Decimal("45.00"),
            currency="USD",
            quantity=2,
            state=ContractState.DRAFT,
        )

        # Confirm via POST -> checks clean unnumbered headings, NO Additional options, NO SHA-256
        confirm_resp = client.post(reverse("contract_confirm", args=[apparel_contract.public_ref]))
        self.assertEqual(confirm_resp.status_code, 200)
        confirm_html = confirm_resp.content.decode("utf-8")
        for heading in (
            "Shopping request",
            "Budget and quantity",
            "Important purchase information",
            "Confirmation and payment",
        ):
            self.assertIn(heading, confirm_html)
        for numbered_heading in ("1. Your shopping request", "2. Budget and quantity", "5. Confirmation and payment"):
            self.assertNotIn(numbered_heading, confirm_html)
        self.assertNotIn("tc-stage-bar", confirm_html.split("</style>")[1])
        self.assertNotIn("Additional options", confirm_html)
        self.assertNotIn("IMMUTABLE BINDING", confirm_html)
        self.assertNotIn("SHA-256", confirm_html)
        self.assertIn("Shipping and tax are currently unconfirmed.", confirm_html)

        # Evaluation page with one imaged product and one imageless fallback product
        apparel_contract.refresh_from_db()
        p_with_img = ProductEvidence.objects.create(
            product_id="JOG-IMG-1",
            title="Nike Black Joggers",
            description="Comfortable slim joggers",
            price=Decimal("20.00"),
            currency="USD",
            source_merchant="Nike",
            stock_status="IN_STOCK",
            image_url="https://cdn.example.com/joggers.jpg",
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )
        p_no_img = ProductEvidence.objects.create(
            product_id="JOG-NOIMG-2",
            title="Plain Fleece Joggers",
            description="Everyday cotton joggers",
            price=Decimal("18.50"),
            currency="USD",
            source_merchant="BasicsShop",
            stock_status="IN_STOCK",
            image_url="",
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )

        with patch("catalog.services.ProductSearchService.search_for_contract") as mock_search:
            mock_search.return_value = ([p_with_img, p_no_img], True, "Fixture")
            eval_resp = client.get(reverse("contract_evaluation", args=[apparel_contract.public_ref]))
            self.assertEqual(eval_resp.status_code, 200)
            eval_html = eval_resp.content.decode("utf-8")

        self.assertIn("Results for your request", eval_html)
        self.assertNotIn("tc-stage-bar", eval_html.split("</style>")[1])
        # Verify literal template typo `${ report.unit_price }}` is gone and real unit price renders cleanly
        self.assertNotIn("${ report.unit_price }}", eval_html)
        self.assertIn("($20.00 &times; 2 units)", eval_html)
        self.assertIn("https://cdn.example.com/joggers.jpg", eval_html)
        self.assertIn("tc-eval-media-apparel", eval_html)
        self.assertIn("Product image unavailable", eval_html)
        self.assertIn("View check details", eval_html)
        self.assertIn('<span class="visually-hidden">for Nike Black Joggers</span>', eval_html)

    def test_accessibility_remediations_across_shared_and_flow_pages(self):
        client = Client()
        c = PurchaseContract.objects.create(
            raw_prompt="Black wireless headphones under $150",
            category="Electronics > Audio > Headphones",
            product_description="Wireless ANC headphones",
            max_budget=Decimal("150.00"),
            currency="USD",
            quantity=1,
            ambiguous_requirements=["battery life"],
            state=ContractState.DRAFT,
        )
        # 1. Nav landmark & skip-link & scroll-padding-top
        rev_html = client.get(reverse("contract_review", args=[c.public_ref])).content.decode("utf-8")
        self.assertIn('aria-label="Primary"', rev_html)
        self.assertNotIn('aria-label="Main Navigation"', rev_html)
        self.assertIn("scroll-padding-top: 84px;", rev_html)
        self.assertIn('id="clarify_req_battery_life"', rev_html)
        self.assertIn('<label for="clarify_req_battery_life"', rev_html)

        # 2. Discovery single H1, disambiguated Merchant links, zero "Additional options"
        client.post(reverse("contract_confirm", args=[c.public_ref]))
        p = ProductEvidence.objects.create(
            product_id="ACC-DISC-1",
            title="Acoustic ANC Headphones",
            description="Wireless ANC headphones",
            price=Decimal("99.00"),
            currency="USD",
            source_merchant="AudioMerchant",
            product_url="https://example.com/acoustic",
            stock_status="IN_STOCK",
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )
        with patch("catalog.services.ProductSearchService.search_for_contract") as mock_search:
            mock_search.return_value = ([p], True, "Fixture")
            disc_html = client.get(reverse("contract_discovery", args=[c.public_ref])).content.decode("utf-8")
        self.assertEqual(disc_html.count("<h1"), 1)
        self.assertIn("Product details &amp; listing info", disc_html)
        self.assertNotIn("Additional options", disc_html)
        self.assertIn('Merchant site <span class="visually-hidden">for Acoustic ANC Headphones', disc_html)

