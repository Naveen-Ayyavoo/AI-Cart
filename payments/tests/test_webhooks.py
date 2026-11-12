"""Webhook verification, deduplication, and state update tests for AI Cart (formerly TrustCart) Phase P6."""

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import ProductEvidence
from contracts.models import PurchaseContract
from orders.models import (
    DEFAULT_DEMO_PAYEE_ID,
    PurchaseApproval,
    PurchaseProposal,
)
from payments.client import PayPalClient, PayPalError
from payments.models import (
    PaymentCaptureRecord,
    PaymentOrder,
    WebhookEventRecord,
)
from payments.services import PaymentService


class PayPalWebhookIntegrationTests(TestCase):
    """Test webhook verification, deduplication, and state updates."""

    def setUp(self):
        self.client = Client()

        self.contract = PurchaseContract.objects.create(
            raw_prompt="Ergonomic keyboard",
            category="Keyboards",
            product_description="Mechanical keyboard",
            max_budget=Decimal("100.00"),
            currency="USD",
            quantity=1,
            state="CONFIRMED",
            confirmed_at=timezone.now(),
        )

        self.product = ProductEvidence.objects.create(
            product_id="prod_keychron_k8",
            brand="Keychron",
            title="Keychron K8 Wireless Keyboard",
            description="Keyboard description",
            price=Decimal("79.99"),
            currency="USD",
            source_merchant="Keychron",
            stock_status="IN_STOCK",
        )

        self.proposal = PurchaseProposal.objects.create(
            contract=self.contract,
            product=self.product,
            source_merchant="Keychron",
            payee_id=DEFAULT_DEMO_PAYEE_ID,
            quantity=1,
            unit_price=Decimal("79.99"),
            base_amount=Decimal("79.99"),
            shipping_amount=Decimal("0.00"),
            tax_amount=Decimal("6.40"),
            fee_amount=Decimal("0.00"),
            total_amount=Decimal("86.39"),
            currency="USD",
            cart_fingerprint="mock_fp_k8",
            charges_confirmed=True,
            status="APPROVED",
        )

        self.approval = PurchaseApproval.objects.create(
            token="token_wh_test",
            proposal=self.proposal,
            cart_fingerprint="mock_fp_k8",
            state="CONSUMED",
            consumed_at=timezone.now(),
        )

        self.order = PaymentOrder.objects.create(
            approval=self.approval,
            proposal=self.proposal,
            contract=self.contract,
            paypal_order_id="PP-ORD-WH-001",
            cart_fingerprint="mock_fp_k8",
            status="CREATED",
            payee_id=DEFAULT_DEMO_PAYEE_ID,
            currency="USD",
            unit_price=Decimal("79.99"),
            quantity=1,
            base_amount=Decimal("79.99"),
            shipping_amount=Decimal("0.00"),
            tax_amount=Decimal("6.40"),
            fee_amount=Decimal("0.00"),
            total_amount=Decimal("86.39"),
            create_idempotency_key="CREATE-WH-001",
            capture_idempotency_key="CAPTURE-WH-001",
        )

        self.valid_headers = {
            "PAYPAL-TRANSMISSION-ID": "trans_12345",
            "PAYPAL-TRANSMISSION-TIME": "2026-11-10T12:00:00Z",
            "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-1",
            "PAYPAL-AUTH-ALGO": "SHA256withRSA",
            "PAYPAL-TRANSMISSION-SIG": "valid_signature_hash_xyz",
        }

    def test_webhook_missing_headers_rejected(self):
        """Missing PayPal verification headers returns HTTP 400."""
        url = reverse("payments:paypal_webhook")
        payload = json.dumps({"id": "WH-EV-1", "event_type": "CHECKOUT.ORDER.APPROVED"})
        resp = self.client.post(url, data=payload, content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Missing mandatory PayPal webhook transmission headers", resp.content.decode())

    def test_webhook_invalid_signature_rejected(self):
        """Invalid cryptographic signature is rejected and recorded as REJECTED."""
        mock_client = MagicMock(spec=PayPalClient)
        mock_client.verify_webhook_signature.return_value = False

        payload = {
            "id": "WH-FORGED-999",
            "event_type": "CHECKOUT.ORDER.APPROVED",
            "resource_type": "checkout-order",
            "summary": "Order approved",
        }

        with self.assertRaises(PayPalError):
            PaymentService.handle_webhook(
                headers=self.valid_headers,
                raw_body=json.dumps(payload),
                client=mock_client,
            )

        # Check audit record
        event_record = WebhookEventRecord.objects.get(event_id="WH-FORGED-999")
        self.assertEqual(event_record.status, "REJECTED")

    def test_webhook_duplicate_event_deduplication(self):
        """Duplicate webhook event IDs are skipped without reprocessing."""
        mock_client = MagicMock(spec=PayPalClient)
        mock_client.verify_webhook_signature.return_value = True

        payload = {
            "id": "WH-DUP-001",
            "event_type": "CHECKOUT.ORDER.APPROVED",
            "resource": {"id": self.order.paypal_order_id},
        }

        # First call processes event
        rec1 = PaymentService.handle_webhook(
            headers=self.valid_headers,
            raw_body=json.dumps(payload),
            client=mock_client,
        )
        self.assertEqual(rec1.status, "PROCESSED")

        # Second call with same event_id is recognized as duplicate
        rec2 = PaymentService.handle_webhook(
            headers=self.valid_headers,
            raw_body=json.dumps(payload),
            client=mock_client,
        )
        self.assertEqual(rec2.status, "DUPLICATE")
        # Ensure verify_webhook_signature was only called once
        self.assertEqual(mock_client.verify_webhook_signature.call_count, 1)

    def test_webhook_processes_order_approved(self):
        """CHECKOUT.ORDER.APPROVED transitions order from CREATED to BUYER_APPROVED."""
        mock_client = MagicMock(spec=PayPalClient)
        mock_client.verify_webhook_signature.return_value = True

        payload = {
            "id": "WH-EV-ORDER-APPROVED",
            "event_type": "CHECKOUT.ORDER.APPROVED",
            "resource": {"id": self.order.paypal_order_id},
        }

        PaymentService.handle_webhook(
            headers=self.valid_headers,
            raw_body=json.dumps(payload),
            client=mock_client,
        )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "BUYER_APPROVED")

    def test_webhook_processes_capture_completed(self):
        """PAYMENT.CAPTURE.COMPLETED triggers authoritative reconciliation and marks COMPLETED."""
        mock_client = MagicMock(spec=PayPalClient)
        mock_client.verify_webhook_signature.return_value = True
        mock_client.get_order.return_value = {
            "id": self.order.paypal_order_id,
            "status": "COMPLETED",
            "purchase_units": [
                {
                    "payments": {
                        "captures": [
                            {
                                "id": "CAP-WH-777",
                                "status": "COMPLETED",
                                "amount": {"value": "86.39", "currency_code": "USD"},
                            }
                        ]
                    }
                }
            ],
        }

        payload = {
            "id": "WH-EV-CAP-COMPLETED",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "resource": {
                "id": "CAP-WH-777",
                "status": "COMPLETED",
                "amount": {"value": "86.39", "currency_code": "USD"},
                "supplementary_data": {
                    "related_ids": {
                        "order_id": self.order.paypal_order_id,
                    }
                },
            },
        }

        PaymentService.handle_webhook(
            headers=self.valid_headers,
            raw_body=json.dumps(payload),
            client=mock_client,
        )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "COMPLETED")
        self.assertTrue(PaymentCaptureRecord.objects.filter(capture_id="CAP-WH-777").exists())

    def test_out_of_order_webhook_cannot_regress_completed_order(self):
        """Out-of-order CHECKOUT.ORDER.APPROVED arriving after COMPLETED is ignored and does NOT regress status."""
        self.order.status = "COMPLETED"
        self.order.save()

        mock_client = MagicMock(spec=PayPalClient)
        mock_client.verify_webhook_signature.return_value = True

        payload = {
            "id": "WH-EV-OUT-OF-ORDER",
            "event_type": "CHECKOUT.ORDER.APPROVED",
            "resource": {"id": self.order.paypal_order_id},
        }

        PaymentService.handle_webhook(
            headers=self.valid_headers,
            raw_body=json.dumps(payload),
            client=mock_client,
        )

        self.order.refresh_from_db()
        # Invariant check: Status remains COMPLETED
        self.assertEqual(self.order.status, "COMPLETED")

    def test_webhook_http_listener_endpoint(self):
        """Test full HTTP POST to webhook listener endpoint."""
        with patch.object(PaymentService, "handle_webhook") as mock_handle:
            mock_record = MagicMock()
            mock_record.event_id = "WH-HTTP-1"
            mock_record.status = "PROCESSED"
            mock_handle.return_value = mock_record

            url = reverse("payments:paypal_webhook")
            payload = json.dumps({"id": "WH-HTTP-1", "event_type": "PAYMENT.CAPTURE.COMPLETED"})
            resp = self.client.post(
                url,
                data=payload,
                content_type="application/json",
                HTTP_PAYPAL_TRANSMISSION_ID="trans_abc",
                HTTP_PAYPAL_TRANSMISSION_TIME="2026-11-10T12:00:00Z",
                HTTP_PAYPAL_CERT_URL="https://api.sandbox.paypal.com/cert.pem",
                HTTP_PAYPAL_AUTH_ALGO="SHA256withRSA",
                HTTP_PAYPAL_TRANSMISSION_SIG="sig_abc",
            )

            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["event_id"], "WH-HTTP-1")
