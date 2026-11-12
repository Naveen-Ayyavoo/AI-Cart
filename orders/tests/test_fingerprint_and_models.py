"""Unit tests for Cart Fingerprinting, Purchase Proposal & Approval Models.

Covers:
- APPR-01 (SHA-256 cart fingerprinting over exact parameters)
- APPR-02 (Time-limited 15-minute TTL approval token)
- APPR-03 (Tamper resistance: 1 cent or parameter modification invalidates approval)
- APPR-05 (Single-use consumption and replay rejection)
"""

import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from catalog.models import ProductEvidence
from contracts.models import PurchaseContract
from orders.fingerprint import CartFingerprintParams, compute_cart_fingerprint
from orders.models import (
    DEFAULT_DEMO_PAYEE_ID,
    DEMO_PAYEE_DISCLOSURE,
    ApprovalAlreadyConsumedError,
    ApprovalExpiredError,
    ApprovalInvalidError,
    PurchaseApproval,
    PurchaseProposal,
)
from policies.models import PolicyEvaluationReport


class CartFingerprintTests(TestCase):
    """Test cryptographic SHA-256 cart fingerprinting."""

    def setUp(self):
        self.params = CartFingerprintParams(
            product_id="prod_123",
            variant_id="VAR_BLK",
            sku="SKU_999",
            source_merchant="Amazon",
            payee_id=DEFAULT_DEMO_PAYEE_ID,
            quantity=1,
            unit_price=Decimal("148.00"),
            base_amount=Decimal("148.00"),
            shipping_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            fee_amount=Decimal("0.00"),
            total_amount=Decimal("148.00"),
            currency="USD",
            contract_id=str(uuid.uuid4()),
            contract_version=1,
        )

    def test_fingerprint_deterministic(self):
        """Identical parameters produce exact identical SHA-256 hash."""
        fp1 = compute_cart_fingerprint(self.params)
        fp2 = compute_cart_fingerprint(self.params)
        self.assertEqual(fp1, fp2)
        self.assertEqual(len(fp1), 64)

    def test_fingerprint_tamper_detection_price(self):
        """Altering unit price by even 1 cent ($0.01) generates a completely different hash."""
        fp1 = compute_cart_fingerprint(self.params)
        tampered_params = CartFingerprintParams(
            product_id=self.params.product_id,
            variant_id=self.params.variant_id,
            sku=self.params.sku,
            source_merchant=self.params.source_merchant,
            payee_id=self.params.payee_id,
            quantity=self.params.quantity,
            unit_price=Decimal("148.01"),  # 1 cent difference
            base_amount=Decimal("148.01"),
            shipping_amount=self.params.shipping_amount,
            tax_amount=self.params.tax_amount,
            fee_amount=self.params.fee_amount,
            total_amount=Decimal("148.01"),
            currency=self.params.currency,
            contract_id=self.params.contract_id,
            contract_version=self.params.contract_version,
        )
        fp2 = compute_cart_fingerprint(tampered_params)
        self.assertNotEqual(fp1, fp2)

    def test_fingerprint_tamper_detection_payee(self):
        """Altering PayPal demo payee generates a different hash."""
        fp1 = compute_cart_fingerprint(self.params)
        tampered_params = CartFingerprintParams(
            product_id=self.params.product_id,
            variant_id=self.params.variant_id,
            sku=self.params.sku,
            source_merchant=self.params.source_merchant,
            payee_id="attacker-payee@malicious.com",
            quantity=self.params.quantity,
            unit_price=self.params.unit_price,
            base_amount=self.params.base_amount,
            shipping_amount=self.params.shipping_amount,
            tax_amount=self.params.tax_amount,
            fee_amount=self.params.fee_amount,
            total_amount=self.params.total_amount,
            currency=self.params.currency,
            contract_id=self.params.contract_id,
            contract_version=self.params.contract_version,
        )
        fp2 = compute_cart_fingerprint(tampered_params)
        self.assertNotEqual(fp1, fp2)

    def test_fingerprint_tamper_detection_contract_version(self):
        """Incrementing contract version generates a different hash."""
        fp1 = compute_cart_fingerprint(self.params)
        tampered_params = CartFingerprintParams(
            product_id=self.params.product_id,
            variant_id=self.params.variant_id,
            sku=self.params.sku,
            source_merchant=self.params.source_merchant,
            payee_id=self.params.payee_id,
            quantity=self.params.quantity,
            unit_price=self.params.unit_price,
            base_amount=self.params.base_amount,
            shipping_amount=self.params.shipping_amount,
            tax_amount=self.params.tax_amount,
            fee_amount=self.params.fee_amount,
            total_amount=self.params.total_amount,
            currency=self.params.currency,
            contract_id=self.params.contract_id,
            contract_version=2,  # revision
        )
        fp2 = compute_cart_fingerprint(tampered_params)
        self.assertNotEqual(fp1, fp2)


