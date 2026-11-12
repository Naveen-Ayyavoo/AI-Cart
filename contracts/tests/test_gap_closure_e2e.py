"""
Comprehensive end-to-end regression suite for Remaining UX & Shopping Journey Gap Closure:
1. Product identity (iPhone 17 Pro Max vs Case / Accessory / Replacement Part, Buy Anyway block)
2. Discovery layout classification, no unearned badges on incompatible items, 2-col desktop grid, single Edit Criteria
3. Action button alignment across Review, Confirmation, Discovery, Purchase Summary, and Receipt
4. Channel3 loading feedback metadata
5. Direct product selection from Discovery to Purchase Summary
6. Session-scoped Payment History (completed, pending, failed, cancelled, refunded; ownership isolation)
7. Revision notice consolidation, PayPal return URL parameter cleanup, shipping/tax/total capture verification
8. No journey indicator / breadcrumbs / numbered strip
9. Full E2E offline journey from shopper request -> receipt -> payment history ($0.00 spend)
"""

from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import ProductEvidence
from contracts.models import ContractSource, ContractState, PurchaseContract
from orders.models import DEFAULT_DEMO_PAYEE_ID, PurchaseApproval, PurchaseProposal
from payments.models import PaymentCaptureRecord, PaymentOrder
from policies.engine import PolicyEngine


