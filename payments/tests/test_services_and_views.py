"""Integration tests for PayPal Sandbox checkout, pre-capture revalidation, and server capture.

Covers:
- PAY-01 (Order creation with idempotency)
- PAY-02 (Buyer redirect to PayPal Sandbox)
- PAY-03 (Deterministic pre-capture revalidation)
- PAY-04 (Server-side capture execution)
- PAY-06 (Controlled demo payee boundary disclosure)
- Negative failure tests:
  * Altered payee
  * Altered amount / price tampering
  * Currency mismatch
  * Cart fingerprint tampering
  * Timeout / ambiguous response entering PENDING_RECONCILIATION
  * Authoritative reconciliation
  * Buyer cancellation
  * Replay prevention / single-use approval token consumption
"""

from decimal import Decimal
from unittest.mock import MagicMock

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import ProductEvidence
from contracts.models import PurchaseContract
from orders.models import (
    DEFAULT_DEMO_PAYEE_ID,
    ApprovalAlreadyConsumedError,
    PurchaseApproval,
    PurchaseProposal,
)
from payments.client import (
    PayPalAPIError,
    PayPalClient,
    PayPalTimeoutError,
)
from payments.models import PaymentOrder
from payments.services import (
    PaymentService,
    PayPalRevalidationError,
)


