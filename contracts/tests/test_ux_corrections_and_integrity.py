"""
Regression tests for Review, Discovery, Confirmation & Home UX Corrections
plus Request-to-Contract Integrity and Safe Buy Anyway invariants.
"""

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import ProductEvidence
from contracts.fixtures import get_demo_scenario
from contracts.interpreter import (
    detect_contract_contradictions,
    format_spec_label,
    format_spec_value,
)
from contracts.models import ContractSource, ContractState, PurchaseContract
from orders.models import PurchaseApproval, PurchaseProposal


class RequestToContractIntegrityTests(TestCase):
    """P0: Failed/unavailable AI interpretation must NEVER load unrelated demo contracts."""

    @patch.dict("os.environ", {"GEMINI_API_KEY": ""})
    def test_iphone_prompt_fallback_preserves_request_never_headphones(self):
        prompt = "iphone 17 pro max refurbished under 1000$"
        resp = self.client.post(reverse("contract_create"), {"prompt": prompt})
        contract = PurchaseContract.objects.order_by("-created_at").first()
        self.assertIsNotNone(contract)
        self.assertRedirects(resp, reverse("contract_review", args=[contract.public_ref]))

        self.assertEqual(contract.raw_prompt, prompt)
        self.assertEqual(contract.source, ContractSource.FALLBACK_PARSER)
        self.assertEqual(contract.category, "Electronics > Smartphones")
        self.assertEqual(contract.max_budget, Decimal("1000.00"))
        self.assertEqual(contract.preferred_specs.get("condition"), "Refurbished")
        self.assertEqual(contract.excluded_terms, [])
        self.assertNotIn("Headphones", contract.category)
        self.assertNotIn("Headphones", contract.product_description)
        self.assertNotIn("refurbished", [t.lower() for t in contract.excluded_terms])

        review_resp = self.client.get(reverse("contract_review", args=[contract.public_ref]))
        html = review_resp.content.decode("utf-8")
        # Single clear fallback banner, zero duplicate Django warning banner, Retry button present
        self.assertEqual(html.count('id="parse-fallback-banner"'), 1)
        self.assertNotIn('id="demo-sample-banner"', html)
        self.assertIn("Retry AI Interpretation", html)
        self.assertNotIn("New Search</span>", html)  # no duplicate intro button
        # Category-specific optional details should be Smartphones (Storage, Carrier lock), NEVER Headphones
        self.assertIn("Storage capacity", html)
        self.assertIn("Carrier lock status", html)
        self.assertNotIn("Headphone Design", html)
        self.assertNotIn("Noise Cancellation", html)

    @patch("urllib.request.urlopen")
    def test_429_and_malformed_json_preserve_request_not_headphones_demo(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"{not-valid-json"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with patch.dict("os.environ", {"GEMINI_API_KEY": "fake_test_key"}):
            resp = self.client.post(
                reverse("contract_create"),
                {"prompt": "iphone 17 pro max refurbished under 1000$"},
            )
            self.assertEqual(resp.status_code, 302)

        contract = PurchaseContract.objects.order_by("-created_at").first()
        self.assertEqual(contract.source, ContractSource.FALLBACK_PARSER)
        self.assertEqual(contract.max_budget, Decimal("1000.00"))
        self.assertEqual(contract.category, "Electronics > Smartphones")

    def test_contradiction_blocks_confirmation_until_resolved(self):
        contradicting = PurchaseContract.objects.create(
            raw_prompt="iphone 17 pro max refurbished under 1000$",
            category="Electronics > Smartphones",
            product_description="iphone 17 pro max refurbished under 1000$",
            max_budget=Decimal("1000.00"),
            currency="USD",
            quantity=1,
            required_specs={"condition": "Refurbished"},
            excluded_terms=["refurbished"],
            source=ContractSource.FALLBACK_PARSER,
            state=ContractState.DRAFT,
        )
        issues = detect_contract_contradictions(contradicting)
        self.assertTrue(issues)

        with self.assertRaises(ValidationError):
            contradicting.confirm()

        rev_html = self.client.get(reverse("contract_review", args=[contradicting.public_ref])).content.decode("utf-8")
        self.assertIn('id="contract-contradictions-banner"', rev_html)
        self.assertIn('id="confirm-criteria-btn"', rev_html)
        self.assertIn("disabled", rev_html.split('id="confirm-criteria-btn"')[1][:120])

        # POST confirm fails closed and redirects back cleanly
        conf_post = self.client.post(reverse("contract_confirm", args=[contradicting.public_ref]))
        self.assertRedirects(conf_post, reverse("contract_review", args=[contradicting.public_ref]))
        contradicting.refresh_from_db()
        self.assertEqual(contradicting.state, ContractState.DRAFT)

    def test_retry_parse_updates_fallback_draft_when_gemini_recovers(self):
        draft = PurchaseContract.objects.create(
            raw_prompt="iphone 17 pro max refurbished under 1000$",
            category="Electronics > Smartphones",
            product_description="iphone 17 pro max refurbished under 1000$",
            max_budget=Decimal("1000.00"),
            currency="USD",
            quantity=1,
            source=ContractSource.FALLBACK_PARSER,
            state=ContractState.DRAFT,
        )
        live_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "category": "Electronics > Smartphones",
                                        "product_description": "Refurbished Apple iPhone 17 Pro Max unlocked smartphone",
                                        "max_budget": "1000.00",
                                        "currency": "USD",
                                        "quantity": 1,
                                        "required_specs": {"condition": "Refurbished"},
                                        "preferred_specs": {"storage_capacity": "256GB"},
                                        "excluded_terms": [],
                                        "ambiguous_requirements": ["carrier lock"],
                                    }
                                )
                            }
                        ]
                    }
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(live_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch.dict("os.environ", {"GEMINI_API_KEY": "mock_key"}), patch(
            "urllib.request.urlopen", return_value=mock_resp
        ):
            retry_resp = self.client.post(reverse("contract_retry_parse", args=[draft.public_ref]))
            self.assertRedirects(retry_resp, reverse("contract_review", args=[draft.public_ref]))

        draft.refresh_from_db()
        self.assertEqual(draft.source, ContractSource.GEMINI_LIVE)
        self.assertEqual(draft.product_description, "Refurbished Apple iPhone 17 Pro Max unlocked smartphone")
        self.assertEqual(draft.preferred_specs.get("storage_capacity"), "256GB")


class SpecFormattingAndUIHierarchyTests(TestCase):
    """Readable spec keys/values, single action sets on Confirmed, compact Home UI."""

    def test_spec_formatting_mappings(self):
        self.assertEqual(format_spec_label("connectivity"), "Connectivity")
        self.assertEqual(format_spec_label("noise_cancelling"), "Noise cancellation")
        self.assertEqual(format_spec_label("form_factor"), "Design")
        self.assertEqual(format_spec_label("battery_life"), "Battery life")
        self.assertEqual(format_spec_label("color"), "Colour")

        self.assertEqual(format_spec_value("battery_life", ">= 30 hours"), "30+ hours")
        self.assertEqual(format_spec_value("noise_cancelling", "Active"), "Active noise cancellation")
        self.assertEqual(format_spec_value("form_factor", "Over-Ear"), "Over-ear")
        self.assertEqual(format_spec_value("connectivity", "Bluetooth"), "Bluetooth connectivity")

    def test_review_uses_readable_labels_and_what_to_exclude(self):
        demo = get_demo_scenario("headphones", save_to_db=True)
        html = self.client.get(reverse("contract_review", args=[demo.public_ref])).content.decode("utf-8")
        for expected in (
            "Noise cancellation:",
            "Active noise cancellation",
            "Over-ear",
            "Bluetooth connectivity",
            "Battery life:",
            "30+ hours",
            "What to exclude",
        ):
            self.assertIn(expected, html)
        self.assertNotIn("tc-journey-indicator", html)
        # Ensure visible summary shows readable keys & values, never raw machine keys
        summary_block = html.split("Essential Purchase Requirements")[1].split("Optional details")[0]
        self.assertNotIn("noise_cancelling:", summary_block)
        self.assertNotIn("form_factor:", summary_block)
        self.assertNotIn("battery_life:", summary_block)
        # No redundant page-level New Search button on Review intro
        intro_section = html.split('<div class="tc-page-intro">')[1].split("</div>")[0]
        self.assertNotIn("New Search", intro_section)

    def test_confirmed_page_has_no_duplicate_cta_and_no_numeric_prefixes(self):
        demo = get_demo_scenario("headphones", save_to_db=True)
        resp = self.client.post(reverse("contract_confirm", args=[demo.public_ref]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        self.assertEqual(html.count("Find Matching Products"), 1)
        self.assertEqual(html.count("Edit Requirements"), 1)
        for clean_title in ("Shopping request", "Budget and quantity", "Important purchase information", "Confirmation and payment"):
            self.assertIn(clean_title, html)
        self.assertNotIn("1. Your shopping request", html)
        self.assertNotIn("5. Confirmation and payment", html)

    def test_home_has_no_magnifying_glass_icon_and_has_inline_status(self):
        html = self.client.get(reverse("home")).content.decode("utf-8").split("</style>")[1]
        self.assertNotIn("tc-search-icon", html)
        self.assertIn('id="home-inline-loading-status"', html)


class SafeBuyAnywayWorkflowTests(TestCase):
    """Discovery Buy Anyway routes cleanly to auditable revision without bypassing PolicyEngine."""

    def setUp(self):
        self.contract = PurchaseContract.objects.create(
            raw_prompt="Wireless over-ear headphones under $150 no on-ear",
            category="Electronics > Audio > Headphones",
            product_description="Over-ear wireless headphones",
            max_budget=Decimal("150.00"),
            currency="USD",
            quantity=1,
            required_specs={"connectivity": "Bluetooth", "battery_life": "30+ hours"},
            excluded_terms=["on-ear"],
            state=ContractState.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        self.unknown_prod = ProductEvidence.objects.create(
            product_id="BUY-UNK-1",
            title="Acoustic ANC Bluetooth Over-Ear Headphones",
            description="Comfortable over-ear wireless headphones with ANC.",
            price=Decimal("119.00"),
            currency="USD",
            source_merchant="AudioDirect",
            stock_status="IN_STOCK",
            raw_evidence={"features": {"connectivity": "Bluetooth", "form_factor": "Over-Ear"}},
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )
        self.conflict_prod = ProductEvidence.objects.create(
            product_id="BUY-CONF-2",
            title="Compact On-Ear Wireless Bluetooth Headphones",
            description="Lightweight on-ear wireless headphones.",
            price=Decimal("99.00"),
            currency="USD",
            source_merchant="SoundStore",
            stock_status="IN_STOCK",
            raw_evidence={"features": {"connectivity": "Bluetooth", "battery_life": "35 hours", "form_factor": "On-Ear"}},
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )
        self.oos_prod = ProductEvidence.objects.create(
            product_id="BUY-OOS-3",
            title="Unavailable Wireless Headphones",
            description="Out of stock.",
            price=Decimal("95.00"),
            currency="USD",
            source_merchant="EmptyShop",
            stock_status="OUT_OF_STOCK",
            retrieval_timestamp=timezone.now(),
            is_fixture=True,
        )

    def test_discovery_shows_actionable_buy_anyway_never_dead_disabled_labels(self):
        with patch("catalog.services.ProductSearchService.search_for_contract") as mock_search:
            mock_search.return_value = ([self.unknown_prod, self.conflict_prod, self.oos_prod], True, "Fixture")
            html = self.client.get(reverse("contract_discovery", args=[self.contract.public_ref])).content.decode("utf-8")

        self.assertNotIn("Unverified Specs", html)
        self.assertNotIn(">Ineligible<", html)
        self.assertIn(reverse("contract_buy_anyway", args=[self.contract.public_ref, "BUY-UNK-1"]), html)
        self.assertIn(reverse("contract_buy_anyway", args=[self.contract.public_ref, "BUY-CONF-2"]), html)
        self.assertIn("Buy Anyway", html)
        # Truly out-of-stock item cannot bypass via Buy Anyway
        self.assertNotIn(reverse("contract_buy_anyway", args=[self.contract.public_ref, "BUY-OOS-3"]), html)
        self.assertIn("Unavailable", html)

    def test_buy_anyway_situation_a_creates_new_draft_revision_voiding_old_approvals(self):
        old_prop = PurchaseProposal.objects.create(
            contract=self.contract,
            product=self.unknown_prod,
            source_merchant="Shop",
            payee_id="sandbox-payee",
            unit_price=Decimal("100.00"),
            quantity=1,
            base_amount=Decimal("100.00"),
            total_amount=Decimal("100.00"),
            currency="USD",
            status="APPROVED",
            cart_fingerprint="fp-old",
        )
        old_appr = PurchaseApproval.objects.create(
            proposal=old_prop,
            state="APPROVED",
            cart_fingerprint="fp-old",
            expires_at=timezone.now() + timezone.timedelta(minutes=15),
        )

        # POST without checkboxes does NOT mutate or create revision
        incomplete = self.client.post(
            reverse("contract_buy_anyway", args=[self.contract.public_ref, "BUY-UNK-1"]),
            {},
        )
        self.assertEqual(incomplete.status_code, 200)
        self.assertEqual(PurchaseContract.objects.count(), 1)

        # POST with both acknowledgments creates DRAFT v2, supersedes v1, voids old approvals
        complete = self.client.post(
            reverse("contract_buy_anyway", args=[self.contract.public_ref, "BUY-UNK-1"]),
            {"acknowledge_risk": "on", "acknowledge_revision": "on"},
        )
        v2 = PurchaseContract.objects.order_by("-version").first()
        self.assertEqual(v2.version, 2)
        self.assertEqual(v2.state, ContractState.DRAFT)
        self.assertRedirects(complete, reverse("contract_review", args=[v2.public_ref]))

        self.contract.refresh_from_db()
        old_prop.refresh_from_db()
        old_appr.refresh_from_db()
        self.assertEqual(self.contract.state, ContractState.SUPERSEDED)
        self.assertEqual(old_prop.status, "SUPERSEDED")
        self.assertEqual(old_appr.state, "VOIDED")
        self.assertEqual(
            v2.extraction_provenance["buy_anyway_acknowledgment"]["product_id"],
            "BUY-UNK-1",
        )
        # Verify v2 still blocks direct discovery until explicitly confirmed by shopper
        disc_blocked = self.client.get(reverse("contract_discovery", args=[v2.public_ref]))
        self.assertRedirects(disc_blocked, reverse("contract_review", args=[v2.public_ref]))

    def test_buy_anyway_situation_b_removes_conflicting_exclusion_into_new_draft(self):
        resp = self.client.post(
            reverse("contract_buy_anyway", args=[self.contract.public_ref, "BUY-CONF-2"]),
            {"acknowledge_risk": "on", "acknowledge_revision": "on"},
        )
        v2 = PurchaseContract.objects.order_by("-version").first()
        self.assertEqual(v2.version, 2)
        self.assertEqual(v2.state, ContractState.DRAFT)
        self.assertRedirects(resp, reverse("contract_review", args=[v2.public_ref]))
        self.assertNotIn("on-ear", v2.excluded_terms)
        self.assertEqual(
            v2.extraction_provenance["buy_anyway_acknowledgment"]["situation"],
            "CONSTRAINT_CONFLICT",
        )