class ProductIdentityAndIncompatibleBlockingTests(TestCase):
    """Req 1 & 2: Accessories, cases, covers, and parts never qualify as main devices or bypass via Buy Anyway."""

    def setUp(self):
        self.iphone_contract = PurchaseContract.objects.create(
            raw_prompt="iphone 17 pro max refurbished under 1000$",
            category="Electronics > Smartphones",
            product_description="iPhone 17 Pro Max Refurbished",
            max_budget=Decimal("1000.00"),
            currency="USD",
            quantity=1,
            required_specs={},
            preferred_specs={"condition": "Refurbished"},
            excluded_terms=[],
            source=ContractSource.FALLBACK_PARSER,
            state=ContractState.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        self.real_iphone = ProductEvidence.objects.create(
            product_id="IPHONE-17-PM-REAL",
            brand="Apple",
            title="Apple iPhone 17 Pro Max 256GB (Refurbished) - Unlocked",
            description="Genuine Apple iPhone 17 Pro Max Grade-A refurbished smartphone, unlocked.",
            price=Decimal("949.00"),
            currency="USD",
            source_merchant="RefurbMobile",
            stock_status="IN_STOCK",
            raw_evidence={"features": {"condition": "Refurbished", "storage": "256 GB"}},
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )
        self.iphone_case = ProductEvidence.objects.create(
            product_id="IPHONE-17-PM-CASE",
            brand="Spigen",
            title="Spigen Ultra Hybrid MagFit Case for iPhone 17 Pro Max",
            description="Clear protective bumper case cover designed for iPhone 17 Pro Max.",
            price=Decimal("24.99"),
            currency="USD",
            source_merchant="AccessoryWorld",
            stock_status="IN_STOCK",
            raw_evidence={"features": {"condition": "Refurbished", "color": "Clear"}},
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )
        self.screen_part = ProductEvidence.objects.create(
            product_id="IPHONE-17-PM-SCREEN",
            brand="RepairParts",
            title="OLED Replacement Screen Digitizer Assembly for iPhone 17 Pro Max",
            description="Replacement display part for broken iPhone 17 Pro Max phones.",
            price=Decimal("189.00"),
            currency="USD",
            source_merchant="FixSupply",
            stock_status="IN_STOCK",
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )
        self.protector = ProductEvidence.objects.create(
            product_id="IPHONE-17-PM-GLASS",
            brand="amFilm",
            title="Tempered Glass Screen Protector (3-Pack) for iPhone 17 Pro Max",
            description="Scratch-resistant glass screen protector cover.",
            price=Decimal("12.99"),
            currency="USD",
            source_merchant="AccessoryWorld",
            stock_status="IN_STOCK",
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )
        self.headphones = ProductEvidence.objects.create(
            product_id="AUDIO-WH-CROSS",
            brand="Sony",
            title="Sony WH-1000XM5 Wireless Headphones",
            description="Over-ear Bluetooth headphones.",
            price=Decimal("299.00"),
            currency="USD",
            source_merchant="AudioShop",
            stock_status="IN_STOCK",
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )
        self.over_budget_iphone = ProductEvidence.objects.create(
            product_id="IPHONE-17-PM-OVER",
            brand="Apple",
            title="Apple iPhone 17 Pro Max 1TB Smartphone",
            description="Factory unlocked iPhone 17 Pro Max smartphone.",
            price=Decimal("1299.00"),
            currency="USD",
            source_merchant="PhoneStore",
            stock_status="IN_STOCK",
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )

    def test_case_protector_part_and_cross_category_fail_category_compatibility(self):
        engine = PolicyEngine()
        res_real = engine.evaluate(self.iphone_contract, self.real_iphone)
        self.assertEqual(res_real.outcome, "ELIGIBLE")

        for bad_item in (self.iphone_case, self.screen_part, self.protector, self.headphones):
            with self.subTest(product=bad_item.product_id):
                res = engine.evaluate(self.iphone_contract, bad_item)
                self.assertEqual(res.outcome, "INELIGIBLE")
                cat_rules = [r for r in res.rule_results if r.rule_name == "CategoryCompatibility"]
                self.assertEqual(len(cat_rules), 1)
                self.assertEqual(cat_rules[0].outcome, "FAIL")

    def test_explicit_case_request_still_allows_case_product(self):
        case_contract = PurchaseContract.objects.create(
            raw_prompt="clear iphone 17 pro max case under $40",
            category="Electronics > Phone Accessories",
            product_description="Clear iPhone 17 Pro Max Case",
            max_budget=Decimal("40.00"),
            currency="USD",
            quantity=1,
            state=ContractState.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        res = PolicyEngine().evaluate(case_contract, self.iphone_case)
        self.assertEqual(res.outcome, "ELIGIBLE")

    def test_discovery_segregates_sections_blocks_case_badges_and_buy_anyway(self):
        with patch("catalog.services.ProductSearchService.search_for_contract") as mock_search:
            mock_search.return_value = (
                [self.iphone_case, self.protector, self.over_budget_iphone, self.real_iphone],
                True,
                "Fixture",
            )
            resp = self.client.get(reverse("contract_discovery", args=[self.iphone_contract.public_ref]))
            self.assertEqual(resp.status_code, 200)
            html = resp.content.decode("utf-8")

        # Real iPhone is in eligible shortlist with awards; case is incompatible & NOT awarded badges
        eligible_shortlist = resp.context["shortlist_items"]
        self.assertEqual([it["product"].product_id for it in eligible_shortlist], ["IPHONE-17-PM-REAL"])
        self.assertIn("Lowest Item Subtotal", eligible_shortlist[0]["distinctions"])

        for it in resp.context["decorated_items"]:
            if it["product"].product_id in ("IPHONE-17-PM-CASE", "IPHONE-17-PM-GLASS"):
                self.assertFalse(it["is_eligible"])
                self.assertFalse(it["is_compatible"])
                self.assertFalse(it["can_buy_anyway"])
                self.assertEqual(it["distinctions"], ["Incompatible"])
                self.assertNotIn("Lowest Item Subtotal", it["distinctions"])
                self.assertNotIn("Best Preference Match", it["distinctions"])

        # Section separation, single Edit Criteria, no Buy Anyway on case, disabled Incompatible Product
        eligible_sec = html.split('id="eligible-matches-section"')[1].split('id="needs-review-section"')[0]
        self.assertIn("Apple iPhone 17 Pro Max 256GB", eligible_sec)
        self.assertNotIn("Spigen Ultra Hybrid", eligible_sec)

        review_sec = html.split('id="needs-review-section"')[1].split('id="more-results-details"')[0]
        self.assertIn("Apple iPhone 17 Pro Max 1TB Smartphone", review_sec)

        more_sec = html.split('id="more-results-details"')[1]
        self.assertIn("Spigen Ultra Hybrid MagFit Case", more_sec)
        self.assertIn("Incompatible Product", more_sec)
        self.assertNotIn(reverse("contract_buy_anyway", args=[self.iphone_contract.public_ref, "IPHONE-17-PM-CASE"]), html)

        # Single Edit Criteria action on Discovery
        self.assertEqual(html.count("Edit Criteria"), 1)
        self.assertNotIn("Refine Criteria", html)

        # Direct Buy Anyway POST on iPhone case MUST fail closed without creating any revision
        ba_resp = self.client.post(
            reverse("contract_buy_anyway", args=[self.iphone_contract.public_ref, "IPHONE-17-PM-CASE"]),
            {"acknowledge_risk": "on", "acknowledge_revision": "on"},
            follow=True,
        )
        self.assertEqual(PurchaseContract.objects.count(), 1)
        self.assertIn("cannot proceed", ba_resp.content.decode("utf-8").lower())


class NavigationButtonAlignmentAndSelectionTests(TestCase):
    """Req 2, 3, 4, 5, 8: No journey strip, consistent right alignment, Channel3 loading attrs, direct Select."""

    def setUp(self):
        self.contract = PurchaseContract.objects.create(
            raw_prompt="Bluetooth headphones under $150",
            category="Electronics > Audio > Headphones",
            product_description="Wireless headphones",
            max_budget=Decimal("150.00"),
            currency="USD",
            quantity=1,
            required_specs={"connectivity": "Bluetooth"},
            state=ContractState.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        self.prod = ProductEvidence.objects.create(
            product_id="SEL-DIRECT-1",
            brand="Soundcore",
            title="Soundcore Q30 Bluetooth Wireless Headphones",
            description="Wireless Bluetooth headphones.",
            price=Decimal("79.99"),
            currency="USD",
            source_merchant="Anker",
            stock_status="IN_STOCK",
            raw_evidence={"features": {"connectivity": "Bluetooth"}},
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )

    def test_no_journey_indicator_and_proper_action_ordering(self):
        # Confirmed page: no journey indicator, Edit Requirements BEFORE Find Matching Products, Channel3 loading attrs
        conf_html = self.client.get(reverse("contract_confirm", args=[self.contract.public_ref])).content.decode("utf-8")
        self.assertNotIn("tc-journey-indicator", conf_html)
        self.assertNotIn("tc-stage-bar", conf_html.split("</style>")[1])
        self.assertLess(conf_html.index("Edit Requirements"), conf_html.index("Find Matching Products"))
        self.assertIn("Searching Channel3&#x27;s product catalogue", conf_html.replace("'", "&#x27;")) if "&#x27;" in conf_html else self.assertIn("Searching Channel3's product catalogue", conf_html)

        # Discovery page CSS 3-column desktop, 2-column tablet/narrow desktop & 1-column mobile
        with patch("catalog.services.ProductSearchService.search_for_contract") as mock_search:
            mock_search.return_value = ([self.prod], True, "Fixture")
            disc_html = self.client.get(reverse("contract_discovery", args=[self.contract.public_ref])).content.decode("utf-8")
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr));", disc_html)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", disc_html)
        self.assertNotIn("tc-journey-indicator", disc_html)
        self.assertIn(reverse("contract_select_product", args=[self.contract.public_ref, "SEL-DIRECT-1"]), disc_html)

        # Review page: side-by-side Required & Preferred specs cards (not tc-brief-cell-full) + empty pref message
        rev_html = self.client.get(reverse("contract_review", args=[self.contract.public_ref])).content.decode("utf-8")
        req_chunk = rev_html.split("Required Specifications (Must-Have)")[0][-80:]
        pref_chunk = rev_html.split("Preferred Specifications (Optional)")[0][-80:]
        self.assertNotIn("tc-brief-cell-full", req_chunk)
        self.assertNotIn("tc-brief-cell-full", pref_chunk)
        self.assertIn("No optional preferences set yet.", rev_html)

        # Approval detail ("Purchase Summary Approved"): secondary Back to Results precedes right-aligned PayPal button
        sel_resp = self.client.post(reverse("contract_select_product", args=[self.contract.public_ref, "SEL-DIRECT-1"]))
        proposal = PurchaseProposal.objects.get(contract=self.contract, product=self.prod)
        self.assertRedirects(sel_resp, reverse("proposal_detail", args=[proposal.public_ref]))
        app_resp = self.client.post(reverse("proposal_detail", args=[proposal.public_ref]), {"action": "approve"})
        approval = proposal.approval
        self.assertRedirects(app_resp, reverse("approval_detail", args=[approval.public_ref]))
        app_html = self.client.get(reverse("approval_detail", args=[approval.public_ref])).content.decode("utf-8")
        self.assertIn("Purchase Summary Approved", app_html)
        self.assertIn('class="tc-approval-actions"', app_html)
        actions_area = app_html.split('class="tc-approval-actions"')[1].split("</div>")[0]
        self.assertLess(actions_area.index("Back to Results"), actions_area.index("Proceed to PayPal Sandbox Checkout"))
        # Rendering GET never triggers PaymentOrder creation
        self.assertEqual(PaymentOrder.objects.count(), 0)

        # Review page: consolidated single revision banner (zero redundant toast), Edit Criteria before Confirm
        v2_resp = self.client.post(
            reverse("contract_revise_budget", args=[self.contract.public_ref]),
            {"max_budget": "180.00"},
            follow=True,
        )
        v2_html = v2_resp.content.decode("utf-8")
        self.assertNotIn("tc-journey-indicator", v2_html)
        self.assertEqual(v2_html.count('id="revision-diff-banner"'), 1)
        self.assertNotIn('id="buy-anyway-audit-banner"', v2_html)
        self.assertLess(v2_html.index('id="toggle-edit-btn"'), v2_html.index('id="confirm-criteria-btn"'))

    def test_select_this_product_goes_directly_to_purchase_summary(self):
        resp = self.client.post(
            reverse("contract_select_product", args=[self.contract.public_ref, "SEL-DIRECT-1"]),
        )
        proposal = PurchaseProposal.objects.get(contract=self.contract, product=self.prod)
        # Directly redirects to Purchase Summary (proposal_detail), NOT evaluation
        self.assertRedirects(resp, reverse("proposal_detail", args=[proposal.public_ref]))
        self.assertNotIn("/evaluation/", resp.url)
        # Deterministic backend evaluation report persisted cleanly
        self.assertIsNotNone(proposal.policy_report)
        self.assertEqual(proposal.policy_report.outcome, "ELIGIBLE")