class PurchaseProposalAndApprovalModelTests(TestCase):
    """Test PurchaseProposal and PurchaseApproval models and atomic lifecycle."""

    def setUp(self):
        self.contract = PurchaseContract.objects.create(
            raw_prompt="Sony WH-CH720N wireless noise canceling headphones under $150",
            category="Audio / Headphones",
            product_description="Sony WH-CH720N wireless noise canceling headphones",
            max_budget=Decimal("150.00"),
            currency="USD",
            quantity=1,
            state="CONFIRMED",
            confirmed_at=timezone.now(),
        )

        self.product = ProductEvidence.objects.create(
            product_id="ch3_demo_whch720n",
            brand="Sony",
            title="Sony WH-CH720N Wireless Noise Canceling Headphones",
            description="Lightweight wireless noise canceling headphones.",
            price=Decimal("148.00"),
            currency="USD",
            source_merchant="Amazon",
            merchant_id="amzn_us",
            variant_id="WHCH720N/B",
            sku="B0BS1PR858",
            stock_status="IN_STOCK",
            raw_evidence={"features": {"noise_canceling": "Active"}},
        )

        self.policy_report = PolicyEvaluationReport.objects.create(
            contract=self.contract,
            product=self.product,
            outcome="ELIGIBLE",
            unit_price=Decimal("148.00"),
            quantity=1,
            total_item_price=Decimal("148.00"),
            budget_ceiling=Decimal("150.00"),
            currency="USD",
            preference_score=100,
            summary="Eligible: Passed all constraints.",
        )

        # Create Proposal
        self.proposal = PurchaseProposal(
            contract=self.contract,
            product=self.product,
            policy_report=self.policy_report,
            source_merchant=self.product.source_merchant,
            payee_id=DEFAULT_DEMO_PAYEE_ID,
            variant_id=self.product.variant_id,
            sku=self.product.sku,
            quantity=1,
            unit_price=Decimal("148.00"),
            base_amount=Decimal("148.00"),
            shipping_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            fee_amount=Decimal("0.00"),
            total_amount=Decimal("148.00"),
            currency="USD",
            charges_confirmed=True,
        )
        self.proposal.cart_fingerprint = self.proposal.calculate_fingerprint()
        self.proposal.save()

    def test_proposal_validation_math(self):
        """Invalid arithmetic between base, shipping, taxes, and total raises ValidationError."""
        # Bad total math
        bad_proposal = PurchaseProposal(
            contract=self.contract,
            product=self.product,
            source_merchant="Amazon",
            payee_id=DEFAULT_DEMO_PAYEE_ID,
            quantity=1,
            unit_price=Decimal("148.00"),
            base_amount=Decimal("148.00"),
            shipping_amount=Decimal("10.00"),
            total_amount=Decimal("148.00"),  # Should be 158.00
            currency="USD",
            cart_fingerprint="dummy",
        )
        with self.assertRaises(ValidationError):
            bad_proposal.clean()

    def test_proposal_validation_budget_exceeded(self):
        """Proposal exceeding contract max_budget raises ValidationError."""
        over_budget_proposal = PurchaseProposal(
            contract=self.contract,
            product=self.product,
            source_merchant="Amazon",
            payee_id=DEFAULT_DEMO_PAYEE_ID,
            quantity=1,
            unit_price=Decimal("155.00"),
            base_amount=Decimal("155.00"),
            total_amount=Decimal("155.00"),  # > 150.00 budget
            currency="USD",
            cart_fingerprint="dummy",
        )
        with self.assertRaises(ValidationError):
            over_budget_proposal.clean()

    def test_approval_lifecycle_happy_path(self):
        """Full happy path: PENDING -> approve() -> APPROVED -> consume() -> CONSUMED."""
        approval = PurchaseApproval.create_pending_approval(self.proposal, shopper_ip="127.0.0.1")
        self.assertEqual(approval.state, "PENDING")
        self.assertFalse(approval.is_expired())

        # Approve
        approval.approve(shopper_ip="127.0.0.1")
        self.assertEqual(approval.state, "APPROVED")
        self.assertIsNotNone(approval.approved_at)

        # Verify valid for consumption
        valid, _msg = approval.is_valid_for_consumption()
        self.assertTrue(valid)

        # Consume atomically
        approval.consume(order_reference="ORD-TEST-001")
        self.assertEqual(approval.state, "CONSUMED")
        self.assertIsNotNone(approval.consumed_at)

    def test_approval_single_use_replay_prevention(self):
        """Consuming an already consumed approval raises ApprovalAlreadyConsumedError."""
        approval = PurchaseApproval.create_pending_approval(self.proposal)
        approval.approve()
        approval.consume(order_reference="ORD-TEST-001")

        # Second consumption attempt MUST raise ApprovalAlreadyConsumedError
        with self.assertRaises(ApprovalAlreadyConsumedError):
            approval.consume(order_reference="ORD-TEST-REPLAY")

    def test_approval_expiration_ttl(self):
        """Approval past its 15-minute TTL cannot be approved or consumed."""
        approval = PurchaseApproval.create_pending_approval(self.proposal)
        # Fast-forward expiry into the past
        approval.expires_at = timezone.now() - timedelta(seconds=1)
        approval.save()

        self.assertTrue(approval.is_expired())

        with self.assertRaises(ApprovalExpiredError):
            approval.approve()

    def test_approval_voided_on_fingerprint_tamper(self):
        """If proposal price is tampered with after approval, consumption voids the token."""
        approval = PurchaseApproval.create_pending_approval(self.proposal)
        approval.approve()

        # Malicious out-of-band price alteration
        self.proposal.unit_price = Decimal("199.00")
        self.proposal.base_amount = Decimal("199.00")
        self.proposal.total_amount = Decimal("199.00")
        self.proposal.save()

        # Re-verification fails because database fingerprint no longer matches recalculated hash
        self.assertFalse(self.proposal.verify_fingerprint())

        with self.assertRaises(ApprovalInvalidError):
            approval.consume(order_reference="ORD-TAMPER")

        approval.refresh_from_db()
        self.assertEqual(approval.state, "VOIDED")

    def test_controlled_payee_disclosure_and_separation(self):
        """Ensure Channel3 source merchant and PayPal payee are distinct and carry disclosure."""
        self.assertEqual(self.proposal.source_merchant, "Amazon")
        self.assertEqual(self.proposal.payee_id, DEFAULT_DEMO_PAYEE_ID)
        self.assertNotEqual(self.proposal.source_merchant, self.proposal.payee_id)
        self.assertIn("PayPal Sandbox", DEMO_PAYEE_DISCLOSURE)
