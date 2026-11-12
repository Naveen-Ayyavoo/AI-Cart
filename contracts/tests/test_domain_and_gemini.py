"""
Unit test suite for Purchase Contract domain models, Pydantic schemas,
demo fixtures, and Gemini Free Tier client.
"""

import io
import json
import urllib.error
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from pydantic import ValidationError as PydanticValidationError

from contracts.fixtures import DEMO_SCENARIOS, FALLBACK_DISCLOSURE, get_demo_scenario
from contracts.gemini import MODEL_FLASH, MODEL_FLASH_LITE, GeminiContractClient
from contracts.models import ContractSource, ContractState, PurchaseContract
from contracts.schemas import PurchaseContractExtraction


class PurchaseContractModelTestCase(TestCase):
    def test_contract_model_creation_and_clean(self):
        """Verify valid contract creation with exact Decimal budget passes clean()."""
        contract = PurchaseContract.objects.create(
            raw_prompt="Looking for wireless headphones under $150",
            category="Electronics > Audio",
            product_description="Wireless over-ear headphones",
            max_budget=Decimal("150.00"),
            currency="USD",
            quantity=1,
            required_specs={"connectivity": "Bluetooth"},
            preferred_specs={"color": "Black"},
            excluded_terms=["wired"],
            ambiguous_requirements=[],
            source=ContractSource.GEMINI_LIVE,
            model_used=MODEL_FLASH_LITE,
        )
        contract.full_clean()
        self.assertIsInstance(contract.max_budget, Decimal)
        self.assertEqual(contract.max_budget, Decimal("150.00"))
        self.assertEqual(contract.version, 1)
        self.assertEqual(contract.state, ContractState.DRAFT)

    def test_contract_clean_rejects_negative_or_zero_budget(self):
        """Zero or negative budgets must fail closed."""
        contract = PurchaseContract(
            raw_prompt="Invalid budget item",
            category="Test",
            product_description="Test item",
            max_budget=Decimal("0.00"),
            currency="USD",
        )
        with self.assertRaises(DjangoValidationError):
            contract.clean()

    def test_contract_clean_rejects_invalid_quantity(self):
        """Quantity less than 1 must fail closed."""
        contract = PurchaseContract(
            raw_prompt="Invalid quantity item",
            category="Test",
            product_description="Test item",
            max_budget=Decimal("50.00"),
            currency="USD",
            quantity=0,
        )
        with self.assertRaises(DjangoValidationError):
            contract.clean()

    def test_contract_clean_rejects_prompt_exceeding_2000_chars(self):
        """Prompts over 2,000 characters must fail closed."""
        long_prompt = "a" * 2001
        contract = PurchaseContract(
            raw_prompt=long_prompt,
            category="Test",
            product_description="Test item",
            max_budget=Decimal("50.00"),
            currency="USD",
        )
        with self.assertRaises(DjangoValidationError):
            contract.clean()

    def test_contract_confirm_locks_state(self):
        """Confirming marks contract CONFIRMED and sets confirmed_at timestamp."""
        contract = PurchaseContract.objects.create(
            raw_prompt="Valid prompt",
            category="Electronics",
            product_description="Audio device",
            max_budget=Decimal("99.99"),
            currency="USD",
            quantity=1,
        )
        self.assertIsNone(contract.confirmed_at)
        contract.confirm()
        self.assertEqual(contract.state, ContractState.CONFIRMED)
        self.assertIsNotNone(contract.confirmed_at)

        # Cannot reconfirm
        with self.assertRaises(DjangoValidationError):
            contract.confirm()

    def test_contract_versioning_and_revisions(self):
        """Creating a revision increments version, links parent, sets state to DRAFT, and supersedes confirmed parent."""
        parent = PurchaseContract.objects.create(
            raw_prompt="Initial prompt",
            category="Electronics",
            product_description="Version 1 specs",
            max_budget=Decimal("100.00"),
            currency="USD",
            quantity=1,
        )
        parent.confirm()
        self.assertEqual(parent.state, ContractState.CONFIRMED)

        # Create revision with budget override
        revision = parent.create_revision(max_budget=Decimal("120.00"))
        parent.refresh_from_db()

        self.assertEqual(parent.state, ContractState.SUPERSEDED)
        self.assertEqual(revision.version, 2)
        self.assertEqual(revision.parent_contract, parent)
        self.assertEqual(revision.state, ContractState.DRAFT)
        self.assertEqual(revision.max_budget, Decimal("120.00"))
        self.assertIsNone(revision.confirmed_at)