class PaymentHistoryReturnAndE2EJourneyTests(TestCase):
    """Req 6, 7, 9: Payment History session isolation, statuses, URL cleanup, receipt verification, full E2E flow."""

    def test_payment_history_isolation_empty_and_distinct_statuses(self):
        client_a = Client()
        client_b = Client()

        # Empty session history never fabricates fake transactions
        empty_resp = client_a.get(reverse("payments:history"))
        self.assertEqual(empty_resp.status_code, 200)
        self.assertIn("No transactions found", empty_resp.content.decode("utf-8"))

        # Touch home in both sessions so each has a real distinct Django session key
        client_a.get(reverse("home"))
        client_b.get(reverse("home"))
        sess_a = client_a.session.session_key
        sess_b = client_b.session.session_key
        self.assertNotEqual(sess_a, sess_b)

        c_a = PurchaseContract.objects.create(
            raw_prompt="iPhone under $1000",
            category="Electronics > Smartphones",
            product_description="iPhone 17 Pro Max",
            max_budget=Decimal("1000.00"),
            owner_session_key=sess_a,
            state=ContractState.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        c_b = PurchaseContract.objects.create(
            raw_prompt="Private Client B request",
            category="Electronics",
            product_description="Secret Laptop",
            max_budget=Decimal("900.00"),
            owner_session_key=sess_b,
            state=ContractState.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        prod_a = ProductEvidence.objects.create(
            product_id="HIST-A",
            title="Apple iPhone 17 Pro Max 256GB",
            price=Decimal("949.00"),
            currency="USD",
            source_merchant="RefurbMobile",
            stock_status="IN_STOCK",
            retrieval_timestamp=timezone.now(),
        )
        prod_b = ProductEvidence.objects.create(
            product_id="HIST-B",
            title="Secret Client B Laptop",
            price=Decimal("850.00"),
            currency="USD",
            source_merchant="LaptopWorld",
            stock_status="IN_STOCK",
            retrieval_timestamp=timezone.now(),
        )

        def make_order(contract, product, status, suffix):
            prop = PurchaseProposal.objects.create(
                contract=contract,
                product=product,
                source_merchant=product.source_merchant,
                payee_id=DEFAULT_DEMO_PAYEE_ID,
                quantity=1,
                unit_price=product.price,
                base_amount=product.price,
                total_amount=product.price,
                currency="USD",
                status="APPROVED",
                cart_fingerprint=f"fp-{suffix}",
            )
            appr = PurchaseApproval.objects.create(
                token=f"tok-{suffix}",
                proposal=prop,
                cart_fingerprint=f"fp-{suffix}",
                state="CONSUMED",
            )
            return PaymentOrder.objects.create(
                approval=appr,
                proposal=prop,
                contract=contract,
                paypal_order_id=f"PP-HIST-{suffix}",
                cart_fingerprint=f"fp-{suffix}",
                status=status,
                payee_id=DEFAULT_DEMO_PAYEE_ID,
                currency="USD",
                unit_price=product.price,
                quantity=1,
                base_amount=product.price,
                total_amount=product.price,
                create_idempotency_key=f"C-{suffix}",
                capture_idempotency_key=f"K-{suffix}",
            )

        o_comp = make_order(c_a, prod_a, "COMPLETED", "COMP")
        PaymentCaptureRecord.objects.create(
            order=o_comp,
            capture_id="CAP-HIST-COMP",
            status="COMPLETED",
            amount=Decimal("949.00"),
            currency="USD",
            raw_response={"amount": {"value": "949.00", "currency_code": "USD"}},
        )
        make_order(c_a, prod_a, "PENDING_RECONCILIATION", "PEND")
        make_order(c_a, prod_a, "FAILED", "FAIL")
        make_order(c_a, prod_a, "CANCELLED", "CANC")
        make_order(c_a, prod_a, "REFUNDED", "REF")
        make_order(c_b, prod_b, "COMPLETED", "OTHER-B")

        hist_html = client_a.get(reverse("payments:history")).content.decode("utf-8")
        for expected in (
            "Apple iPhone 17 Pro Max 256GB",
            "$949.00 USD",
            "Completed",
            "Pending Reconciliation",
            "Failed",
            "Cancelled",
            "Refunded",
            "View Receipt",
            "View Details",
        ):
            self.assertIn(expected, hist_html)
        # Never leak another session's order
        self.assertNotIn("Secret Client B Laptop", hist_html)
        self.assertNotIn("PP-HIST-OTHER-B", hist_html)

        # Receipt page: reconciliation verified, Back to Product Results label, primary on right
        rec_html = client_a.get(reverse("payments:order_detail", args=["PP-HIST-COMP"])).content.decode("utf-8")
        self.assertIn("Totals Reconciled:", rec_html)
        self.assertIn("$949.00 USD", rec_html)
        self.assertIn("Back to Product Results", rec_html)
        self.assertNotIn("View Checked Results", rec_html)
        self.assertLess(rec_html.index("Back to Product Results"), rec_html.index("Start New Search"))

    @patch.dict("os.environ", {"GEMINI_API_KEY": ""})
    @patch("payments.services.PayPalClient")
    @patch("catalog.services.ProductSearchService.search_for_contract")
    def test_full_e2e_shopper_request_to_receipt_and_history(self, mock_search, mock_paypal_cls):
        """Full journey: prompt -> fallback review -> confirm -> discovery -> direct select -> approve -> PayPal return -> receipt -> history."""
        iphone = ProductEvidence.objects.create(
            product_id="E2E-IPHONE-17",
            brand="Apple",
            title="Apple iPhone 17 Pro Max 256GB Refurbished",
            description="Unlocked refurbished Apple iPhone 17 Pro Max smartphone.",
            price=Decimal("949.00"),
            currency="USD",
            source_merchant="RefurbMobile",
            stock_status="IN_STOCK",
            raw_evidence={"features": {"condition": "Refurbished"}},
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )
        case = ProductEvidence.objects.create(
            product_id="E2E-CASE-17",
            brand="Spigen",
            title="iPhone 17 Pro Max Protective Case",
            description="Silicone phone case for iPhone 17 Pro Max.",
            price=Decimal("25.00"),
            currency="USD",
            source_merchant="AccessoryWorld",
            stock_status="IN_STOCK",
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )
        mock_search.return_value = ([case, iphone], True, "Using local test products")

        mock_client = mock_paypal_cls.return_value
        mock_client.create_order.return_value = {
            "id": "PP-E2E-IPHONE-01",
            "status": "CREATED",
            "links": [{"rel": "approve", "href": "https://www.sandbox.paypal.com/checkoutnow?token=PP-E2E-IPHONE-01"}],
        }

        client = Client()
        # 1. Submit shopper request offline
        create_resp = client.post(reverse("contract_create"), {"prompt": "iphone 17 pro max refurbished under 1000$"})
        contract = PurchaseContract.objects.order_by("-created_at").first()
        self.assertRedirects(create_resp, reverse("contract_review", args=[contract.public_ref]))

        # 2. Confirm requirements
        conf_resp = client.post(reverse("contract_confirm", args=[contract.public_ref]))
        self.assertEqual(conf_resp.status_code, 200)

        # 3. Discovery segregates iPhone case cleanly & ranks iPhone eligible
        disc_resp = client.get(reverse("contract_discovery", args=[contract.public_ref]))
        self.assertEqual([it["product"].product_id for it in disc_resp.context["shortlist_items"]], ["E2E-IPHONE-17"])

        # 4. Click "Select This Product" -> directly lands on Purchase Summary (NOT /evaluation/)
        sel_resp = client.post(reverse("contract_select_product", args=[contract.public_ref, "E2E-IPHONE-17"]))
        proposal = PurchaseProposal.objects.get(contract=contract, product=iphone)
        self.assertRedirects(sel_resp, reverse("proposal_detail", args=[proposal.public_ref]))

        # 5. Explicitly approve proposal -> Checkout approval page
        app_resp = client.post(reverse("proposal_detail", args=[proposal.public_ref]), {"action": "approve"})
        approval = proposal.approval
        self.assertRedirects(app_resp, reverse("approval_detail", args=[approval.public_ref]))

        # 6. Initiate PayPal Sandbox checkout -> redirect to sandbox
        init_resp = client.post(reverse("payments:checkout_initiate", args=[approval.token]))
        self.assertEqual(init_resp.status_code, 302)
        self.assertIn("sandbox.paypal.com", init_resp.url)

        order = PaymentOrder.objects.get(paypal_order_id="PP-E2E-IPHONE-01")
        mock_client.get_order.return_value = {
            "id": "PP-E2E-IPHONE-01",
            "status": "APPROVED",
            "purchase_units": [
                {
                    "amount": {"value": "949.00", "currency_code": "USD"},
                    "payee": {"merchant_id": DEFAULT_DEMO_PAYEE_ID},
                    "custom_id": order.cart_fingerprint,
                }
            ],
        }
        mock_client.capture_order.return_value = {
            "id": "PP-E2E-IPHONE-01",
            "status": "COMPLETED",
            "purchase_units": [
                {
                    "payments": {
                        "captures": [
                            {
                                "id": "CAP-E2E-IPHONE-01",
                                "status": "COMPLETED",
                                "amount": {"value": "949.00", "currency_code": "USD"},
                            }
                        ]
                    }
                }
            ],
        }

        # 7. PayPal return callback -> strips query parameters cleanly & lands on Receipt
        ret_resp = client.get(
            reverse("payments:checkout_return") + "?token=PP-E2E-IPHONE-01&PayerID=BUYER123",
            follow=True,
        )
        self.assertRedirects(ret_resp, reverse("payments:order_detail", args=["PP-E2E-IPHONE-01"]))
        ret_html = ret_resp.content.decode("utf-8")
        self.assertIn("Order Receipt", ret_html)
        self.assertIn("Totals Reconciled:", ret_html)
        self.assertIn("Back to Product Results", ret_html)

        # 8. Payment History lists completed transaction with receipt link
        hist_html = client.get(reverse("payments:history")).content.decode("utf-8")
        self.assertIn("Apple iPhone 17 Pro Max 256GB Refurbished", hist_html)
        self.assertIn("$949.00 USD", hist_html)
        self.assertIn("Completed", hist_html)
        self.assertIn(reverse("payments:order_detail", args=["PP-E2E-IPHONE-01"]), hist_html)

