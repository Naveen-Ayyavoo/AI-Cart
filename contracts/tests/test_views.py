"""
Automated test suite for Purchase Contract views, forms, versioning workflows,
and non-payment authorization disclosures.
"""

import json
from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from contracts.fixtures import get_demo_scenario
from contracts.models import ContractSource, ContractState, PurchaseContract


class ContractViewsWorkflowTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_home_page_renders_form_and_scenarios(self):
        """Home page renders prompt intake form and all 3 demo scenarios."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home.html")
        content = response.content.decode("utf-8")
        self.assertIn("Describe What You Want to Purchase", content)
        self.assertIn("2,000 characters", content)
        self.assertIn("Wireless Noise-Canceling Headphones under $150", content)
        self.assertIn("Mechanical Gaming Keyboard under $100", content)
        self.assertIn("Ergonomic Office Chair under $250", content)

    @patch("contracts.gemini.GeminiContractClient.extract_contract")
    def test_prompt_submission_creates_draft_contract(self, mock_extract):
        """Valid prompt extraction redirects to review page in DRAFT state."""
        mock_contract = PurchaseContract.objects.create(
            raw_prompt="Ergonomic chair under $200",
            category="Furniture",
            product_description="Office chair",
            max_budget=Decimal("200.00"),
            currency="USD",
            quantity=1,
            state=ContractState.DRAFT,
            source=ContractSource.GEMINI_LIVE,
        )
        mock_extract.return_value = (mock_contract, False, "Success")

        response = self.client.post(
            reverse("contract_create"),
            {"prompt": "Ergonomic chair under $200"},
        )
        self.assertRedirects(response, reverse("contract_review", args=[mock_contract.public_ref]))

    def test_prompt_submission_rejects_exceeded_length(self):
        """Prompts exceeding 2,000 characters return HTTP 400 and fail closed."""
        long_prompt = "x" * 2001
        response = self.client.post(
            reverse("contract_create"),
            {"prompt": long_prompt},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PurchaseContract.objects.count(), 0)

    def test_scenario_quick_click_loads_demo_fixture(self):
        """Selecting a demo scenario loads fixture without Gemini API calls."""
        response = self.client.post(
            reverse("contract_create"),
            {"scenario_key": "headphones"},
        )
        contract = PurchaseContract.objects.first()
        self.assertIsNotNone(contract)
        self.assertEqual(contract.source, ContractSource.DEMO_FIXTURE)
        self.assertEqual(contract.category, "Electronics > Audio > Headphones")
        self.assertRedirects(response, reverse("contract_review", args=[contract.public_ref]))

    def test_review_page_renders_fields_and_disclosures(self):
        """Review page renders fields, fallback banner (if fixture), and non-payment notice."""
        contract = get_demo_scenario("keyboard", save_to_db=True)
        response = self.client.get(reverse("contract_review", args=[contract.public_ref]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "contracts/review.html")

        content = response.content.decode("utf-8")
        # Check clean demonstration sample notice
        self.assertIn("Sample Shopping Plan:", content)
        self.assertNotIn("Gemini Free Tier", content)
        self.assertNotIn("Zero-Spend", content)
        # Check non-payment authorization notice
        self.assertIn("It does NOT charge your account, reserve funds, or authorize payment", content)
        # Check fields and version badge
        self.assertIn("Version 1", content)
        self.assertIn("100.00", content)
        self.assertIn("Tenkeyless (TKL)", content)

    def test_contract_update_in_draft_state(self):
        """Updating a DRAFT contract modifies fields in place on the same version."""
        contract = PurchaseContract.objects.create(
            raw_prompt="Initial query",
            category="Computers",
            product_description="Basic keyboard",
            max_budget=Decimal("75.00"),
            currency="USD",
            quantity=1,
            state=ContractState.DRAFT,
        )
        update_data = {
            "category": "Computers > Keyboards",
            "product_description": "Updated mechanical keyboard",
            "max_budget": "89.99",
            "currency": "USD",
            "quantity": 2,
            "required_specs_json": json.dumps({"switches": "Tactile"}),
            "preferred_specs_json": json.dumps({"color": "Grey"}),
            "excluded_terms_json": json.dumps(["wireless"]),
            "ambiguous_requirements_json": json.dumps([]),
        }
        response = self.client.post(
            reverse("contract_update", args=[contract.public_ref]),
            update_data,
        )
        self.assertRedirects(response, reverse("contract_review", args=[contract.public_ref]))

        contract.refresh_from_db()
        self.assertEqual(contract.version, 1)
        self.assertEqual(contract.category, "Computers > Keyboards")
        self.assertEqual(contract.max_budget, Decimal("89.99"))
        self.assertEqual(contract.quantity, 2)
        self.assertEqual(contract.required_specs, {"switches": "Tactile"})
        self.assertEqual(contract.excluded_terms, ["wireless"])

    def test_contract_update_in_confirmed_state_creates_new_version(self):
        """
        Modifying a CONFIRMED contract must create a new version in DRAFT state.
        Confirmed contracts are immutable and marked SUPERSEDED.
        """
        contract = PurchaseContract.objects.create(
            raw_prompt="Locked prompt",
            category="Audio",
            product_description="Locked headphones",
            max_budget=Decimal("150.00"),
            currency="USD",
            quantity=1,
            state=ContractState.DRAFT,
        )
        contract.confirm()
        self.assertEqual(contract.state, ContractState.CONFIRMED)

        # Attempt to edit confirmed contract
        update_data = {
            "category": "Audio > Headphones",
            "product_description": "Locked headphones with budget change",
            "max_budget": "175.00",
            "currency": "USD",
            "quantity": 1,
            "required_specs_json": json.dumps({}),
            "preferred_specs_json": json.dumps({}),
            "excluded_terms_json": json.dumps([]),
            "ambiguous_requirements_json": json.dumps([]),
        }
        response = self.client.post(
            reverse("contract_update", args=[contract.public_ref]),
            update_data,
        )

        contract.refresh_from_db()
        # Original must now be superseded
        self.assertEqual(contract.state, ContractState.SUPERSEDED)

        # New contract version must be created
        new_version = PurchaseContract.objects.filter(parent_contract=contract).first()
        self.assertIsNotNone(new_version)
        self.assertEqual(new_version.version, 2)
        self.assertEqual(new_version.state, ContractState.DRAFT)
        self.assertEqual(new_version.max_budget, Decimal("175.00"))
        self.assertRedirects(response, reverse("contract_review", args=[new_version.public_ref]))

    def test_contract_confirm_csrf_and_state_transition(self):
        """CSRF-protected POST to confirm transitions contract to CONFIRMED."""
        contract = PurchaseContract.objects.create(
            raw_prompt="Ready to confirm",
            category="Audio",
            product_description="High quality headphones",
            max_budget=Decimal("120.00"),
            currency="USD",
            quantity=1,
            state=ContractState.DRAFT,
        )
        response = self.client.post(reverse("contract_confirm", args=[contract.public_ref]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "contracts/confirmed.html")

        contract.refresh_from_db()
        self.assertEqual(contract.state, ContractState.CONFIRMED)
        self.assertIsNotNone(contract.confirmed_at)

        content = response.content.decode("utf-8")
        self.assertIn("Shopping Requirements Confirmed", content)
        self.assertIn("Confirming your requirements is not a payment.", content)
        self.assertNotIn("Additional options", content)

    def test_contract_confirm_rejects_get_request(self):
        """GET request to confirmation endpoint is rejected with HTTP 405 Method Not Allowed."""
        contract = PurchaseContract.objects.create(
            raw_prompt="GET attempt",
            category="Audio",
            product_description="Device",
            max_budget=Decimal("50.00"),
            currency="USD",
            quantity=1,
            state=ContractState.DRAFT,
        )
        response = self.client.get(reverse("contract_confirm", args=[contract.public_ref]))
        self.assertEqual(response.status_code, 405)
        contract.refresh_from_db()
        self.assertEqual(contract.state, ContractState.DRAFT)

    def test_contract_confirm_get_request_allowed_when_confirmed(self):
        """GET request to confirmation endpoint renders confirmed.html if contract is already CONFIRMED."""
        contract = PurchaseContract.objects.create(
            raw_prompt="Confirmed view",
            category="Audio",
            product_description="Device",
            max_budget=Decimal("50.00"),
            currency="USD",
            quantity=1,
            state=ContractState.CONFIRMED,
        )
        response = self.client.get(reverse("contract_confirm", args=[contract.public_ref]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "contracts/confirmed.html")
        self.assertIn("Shopping Requirements Confirmed", response.content.decode("utf-8"))

    def test_contract_confirm_post_idempotent_when_already_confirmed(self):
        """POST request to confirmation endpoint when already CONFIRMED does not error and renders receipt."""
        contract = PurchaseContract.objects.create(
            raw_prompt="Already confirmed",
            category="Audio",
            product_description="Device",
            max_budget=Decimal("50.00"),
            currency="USD",
            quantity=1,
            state=ContractState.CONFIRMED,
        )
        response = self.client.post(reverse("contract_confirm", args=[contract.public_ref]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "contracts/confirmed.html")
