"""Unit tests for PayPal Sandbox client, configuration security, and payment models."""

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from catalog.models import ProductEvidence
from contracts.models import PurchaseContract
from orders.models import (
    DEFAULT_DEMO_PAYEE_ID,
    PurchaseApproval,
    PurchaseProposal,
)
from payments.client import (
    PayPalClient,
    PayPalConfigurationError,
)
from payments.models import (
    PaymentCaptureRecord,
    PaymentOrder,
    WebhookEventRecord,
)


class PayPalClientSecurityAndUnitTests(TestCase):
    """Test PayPal client security invariants, OAuth token caching, and API formatting."""

    def test_client_rejects_live_or_non_sandbox_endpoints(self):
        """Invariant: Client MUST fail closed if live production endpoints are configured."""
        with self.assertRaises(PayPalConfigurationError):
            PayPalClient(base_url="https://api-m.paypal.com")

        with self.assertRaises(PayPalConfigurationError):
            PayPalClient(base_url="http://api-m.sandbox.paypal.com")

        with self.assertRaises(PayPalConfigurationError):
            PayPalClient(base_url="https://untrusted-host.example.com")

    def test_client_requires_credentials_for_oauth(self):
        """Missing client_id or client_secret fails closed with PayPalConfigurationError."""
        client = PayPalClient(client_id="", client_secret="")
        with self.assertRaises(PayPalConfigurationError):
            client._get_access_token()

    @patch("urllib.request.urlopen")
    def test_oauth_token_caching_and_refresh(self, mock_urlopen):
        """Access token is cached in-memory and refreshed when requested or expired."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "access_token": "mock_access_token_123",
            "expires_in": 3600,
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        client = PayPalClient(client_id="test_id", client_secret="test_secret")

        # First call retrieves token via API
        token1 = client._get_access_token()
        self.assertEqual(token1, "mock_access_token_123")
        self.assertEqual(mock_urlopen.call_count, 1)

        # Second call uses in-memory cache without hitting network
        token2 = client._get_access_token()
        self.assertEqual(token2, "mock_access_token_123")
        self.assertEqual(mock_urlopen.call_count, 1)

        # Force refresh makes a new network call
        token3 = client._get_access_token(force_refresh=True)
        self.assertEqual(token3, "mock_access_token_123")
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("urllib.request.urlopen")
    def test_create_order_payload_and_idempotency_headers(self, mock_urlopen):
        """Verify Orders v2 payload structure, Decimal formatting, and idempotency header."""
        # 1. Mock OAuth token response
        oauth_resp = MagicMock()
        oauth_resp.read.return_value = json.dumps({"access_token": "token_abc", "expires_in": 3600}).encode("utf-8")

        # 2. Mock Create Order response
        order_resp = MagicMock()
        order_resp.read.return_value = json.dumps({
            "id": "PAYPAL-ORDER-123",
            "status": "CREATED",
            "links": [
                {"rel": "approve", "href": "https://www.sandbox.paypal.com/checkoutnow?token=PAYPAL-ORDER-123"}
            ],
        }).encode("utf-8")

        mock_urlopen.return_value.__enter__.side_effect = [oauth_resp, order_resp]

        client = PayPalClient(client_id="test_id", client_secret="test_secret")
        result = client.create_order(
            reference_id="ORDER-REF-001",
            custom_id="CART-FINGERPRINT-ABC",
            title="Keychron C3 Pro",
            sku="KEYCHRON-C3-RED",
            quantity=1,
            unit_price=Decimal("36.99"),
            base_amount=Decimal("36.99"),
            shipping_amount=Decimal("5.00"),
            tax_amount=Decimal("3.00"),
            total_amount=Decimal("44.99"),
            currency="USD",
            payee_email="sb-merchant-trustcart@business.example.com",
            return_url="http://localhost:8000/payments/checkout/return/",
            cancel_url="http://localhost:8000/payments/checkout/cancel/",
            idempotency_key="IDEMPOTENCY-UUID-001",
        )

        self.assertEqual(result["id"], "PAYPAL-ORDER-123")
        self.assertEqual(result["status"], "CREATED")

        # Inspect the request sent to Orders v2
        create_req = mock_urlopen.call_args_list[1][0][0]
        self.assertEqual(create_req.get_header("Paypal-request-id"), "IDEMPOTENCY-UUID-001")
        self.assertEqual(create_req.get_header("Authorization"), "Bearer token_abc")

        sent_payload = json.loads(create_req.data.decode("utf-8"))
        self.assertEqual(sent_payload["intent"], "CAPTURE")
        unit = sent_payload["purchase_units"][0]
        self.assertEqual(unit["amount"]["value"], "44.99")
        self.assertEqual(unit["amount"]["breakdown"]["item_total"]["value"], "36.99")
        self.assertEqual(unit["amount"]["breakdown"]["shipping"]["value"], "5.00")
        self.assertEqual(unit["amount"]["breakdown"]["tax_total"]["value"], "3.00")
        self.assertEqual(unit["payee"]["email_address"], "sb-merchant-trustcart@business.example.com")
        self.assertEqual(sent_payload["payment_source"]["paypal"]["experience_context"]["user_action"], "PAY_NOW")

    @patch("urllib.request.urlopen")
    def test_get_order_and_capture_order(self, mock_urlopen):
        """Verify get_order and capture_order endpoints and headers."""
        oauth_resp = MagicMock()
        oauth_resp.read.return_value = json.dumps({"access_token": "token_abc", "expires_in": 3600}).encode("utf-8")

        get_resp = MagicMock()
        get_resp.read.return_value = json.dumps({"id": "ORD-123", "status": "APPROVED"}).encode("utf-8")

        capture_resp = MagicMock()
        capture_resp.read.return_value = json.dumps({
            "id": "ORD-123",
            "status": "COMPLETED",
            "purchase_units": [{"payments": {"captures": [{"id": "CAP-999", "status": "COMPLETED"}]}}],
        }).encode("utf-8")

        mock_urlopen.return_value.__enter__.side_effect = [oauth_resp, get_resp, capture_resp]

        client = PayPalClient(client_id="test_id", client_secret="test_secret")

        # 1. get_order
        res_get = client.get_order("ORD-123")
        self.assertEqual(res_get["status"], "APPROVED")

        # 2. capture_order
        res_cap = client.capture_order("ORD-123", idempotency_key="CAP-IDEMP-001")
        self.assertEqual(res_cap["status"], "COMPLETED")
        cap_req = mock_urlopen.call_args_list[2][0][0]
        self.assertEqual(cap_req.get_header("Paypal-request-id"), "CAP-IDEMP-001")

    @patch("urllib.request.urlopen")
    def test_verify_webhook_ssrf_protection_and_verification(self, mock_urlopen):
        """Webhook verification validates cert_url domain and passes payload."""
        client = PayPalClient(client_id="test_id", client_secret="test_secret")

        # SSRF attack: cert_url on non-paypal domain rejected immediately without network call
        is_valid_malicious = client.verify_webhook_signature(
            transmission_id="trans-1",
            transmission_time="2026-11-10T12:00:00Z",
            cert_url="https://attacker.example.com/cert.pem",
            auth_algo="SHA256withRSA",
            transmission_sig="sig123",
            webhook_id="WH-123",
            raw_event_body={"id": "EV-1"},
        )
        self.assertFalse(is_valid_malicious)

        # Legitimate cert_url: verify call sent to PayPal
        oauth_resp = MagicMock()
        oauth_resp.read.return_value = json.dumps({"access_token": "token_abc", "expires_in": 3600}).encode("utf-8")
        verify_resp = MagicMock()
        verify_resp.read.return_value = json.dumps({"verification_status": "SUCCESS"}).encode("utf-8")
        mock_urlopen.return_value.__enter__.side_effect = [oauth_resp, verify_resp]

        is_valid_legit = client.verify_webhook_signature(
            transmission_id="trans-1",
            transmission_time="2026-11-10T12:00:00Z",
            cert_url="https://api.sandbox.paypal.com/v1/notifications/certs/CERT-123",
            auth_algo="SHA256withRSA",
            transmission_sig="sig123",
            webhook_id="WH-123",
            raw_event_body={"id": "EV-1"},
        )
        self.assertTrue(is_valid_legit)


class PaymentModelsUnitTests(TestCase):
    """Test PaymentOrder, PaymentCaptureRecord, and WebhookEventRecord models."""

    def setUp(self):
        self.contract = PurchaseContract.objects.create(
            raw_prompt="Ergonomic mechanical keyboard",
            category="Keyboards",
            product_description="Mechanical keyboard with quiet switches",
            max_budget=Decimal("100.00"),
            currency="USD",
            quantity=1,
            state="CONFIRMED",
            confirmed_at=timezone.now(),
        )
        self.product = ProductEvidence.objects.create(
            product_id="prod_keychron_k2",
            brand="Keychron",
            title="Keychron K2 Wireless Keyboard",
            description="Ergonomic keyboard",
            price=Decimal("45.00"),
            currency="USD",
            source_merchant="Keychron Store",
            stock_status="IN_STOCK",
        )
        self.proposal = PurchaseProposal.objects.create(
            contract=self.contract,
            product=self.product,
            source_merchant="Keychron Store",
            payee_id=DEFAULT_DEMO_PAYEE_ID,
            quantity=1,
            unit_price=Decimal("45.00"),
            base_amount=Decimal("45.00"),
            shipping_amount=Decimal("5.00"),
            tax_amount=Decimal("4.00"),
            fee_amount=Decimal("0.00"),
            total_amount=Decimal("54.00"),
            currency="USD",
            cart_fingerprint="mock_fingerprint_123",
            charges_confirmed=True,
            status="APPROVED",
        )
        self.approval = PurchaseApproval.objects.create(
            token="mock_token_abc",
            proposal=self.proposal,
            cart_fingerprint="mock_fingerprint_123",
            state="CONSUMED",
            consumed_at=timezone.now(),
        )

    def test_payment_order_creation_and_audit_log(self):
        """PaymentOrder links to approval, proposal, and contract, and maintains audit trail."""
        order = PaymentOrder.objects.create(
            approval=self.approval,
            proposal=self.proposal,
            contract=self.contract,
            paypal_order_id="PP-ORD-987",
            cart_fingerprint="mock_fingerprint_123",
            status="CREATED",
            payee_id=DEFAULT_DEMO_PAYEE_ID,
            currency="USD",
            unit_price=Decimal("45.00"),
            quantity=1,
            base_amount=Decimal("45.00"),
            shipping_amount=Decimal("5.00"),
            tax_amount=Decimal("4.00"),
            fee_amount=Decimal("0.00"),
            total_amount=Decimal("54.00"),
            create_idempotency_key="IDEMP-CREATE-001",
            capture_idempotency_key="IDEMP-CAPTURE-001",
            paypal_approval_url="https://www.sandbox.paypal.com/checkoutnow?token=PP-ORD-987",
        )

        order.append_audit_event("CREATED", "Created PayPal order via Orders v2.")
        order.save()

        self.assertEqual(order.status, "CREATED")
        self.assertEqual(order.total_amount, Decimal("54.00"))
        self.assertEqual(len(order.audit_log), 1)

        # PaymentCaptureRecord
        capture = PaymentCaptureRecord.objects.create(
            order=order,
            capture_id="CAP-111",
            status="COMPLETED",
            amount=Decimal("54.00"),
            currency="USD",
        )
        self.assertEqual(capture.status, "COMPLETED")
        self.assertEqual(order.captures.count(), 1)

    def test_webhook_event_record_deduplication(self):
        """WebhookEventRecord enforces unique event_id."""
        WebhookEventRecord.objects.create(
            event_id="WH-EV-001",
            event_type="PAYMENT.CAPTURE.COMPLETED",
            resource_type="capture",
            status="VERIFIED",
        )
        with self.assertRaises(IntegrityError):
            WebhookEventRecord.objects.create(
                event_id="WH-EV-001",
                event_type="PAYMENT.CAPTURE.COMPLETED",
                resource_type="capture",
                status="DUPLICATE",
            )