class PydanticSchemaTestCase(TestCase):
    def test_pydantic_schema_valid_payload(self):
        """Valid schema converts string budget to exact Decimal."""
        payload = {
            "category": "Electronics > Audio",
            "product_description": "Over-ear wireless headphones",
            "max_budget": "149.99",
            "currency": "USD",
            "quantity": 2,
            "required_specs": {"connectivity": "Bluetooth"},
            "preferred_specs": {"color": "White"},
            "excluded_terms": ["wired"],
            "ambiguous_requirements": [],
        }
        extraction = PurchaseContractExtraction(**payload)
        self.assertIsInstance(extraction.max_budget, Decimal)
        self.assertEqual(extraction.max_budget, Decimal("149.99"))
        self.assertEqual(extraction.quantity, 2)

    def test_pydantic_schema_extra_forbid(self):
        """Unrecognized / hallucinated keys must raise ValidationError."""
        payload = {
            "category": "Electronics",
            "product_description": "Device",
            "max_budget": "50.00",
            "currency": "USD",
            "hallucinated_payment_trigger": True,  # extra key
        }
        with self.assertRaises(PydanticValidationError):
            # pyrefly: ignore[unexpected-keyword]
            PurchaseContractExtraction(**payload)

    def test_pydantic_schema_rejects_negative_budget(self):
        """Negative budget fails schema validation."""
        payload = {
            "category": "Electronics",
            "product_description": "Device",
            "max_budget": "-25.00",
            "currency": "USD",
        }
        with self.assertRaises(PydanticValidationError):
            PurchaseContractExtraction(**payload)


class DemoFixturesTestCase(TestCase):
    def test_all_demo_scenarios_valid(self):
        """All predefined demo fixtures must pass Pydantic and Django clean() validation."""
        for key in DEMO_SCENARIOS:
            contract = get_demo_scenario(key, save_to_db=False)
            self.assertEqual(contract.source, ContractSource.DEMO_FIXTURE)
            self.assertEqual(
                contract.extraction_provenance.get("disclosure"),
                FALLBACK_DISCLOSURE,
            )
            self.assertIsInstance(contract.max_budget, Decimal)
            self.assertGreater(contract.max_budget, Decimal("0.00"))
            contract.full_clean()