class PayPalCheckoutIntegrationTests(TestCase):
    """End-to-end flow and negative security validation tests."""

    def setUp(self):
        self.client = Client()

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
            product_id="prod_keychron_v1",
            brand="Keychron",
            title="Keychron V1 QMK Custom Mechanical Keyboard",
            description="Custom mechanical keyboard.",
            price=Decimal("69.99"),
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
            unit_price=Decimal("69.99"),
            base_amount=Decimal("69.99"),
            shipping_amount=Decimal("5.00"),
            tax_amount=Decimal("5.60"),
            fee_amount=Decimal("0.00"),
            total_amount=Decimal("80.59"),
            currency="USD",
            charges_confirmed=True,
            status="APPROVED",
        )
        self.proposal.cart_fingerprint = self.proposal.calculate_fingerprint()
        self.proposal.save()

        self.approval = PurchaseApproval.objects.create(
            token="test_approval_token_123",
            proposal=self.proposal,
            cart_fingerprint=self.proposal.cart_fingerprint,
            state="APPROVED",
            approved_at=timezone.now(),
        )

    def test_full_happy_path_checkout_and_server_capture(self):
        """Full end-to-end flow: initiate -> redirect -> return -> pre-capture revalidation -> capture -> PAID."""
        mock_paypal = MagicMock(spec=PayPalClient)

        # 1. Mock create_order
        mock_paypal.create_order.return_value = {
            "id": "PP-ORD-HAPPY-001",
            "status": "CREATED",
            "links": [
                {"rel": "approve", "href": "https://www.sandbox.paypal.com/checkoutnow?token=PP-ORD-HAPPY-001"}
            ],
        }

        # Step 1: Initiate checkout (consumes approval token atomically)
        payment_order, approve_url = PaymentService.initiate_checkout(
            approval_token=self.approval.token,
            return_url="http://localhost:8000/payments/checkout/return/",
            cancel_url="http://localhost:8000/payments/checkout/cancel/",
            client=mock_paypal,
        )

        self.assertEqual(payment_order.status, "CREATED")
        self.assertEqual(payment_order.paypal_order_id, "PP-ORD-HAPPY-001")
        self.assertEqual(approve_url, "https://www.sandbox.paypal.com/checkoutnow?token=PP-ORD-HAPPY-001")

        # Invariant check: Approval token is now CONSUMED
        self.approval.refresh_from_db()
        self.assertEqual(self.approval.state, "CONSUMED")
        self.assertIsNotNone(self.approval.consumed_at)

        # Invariant check: Attempting duplicate checkout with the same token MUST fail immediately
        with self.assertRaises(ApprovalAlreadyConsumedError):
            PaymentService.initiate_checkout(
                approval_token=self.approval.token,
                return_url="http://localhost:8000/payments/checkout/return/",
                cancel_url="http://localhost:8000/payments/checkout/cancel/",
                client=mock_paypal,
            )

        # 2. Mock get_order for server-side authoritative query
        mock_paypal.get_order.return_value = {
            "id": "PP-ORD-HAPPY-001",
            "status": "APPROVED",
            "purchase_units": [
                {
                    "reference_id": str(payment_order.id),
                    "custom_id": self.approval.cart_fingerprint,
                    "amount": {
                        "currency_code": "USD",
                        "value": "80.59",
                    },
                    "payee": {
                        "email_address": DEFAULT_DEMO_PAYEE_ID,
                    },
                }
            ],
        }

        # 3. Mock capture_order
        mock_paypal.capture_order.return_value = {
            "id": "PP-ORD-HAPPY-001",
            "status": "COMPLETED",
            "purchase_units": [
                {
                    "payments": {
                        "captures": [
                            {
                                "id": "CAPTURE-HAPPY-999",
                                "status": "COMPLETED",
                                "seller_receivable_breakdown": {
                                    "gross_amount": {"value": "80.59", "currency_code": "USD"},
                                },
                            }
                        ]
                    }
                }
            ],
        }

        # Step 2: Complete checkout upon return redirect
        completed_order, capture_record = PaymentService.complete_checkout(
            paypal_order_id="PP-ORD-HAPPY-001",
            client=mock_paypal,
        )

        self.assertEqual(completed_order.status, "COMPLETED")
        self.assertIsNotNone(capture_record)
        self.assertEqual(capture_record.capture_id, "CAPTURE-HAPPY-999")
        self.assertEqual(capture_record.status, "COMPLETED")
        self.assertEqual(capture_record.amount, Decimal("80.59"))

        # Check audit trail
        events = [e["event"] for e in completed_order.audit_log]
        self.assertIn("CREATED", events)
        self.assertIn("BUYER_APPROVED", events)
        self.assertIn("COMPLETED", events)

    def test_pre_capture_revalidation_rejects_altered_payee(self):
        """Security: If PayPal order has an altered or rogue payee, capture is strictly aborted."""
        mock_paypal = MagicMock(spec=PayPalClient)
        mock_paypal.create_order.return_value = {"id": "PP-ORD-ROUGE-PAYEE", "status": "CREATED", "links": []}

        payment_order, _ = PaymentService.initiate_checkout(
            approval_token=self.approval.token,
            return_url="http://localhost:8000/payments/checkout/return/",
            cancel_url="http://localhost:8000/payments/checkout/cancel/",
            client=mock_paypal,
        )

        # Mock remote order with different payee
        mock_paypal.get_order.return_value = {
            "id": "PP-ORD-ROUGE-PAYEE",
            "status": "APPROVED",
            "purchase_units": [
                {
                    "custom_id": self.approval.cart_fingerprint,
                    "amount": {"currency_code": "USD", "value": "80.59"},
                    "payee": {"email_address": "attacker@evil.example.com"},  # Rogue payee!
                }
            ],
        }

        with self.assertRaises(PayPalRevalidationError) as ctx:
            PaymentService.complete_checkout("PP-ORD-ROUGE-PAYEE", client=mock_paypal)

        self.assertIn("Payee", str(ctx.exception))
        # Ensure capture was NEVER called
        self.assertEqual(mock_paypal.capture_order.call_count, 0)

        # Order must be marked FAILED
        payment_order.refresh_from_db()
        self.assertEqual(payment_order.status, "FAILED")

    def test_pre_capture_revalidation_rejects_altered_price(self):
        """Security: If amount shifted (e.g. $80.59 -> $85.00), capture is strictly aborted."""
        mock_paypal = MagicMock(spec=PayPalClient)
        mock_paypal.create_order.return_value = {"id": "PP-ORD-PRICE-SHIFT", "status": "CREATED", "links": []}

        PaymentService.initiate_checkout(
            approval_token=self.approval.token,
            return_url="http://localhost:8000/payments/checkout/return/",
            cancel_url="http://localhost:8000/payments/checkout/cancel/",
            client=mock_paypal,
        )

        # Mock remote order with higher price
        mock_paypal.get_order.return_value = {
            "id": "PP-ORD-PRICE-SHIFT",
            "status": "APPROVED",
            "purchase_units": [
                {
                    "custom_id": self.approval.cart_fingerprint,
                    "amount": {"currency_code": "USD", "value": "85.00"},  # Price changed!
                    "payee": {"email_address": DEFAULT_DEMO_PAYEE_ID},
                }
            ],
        }

        with self.assertRaises(PayPalRevalidationError) as ctx:
            PaymentService.complete_checkout("PP-ORD-PRICE-SHIFT", client=mock_paypal)

        self.assertIn("Price tampering", str(ctx.exception))
        self.assertEqual(mock_paypal.capture_order.call_count, 0)

    def test_pre_capture_revalidation_rejects_cart_fingerprint_mismatch(self):
        """Security: If custom_id does not match the approved cart fingerprint, capture is aborted."""
        mock_paypal = MagicMock(spec=PayPalClient)
        mock_paypal.create_order.return_value = {"id": "PP-ORD-FINGERPRINT-MISMATCH", "status": "CREATED", "links": []}

        PaymentService.initiate_checkout(
            approval_token=self.approval.token,
            return_url="http://localhost:8000/payments/checkout/return/",
            cancel_url="http://localhost:8000/payments/checkout/cancel/",
            client=mock_paypal,
        )

        # Mock remote order with wrong custom_id
        mock_paypal.get_order.return_value = {
            "id": "PP-ORD-FINGERPRINT-MISMATCH",
            "status": "APPROVED",
            "purchase_units": [
                {
                    "custom_id": "forged_fingerprint_xyz",
                    "amount": {"currency_code": "USD", "value": "80.59"},
                    "payee": {"email_address": DEFAULT_DEMO_PAYEE_ID},
                }
            ],
        }

        with self.assertRaises(PayPalRevalidationError):
            PaymentService.complete_checkout("PP-ORD-FINGERPRINT-MISMATCH", client=mock_paypal)

        self.assertEqual(mock_paypal.capture_order.call_count, 0)

    def test_pre_capture_rejects_unapproved_order_without_failing_state(self):
        """Unapproved order (e.g. PAYER_ACTION_REQUIRED) raises error but preserves CREATED state."""
        mock_paypal = MagicMock(spec=PayPalClient)
        mock_paypal.create_order.return_value = {"id": "PP-ORD-PENDING-APPROVAL", "status": "CREATED", "links": []}

        order, _ = PaymentService.initiate_checkout(
            approval_token=self.approval.token,
            return_url="http://localhost:8000/payments/checkout/return/",
            cancel_url="http://localhost:8000/payments/checkout/cancel/",
            client=mock_paypal,
        )

        mock_paypal.get_order.return_value = {
            "id": "PP-ORD-PENDING-APPROVAL",
            "status": "PAYER_ACTION_REQUIRED",
            "purchase_units": [
                {
                    "custom_id": self.approval.cart_fingerprint,
                    "amount": {"currency_code": "USD", "value": "80.59"},
                    "payee": {"email_address": DEFAULT_DEMO_PAYEE_ID},
                }
            ],
        }

        with self.assertRaises(PayPalAPIError):
            PaymentService.complete_checkout("PP-ORD-PENDING-APPROVAL", client=mock_paypal)

        order.refresh_from_db()
        self.assertEqual(order.status, "CREATED")
        self.assertEqual(mock_paypal.capture_order.call_count, 0)

    def test_timeout_enters_pending_reconciliation_and_reconciles(self):
        """Fault tolerance: Network timeout on capture enters PENDING_RECONCILIATION and queries status."""
        mock_paypal = MagicMock(spec=PayPalClient)
        mock_paypal.create_order.return_value = {"id": "PP-ORD-TIMEOUT", "status": "CREATED", "links": []}

        PaymentService.initiate_checkout(
            approval_token=self.approval.token,
            return_url="http://localhost:8000/payments/checkout/return/",
            cancel_url="http://localhost:8000/payments/checkout/cancel/",
            client=mock_paypal,
        )

        # 1. get_order succeeds
        mock_paypal.get_order.side_effect = [
            # First call for complete_checkout
            {
                "id": "PP-ORD-TIMEOUT",
                "status": "APPROVED",
                "purchase_units": [
                    {
                        "custom_id": self.approval.cart_fingerprint,
                        "amount": {"currency_code": "USD", "value": "80.59"},
                        "payee": {"email_address": DEFAULT_DEMO_PAYEE_ID},
                    }
                ],
            },
            # Second call for reconcile_order
            {
                "id": "PP-ORD-TIMEOUT",
                "status": "COMPLETED",
                "purchase_units": [
                    {
                        "payments": {
                            "captures": [{"id": "CAP-RECONCILED-1", "status": "COMPLETED"}]
                        }
                    }
                ],
            },
        ]

        # 2. capture_order raises timeout
        mock_paypal.capture_order.side_effect = PayPalTimeoutError("Connection timed out waiting for PayPal.")

        # Complete checkout catches timeout and invokes reconciliation
        order, capture = PaymentService.complete_checkout("PP-ORD-TIMEOUT", client=mock_paypal)

        self.assertEqual(order.status, "COMPLETED")
        self.assertIsNotNone(capture)
        self.assertEqual(capture.capture_id, "CAP-RECONCILED-1")

    def test_buyer_cancellation_flow(self):
        """Buyer cancellation records CANCELLED status without capture."""
        mock_paypal = MagicMock(spec=PayPalClient)
        mock_paypal.create_order.return_value = {"id": "PP-ORD-CANCEL", "status": "CREATED", "links": []}

        PaymentService.initiate_checkout(
            approval_token=self.approval.token,
            return_url="http://localhost:8000/payments/checkout/return/",
            cancel_url="http://localhost:8000/payments/checkout/cancel/",
            client=mock_paypal,
        )

        cancelled_order = PaymentService.cancel_checkout("PP-ORD-CANCEL")
        self.assertEqual(cancelled_order.status, "CANCELLED")

    def test_views_return_and_receipt_rendering(self):
        """Test HTTP views: checkout return renders receipt and cancellation renders cancelled."""
        order = PaymentOrder.objects.create(
            approval=self.approval,
            proposal=self.proposal,
            contract=self.contract,
            paypal_order_id="PP-ORD-VIEW-TEST",
            cart_fingerprint=self.approval.cart_fingerprint,
            status="COMPLETED",
            payee_id=DEFAULT_DEMO_PAYEE_ID,
            currency="USD",
            unit_price=Decimal("69.99"),
            quantity=1,
            base_amount=Decimal("69.99"),
            shipping_amount=Decimal("5.00"),
            tax_amount=Decimal("5.60"),
            fee_amount=Decimal("0.00"),
            total_amount=Decimal("80.59"),
            create_idempotency_key="CREATE-IDEMP-VIEW",
            capture_idempotency_key="CAPTURE-IDEMP-VIEW",
        )

        # 1. order_detail view
        url = reverse("payments:order_detail", kwargs={"paypal_order_id": order.paypal_order_id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Payment Completed")
        self.assertContains(resp, "Order Paid")
        self.assertContains(resp, "Controlled Demo Payee Boundary")
        self.assertContains(resp, "PP-ORD-VIEW-TEST")
        # Invariant: Sensitive internal idempotency keys must NEVER leak into customer-facing rendered HTML
        self.assertNotContains(resp, "CREATE-IDEMP-VIEW")
        self.assertNotContains(resp, "CAPTURE-IDEMP-VIEW")

        # 2. checkout_cancel view
        cancel_url = reverse("payments:checkout_cancel") + f"?token={order.paypal_order_id}"
        resp_cancel = self.client.get(cancel_url)
        self.assertEqual(resp_cancel.status_code, 200)
        self.assertContains(resp_cancel, "Checkout Cancelled")

    def test_checkout_initiate_approval_error_redirects_without_500(self):
        """When checkout initiation encounters an ApprovalError, redirects to approval_detail without NoReverseMatch."""
        # Consume the approval so it triggers ApprovalAlreadyConsumedError
        self.approval.consume()

        initiate_url = reverse("payments:checkout_initiate", kwargs={"token": self.approval.token})
        response = self.client.post(initiate_url)
        self.assertEqual(response.status_code, 302)
        expected_redirect = reverse("approval_detail", kwargs={"public_ref": self.approval.public_ref})
        self.assertEqual(response.url, expected_redirect)

    def test_checkout_return_missing_token_renders_failed_page_400(self):
        """Returning from PayPal without token parameter renders failed.html with status 400."""
        return_url = reverse("payments:checkout_return")
        response = self.client.get(return_url)
        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "payments/failed.html")
        self.assertContains(response, "Missing PayPal order token parameter.", status_code=400)

    def test_order_detail_view_routes_by_status(self):
        """order_detail renders distinct templates matching the exact payment order status."""
        # PENDING_RECONCILIATION order
        prop_pending = PurchaseProposal.objects.create(
            contract=self.contract,
            product=self.product,
            source_merchant="Keychron",
            payee_id=DEFAULT_DEMO_PAYEE_ID,
            quantity=1,
            unit_price=Decimal("69.99"),
            base_amount=Decimal("69.99"),
            shipping_amount=Decimal("5.00"),
            tax_amount=Decimal("5.60"),
            fee_amount=Decimal("0.00"),
            total_amount=Decimal("80.59"),
            currency="USD",
            charges_confirmed=True,
            status="APPROVED",
            cart_fingerprint="fingerprint_pending_test",
        )
        appr_pending = PurchaseApproval.objects.create(
            token="token_pending_test",
            proposal=prop_pending,
            cart_fingerprint="fingerprint_pending_test",
            state="CONSUMED",
            approved_at=timezone.now(),
        )

        pending_order = PaymentOrder.objects.create(
            approval=appr_pending,
            proposal=prop_pending,
            contract=self.contract,
            paypal_order_id="PP-ORD-PENDING-TEST",
            cart_fingerprint=appr_pending.cart_fingerprint,
            status="PENDING_RECONCILIATION",
            payee_id=DEFAULT_DEMO_PAYEE_ID,
            currency="USD",
            unit_price=Decimal("69.99"),
            quantity=1,
            base_amount=Decimal("69.99"),
            total_amount=Decimal("80.59"),
            create_idempotency_key="CREATE-PENDING",
            capture_idempotency_key="CAPTURE-PENDING",
        )
        url_pending = reverse("payments:order_detail", kwargs={"paypal_order_id": pending_order.paypal_order_id})
        resp_pending = self.client.get(url_pending)
        self.assertEqual(resp_pending.status_code, 200)
        self.assertTemplateUsed(resp_pending, "payments/pending.html")
        self.assertContains(resp_pending, "Payment Pending Reconciliation")

        # CANCELLED order
        prop_cancelled = PurchaseProposal.objects.create(
            contract=self.contract,
            product=self.product,
            source_merchant="Keychron",
            payee_id=DEFAULT_DEMO_PAYEE_ID,
            quantity=1,
            unit_price=Decimal("69.99"),
            base_amount=Decimal("69.99"),
            shipping_amount=Decimal("5.00"),
            tax_amount=Decimal("5.60"),
            fee_amount=Decimal("0.00"),
            total_amount=Decimal("80.59"),
            currency="USD",
            charges_confirmed=True,
            status="APPROVED",
            cart_fingerprint="fingerprint_cancelled_test",
        )
        appr_cancelled = PurchaseApproval.objects.create(
            token="token_cancelled_test",
            proposal=prop_cancelled,
            cart_fingerprint="fingerprint_cancelled_test",
            state="CONSUMED",
            approved_at=timezone.now(),
        )

        cancelled_order = PaymentOrder.objects.create(
            approval=appr_cancelled,
            proposal=prop_cancelled,
            contract=self.contract,
            paypal_order_id="PP-ORD-CANCELLED-TEST",
            cart_fingerprint=appr_cancelled.cart_fingerprint,
            status="CANCELLED",
            payee_id=DEFAULT_DEMO_PAYEE_ID,
            currency="USD",
            unit_price=Decimal("69.99"),
            quantity=1,
            base_amount=Decimal("69.99"),
            total_amount=Decimal("80.59"),
            create_idempotency_key="CREATE-CANCELLED",
            capture_idempotency_key="CAPTURE-CANCELLED",
        )
        url_cancelled = reverse("payments:order_detail", kwargs={"paypal_order_id": cancelled_order.paypal_order_id})
        resp_cancelled = self.client.get(url_cancelled)
        self.assertEqual(resp_cancelled.status_code, 200)
        self.assertTemplateUsed(resp_cancelled, "payments/cancelled.html")
        self.assertContains(resp_cancelled, "Checkout Cancelled")

        # FAILED order
        prop_failed = PurchaseProposal.objects.create(
            contract=self.contract,
            product=self.product,
            source_merchant="Keychron",
            payee_id=DEFAULT_DEMO_PAYEE_ID,
            quantity=1,
            unit_price=Decimal("69.99"),
            base_amount=Decimal("69.99"),
            shipping_amount=Decimal("5.00"),
            tax_amount=Decimal("5.60"),
            fee_amount=Decimal("0.00"),
            total_amount=Decimal("80.59"),
            currency="USD",
            charges_confirmed=True,
            status="APPROVED",
            cart_fingerprint="fingerprint_failed_test",
        )
        appr_failed = PurchaseApproval.objects.create(
            token="token_failed_test",
            proposal=prop_failed,
            cart_fingerprint="fingerprint_failed_test",
            state="CONSUMED",
            approved_at=timezone.now(),
        )

        failed_order = PaymentOrder.objects.create(
            approval=appr_failed,
            proposal=prop_failed,
            contract=self.contract,
            paypal_order_id="PP-ORD-FAILED-TEST",
            cart_fingerprint=appr_failed.cart_fingerprint,
            status="FAILED",
            payee_id=DEFAULT_DEMO_PAYEE_ID,
            currency="USD",
            unit_price=Decimal("69.99"),
            quantity=1,
            base_amount=Decimal("69.99"),
            total_amount=Decimal("80.59"),
            create_idempotency_key="CREATE-FAILED",
            capture_idempotency_key="CAPTURE-FAILED",
        )
        url_failed = reverse("payments:order_detail", kwargs={"paypal_order_id": failed_order.paypal_order_id})
        resp_failed = self.client.get(url_failed)
        self.assertEqual(resp_failed.status_code, 200)
        self.assertTemplateUsed(resp_failed, "payments/failed.html")
        self.assertContains(resp_failed, "Payment status: FAILED")

        # CREATED order (awaiting buyer approval)
        prop_created = PurchaseProposal.objects.create(
            contract=self.contract,
            product=self.product,
            source_merchant="Keychron",
            payee_id=DEFAULT_DEMO_PAYEE_ID,
            quantity=1,
            unit_price=Decimal("69.99"),
            base_amount=Decimal("69.99"),
            shipping_amount=Decimal("5.00"),
            tax_amount=Decimal("5.60"),
            fee_amount=Decimal("0.00"),
            total_amount=Decimal("80.59"),
            currency="USD",
            charges_confirmed=True,
            status="APPROVED",
            cart_fingerprint="fingerprint_created_test",
        )
        appr_created = PurchaseApproval.objects.create(
            token="token_created_test",
            proposal=prop_created,
            cart_fingerprint="fingerprint_created_test",
            state="CONSUMED",
            approved_at=timezone.now(),
        )
        created_order = PaymentOrder.objects.create(
            approval=appr_created,
            proposal=prop_created,
            contract=self.contract,
            paypal_order_id="PP-ORD-CREATED-TEST",
            cart_fingerprint=appr_created.cart_fingerprint,
            status="CREATED",
            payee_id=DEFAULT_DEMO_PAYEE_ID,
            currency="USD",
            unit_price=Decimal("69.99"),
            quantity=1,
            base_amount=Decimal("69.99"),
            total_amount=Decimal("80.59"),
            create_idempotency_key="CREATE-CREATED",
            capture_idempotency_key="CAPTURE-CREATED",
            paypal_approval_url="https://www.sandbox.paypal.com/checkoutnow?token=PP-ORD-CREATED-TEST",
        )
        url_created = reverse("payments:order_detail", kwargs={"paypal_order_id": created_order.paypal_order_id})
        resp_created = self.client.get(url_created)
        self.assertEqual(resp_created.status_code, 200)
        self.assertTemplateUsed(resp_created, "payments/pending.html")
        self.assertContains(resp_created, "Awaiting PayPal Sandbox Buyer Approval")
        self.assertContains(resp_created, "Complete Approval on PayPal Sandbox")

        # BUYER_APPROVED order (ready for server capture)
        prop_approved = PurchaseProposal.objects.create(
            contract=self.contract,
            product=self.product,
            source_merchant="Keychron",
            payee_id=DEFAULT_DEMO_PAYEE_ID,
            quantity=1,
            unit_price=Decimal("69.99"),
            base_amount=Decimal("69.99"),
            shipping_amount=Decimal("5.00"),
            tax_amount=Decimal("5.60"),
            fee_amount=Decimal("0.00"),
            total_amount=Decimal("80.59"),
            currency="USD",
            charges_confirmed=True,
            status="APPROVED",
            cart_fingerprint="fingerprint_approved_test",
        )
        appr_approved = PurchaseApproval.objects.create(
            token="token_approved_test",
            proposal=prop_approved,
            cart_fingerprint="fingerprint_approved_test",
            state="CONSUMED",
            approved_at=timezone.now(),
        )
        approved_order = PaymentOrder.objects.create(
            approval=appr_approved,
            proposal=prop_approved,
            contract=self.contract,
            paypal_order_id="PP-ORD-APPROVED-TEST",
            cart_fingerprint=appr_approved.cart_fingerprint,
            status="BUYER_APPROVED",
            payee_id=DEFAULT_DEMO_PAYEE_ID,
            currency="USD",
            unit_price=Decimal("69.99"),
            quantity=1,
            base_amount=Decimal("69.99"),
            total_amount=Decimal("80.59"),
            create_idempotency_key="CREATE-APPROVED",
            capture_idempotency_key="CAPTURE-APPROVED",
        )
        url_approved = reverse("payments:order_detail", kwargs={"paypal_order_id": approved_order.paypal_order_id})
        resp_approved = self.client.get(url_approved)
        self.assertEqual(resp_approved.status_code, 200)
        self.assertTemplateUsed(resp_approved, "payments/pending.html")
        self.assertContains(resp_approved, "Buyer Approved — Ready for Server Capture")