class GeminiClientTestCase(TestCase):
    def test_prompt_capping_at_2000_chars(self):
        """Gemini client rejects prompts > 2,000 characters immediately."""
        client = GeminiContractClient(api_key="mock_key")
        long_prompt = "x" * 2001
        with self.assertRaises(ValueError) as ctx:
            client.extract_contract(long_prompt)
        self.assertIn("exceeds maximum limit of 2,000 characters", str(ctx.exception))

    def test_model_allocation_routing(self):
        """Client allocates gemini-3.5-flash-lite for routine prompts and gemini-3.8-flash for complex queries."""
        client = GeminiContractClient(api_key="mock_key")
        simple_prompt = "I want wireless headphones under $100"
        complex_prompt = "Looking for a mechanical keyboard comparing tactile versus linear switches trade-off"

        # Verify default model identifiers
        self.assertEqual(MODEL_FLASH_LITE, "gemini-3.5-flash-lite")
        self.assertEqual(MODEL_FLASH, "gemini-3.8-flash")

        self.assertEqual(client.select_model(simple_prompt), "gemini-3.5-flash-lite")
        self.assertEqual(client.select_model(complex_prompt), "gemini-3.8-flash")

    def test_model_identifiers_configurable_via_env(self):
        """Model identifiers can be dynamically configured via environment variables."""
        with patch.dict(
            "os.environ",
            {
                "GEMINI_MODEL_ROUTINE": "gemini-custom-routine",
                "GEMINI_MODEL_COMPLEX": "gemini-custom-complex",
            },
        ):
            custom_client = GeminiContractClient(api_key="mock_key")
            self.assertEqual(
                custom_client.select_model("Routine search"),
                "gemini-custom-routine",
            )
            self.assertEqual(
                custom_client.select_model("Complex trade-off evaluation"),
                "gemini-custom-complex",
            )

    def test_gemini_client_missing_key_fallback(self):
        """When API key is not configured, client preserves the shopper's actual request via FALLBACK_PARSER."""
        client = GeminiContractClient(api_key="")
        contract, is_fallback, msg = client.extract_contract(
            "I want noise cancelling headphones under $150"
        )
        self.assertTrue(is_fallback)
        self.assertEqual(contract.source, ContractSource.FALLBACK_PARSER)
        self.assertEqual(
            contract.extraction_provenance.get("disclosure"),
            "Direct shopper request preservation (AI interpretation unavailable).",
        )
        self.assertEqual(contract.max_budget, Decimal("150.00"))
        self.assertIn("API key not configured", msg)

    @patch("urllib.request.urlopen")
    def test_gemini_client_mock_success(self, mock_urlopen):
        """Mock Gemini HTTP 200 JSON response parses into a valid contract."""
        mock_response_data = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "category": "Electronics > Audio > Headphones",
                                        "product_description": "Over-ear wireless headphones with active noise cancellation",
                                        "max_budget": "139.99",
                                        "currency": "USD",
                                        "quantity": 1,
                                        "required_specs": {"connectivity": "Bluetooth"},
                                        "preferred_specs": {"color": "Midnight Black"},
                                        "excluded_terms": ["wired"],
                                        "ambiguous_requirements": [],
                                    }
                                )
                            }
                        ]
                    }
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_response_data).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        client = GeminiContractClient(api_key="mock_valid_key")
        contract, is_fallback, msg = client.extract_contract(
            "Noise cancelling headphones in black for under $140"
        )

        self.assertFalse(is_fallback)
        self.assertEqual(contract.source, ContractSource.GEMINI_LIVE)
        self.assertEqual(contract.max_budget, Decimal("139.99"))
        self.assertEqual(contract.state, ContractState.DRAFT)
        self.assertIn("Extracted via Gemini Free Tier", msg)

    @patch("urllib.request.urlopen")
    def test_gemini_client_quota_exhaustion_fallback(self, mock_urlopen):
        """HTTP 429 quota exhaustion halts calls and preserves shopper request via FALLBACK_PARSER."""
        http_error = urllib.error.HTTPError(
            url="https://example.com",
            code=429,
            msg="Resource Exhausted",
            hdrs={},
            fp=io.BytesIO(b'{"error": "Resource has been exhausted"}'),
        )
        mock_urlopen.side_effect = http_error

        client = GeminiContractClient(api_key="mock_valid_key")
        contract, is_fallback, msg = client.extract_contract(
            "Looking for an ergonomic mesh desk chair under $250"
        )

        self.assertTrue(is_fallback)
        self.assertEqual(contract.source, ContractSource.FALLBACK_PARSER)
        self.assertEqual(
            contract.extraction_provenance.get("disclosure"),
            "Direct shopper request preservation (AI interpretation unavailable).",
        )
        self.assertEqual(contract.max_budget, Decimal("250.00"))
        self.assertIn("quota reached", msg)

    @patch("urllib.request.urlopen")
    def test_gemini_client_timeout_fallback(self, mock_urlopen):
        """Network timeout preserves shopper request via FALLBACK_PARSER rather than unrelated fixtures."""
        mock_urlopen.side_effect = urllib.error.URLError(TimeoutError("Connection timed out."))

        client = GeminiContractClient(api_key="mock_valid_key")
        contract, is_fallback, msg = client.extract_contract(
            "Noise cancelling headphones for travel under $200"
        )

        self.assertTrue(is_fallback)
        self.assertEqual(contract.source, ContractSource.FALLBACK_PARSER)
        self.assertEqual(
            contract.extraction_provenance.get("disclosure"),
            "Direct shopper request preservation (AI interpretation unavailable).",
        )
        self.assertEqual(contract.max_budget, Decimal("200.00"))
        self.assertIn("could not be completed", msg)

    @patch("urllib.request.urlopen")
    def test_gemini_client_malformed_response_fallback(self, mock_urlopen):
        """Malformed Gemini JSON preserves shopper request via FALLBACK_PARSER without unrelated fixtures."""
        mock_resp = MagicMock()
        # Return invalid non-JSON data
        mock_resp.read.return_value = b"<!DOCTYPE html><html><body>502 Bad Gateway</body></html>"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        client = GeminiContractClient(api_key="mock_valid_key")
        contract, is_fallback, msg = client.extract_contract(
            "Mechanical keyboard with brown tactile switches"
        )

        self.assertTrue(is_fallback)
        self.assertEqual(contract.source, ContractSource.FALLBACK_PARSER)
        self.assertEqual(
            contract.extraction_provenance.get("disclosure"),
            "Direct shopper request preservation (AI interpretation unavailable).",
        )
        self.assertIn("could not be completed", msg)
