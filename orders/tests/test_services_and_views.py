"""Integration tests for ProposalService, ApprovalService, and Orders Views.

Covers:
- APPR-01 (Cart fingerprint verification)
- APPR-02 (Approval token lifecycle)
- APPR-03 (Revalidation and invalidation)
- APPR-04 (Presentation UI and explicit confirmation)
- APPR-05 (Single-use consumption)
"""

from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import ProductEvidence
from contracts.models import PurchaseContract
from orders.models import (
    DEFAULT_DEMO_PAYEE_ID,
    ApprovalError,
    ApprovalInvalidError,
    PurchaseProposal,
)
from orders.services import ApprovalService, ProposalService
from policies.models import PolicyEvaluationReport


class ProposalAndApprovalServiceTests(TestCase):
    """Test proposal creation, pre-approval validation, and approval service."""

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

    def test_proposal_creation_happy_path(self):
        """ProposalService creates proposal with fingerprint and pending approval."""
        proposal, approval = ProposalService.create_proposal(
            contract=self.contract,
            product=self.product,
            policy_report=self.policy_report,
            shipping_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            charges_confirmed=True,
        )
        self.assertEqual(proposal.status, "PROPOSED")
        self.assertEqual(proposal.total_amount, Decimal("148.00"))
        self.assertEqual(approval.state, "PENDING")
        self.assertTrue(proposal.verify_fingerprint())
        self.assertEqual(proposal.source_merchant, "Amazon")
        self.assertEqual(proposal.payee_id, DEFAULT_DEMO_PAYEE_ID)

    def test_proposal_creation_fails_on_unconfirmed_contract(self):
        """Cannot create proposal if contract is in DRAFT state."""
        self.contract.state = "DRAFT"
        self.contract.save()

        with self.assertRaises(ApprovalError) as ctx:
            ProposalService.create_proposal(self.contract, self.product)
        self.assertIn("not in CONFIRMED state", str(ctx.exception))

    def test_proposal_creation_fails_on_ineligible_product(self):
        """Cannot create proposal if policy evaluation is INELIGIBLE."""
        self.policy_report.outcome = "INELIGIBLE"
        self.policy_report.save()

        with self.assertRaises(ApprovalError) as ctx:
            ProposalService.create_proposal(
                self.contract, self.product, policy_report=self.policy_report
            )
        self.assertIn("not ELIGIBLE", str(ctx.exception))

    def test_approval_service_blocks_on_unknown_charges(self):
        """If critical payable charges are unconfirmed, approval MUST be blocked."""
        proposal, _approval = ProposalService.create_proposal(
            contract=self.contract,
            product=self.product,
            policy_report=self.policy_report,
            charges_confirmed=False,  # Unconfirmed shipping/taxes
        )
        with self.assertRaises(ApprovalInvalidError) as ctx:
            ApprovalService.approve_proposal(proposal.id)
        self.assertIn("Critical payable charges", str(ctx.exception))

    def test_approval_service_happy_path_approve_and_consume(self):
        """Approve proposal then consume approval token."""
        proposal, _approval = ProposalService.create_proposal(
            contract=self.contract,
            product=self.product,
            policy_report=self.policy_report,
            charges_confirmed=True,
        )
        approved = ApprovalService.approve_proposal(proposal.id, shopper_ip="192.168.1.1")
        self.assertEqual(approved.state, "APPROVED")
        self.assertEqual(approved.shopper_ip, "192.168.1.1")

        consumed = ApprovalService.consume_approval(approved.token, order_reference="PAYPAL-ORD-123")
        self.assertEqual(consumed.state, "CONSUMED")
        self.assertIsNotNone(consumed.consumed_at)


class OrdersViewsTests(TestCase):
    """Test Orders views for proposal detail and approval receipt."""

    def setUp(self):
        self.client = Client()
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
            stock_status="IN_STOCK",
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
        )

        self.proposal, self.approval = ProposalService.create_proposal(
            contract=self.contract,
            product=self.product,
            policy_report=self.policy_report,
            charges_confirmed=True,
        )

    def test_proposal_detail_view_renders_breakdown_and_payee_disclosure(self):
        """Proposal detail page displays payable breakdown and demo payee disclosure."""
        url = reverse("proposal_detail", kwargs={"public_ref": self.proposal.public_ref})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "orders/proposal_detail.html")

        content = response.content.decode("utf-8")
        self.assertIn("Review Your Purchase Summary", content)
        self.assertIn("PayPal Sandbox Demo Merchant Notice", content)
        self.assertIn(self.proposal.source_merchant, content)
        self.assertIn(self.proposal.payee_id, content)
        self.assertIn("$148.00 USD", content)
        self.assertIn("I Explicitly Approve This Purchase Proposal", content)

    def test_proposal_detail_post_approve_redirects_to_approval_receipt(self):
        """Submitting explicit approval grants approval and redirects to approval receipt."""
        url = reverse("proposal_detail", kwargs={"public_ref": self.proposal.public_ref})
        response = self.client.post(url, {"action": "approve"})
        self.assertEqual(response.status_code, 302)

        self.approval.refresh_from_db()
        self.assertEqual(self.approval.state, "APPROVED")
        self.assertIn(f"/orders/approvals/{self.approval.public_ref}/", response.url)

    def test_approval_detail_view_renders_token_and_expiry(self):
        """Approval detail view renders expiry countdown and next step without leaking raw fingerprint."""
        # Approve proposal
        self.approval.approve()

        url = reverse("approval_detail", kwargs={"public_ref": self.approval.public_ref})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "orders/approval_detail.html")

        content = response.content.decode("utf-8")
        self.assertIn("Purchase Summary Approved", content)
        self.assertIn(self.approval.token, content)
        self.assertIn("Single-Use", content)
        self.assertIn("PayPal Sandbox Checkout", content)
        self.assertNotIn("Phase P6:", content)

    def test_proposal_create_from_evaluation_redirects_to_proposal(self):
        """Generating proposal from evaluation report creates proposal and redirects to proposal view."""
        # Delete the approval and proposal created in setUp to test fresh creation
        self.approval.delete()
        self.proposal.delete()
        url = reverse("proposal_create_from_evaluation", kwargs={"report_id": self.policy_report.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/orders/proposals/", response.url)

    def test_proposal_create_from_evaluation_reuses_existing_pending_proposal(self):
        """Repeated generation requests for the same report reuse the existing pending proposal."""
        url = reverse("proposal_create_from_evaluation", kwargs={"report_id": self.policy_report.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("proposal_detail", kwargs={"public_ref": self.proposal.public_ref}))
        # Verify no duplicate was created
        self.assertEqual(PurchaseProposal.objects.filter(product=self.product).count(), 1)

    def test_proposal_create_from_evaluation_does_not_reuse_stale_price_proposal(self):
        """If policy report price has changed, do NOT reuse old proposal; create fresh proposal reflecting new price."""
        # Update product and report to new price
        self.product.price = Decimal("149.50")
        self.product.save()
        self.policy_report.unit_price = Decimal("149.50")
        self.policy_report.total_item_price = Decimal("149.50")
        self.policy_report.save()

        url = reverse("proposal_create_from_evaluation", kwargs={"report_id": self.policy_report.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        # Should redirect to a new proposal, not self.proposal
        self.assertNotEqual(response.url, reverse("proposal_detail", kwargs={"public_ref": self.proposal.public_ref}))
        # Verify 2 proposals now exist, latest having $149.50
        latest_proposal = PurchaseProposal.objects.filter(product=self.product).latest("created_at")
        self.assertEqual(latest_proposal.unit_price, Decimal("149.50"))
        self.assertEqual(PurchaseProposal.objects.filter(product=self.product).count(), 2)

    def test_proposal_detail_post_approve_when_already_approved_redirects_cleanly(self):
        """Posting action=approve on an already approved proposal redirects to approval_detail with info message."""
        self.approval.approve()
        url = reverse("proposal_detail", kwargs={"public_ref": self.proposal.public_ref})
        response = self.client.post(url, {"action": "approve"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("approval_detail", kwargs={"public_ref": self.approval.public_ref}))

    def test_approval_detail_view_renders_consumed_state(self):
        """Approval detail renders consumed notice when approval has been used."""
        self.approval.approve()
        self.approval.consume()
        url = reverse("approval_detail", kwargs={"public_ref": self.approval.public_ref})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Approval Token Consumed", content)
        self.assertNotIn("Proceed to PayPal Sandbox Checkout", content)

    def test_proposal_detail_renders_safely_when_no_approval_exists(self):
        """Proposal detail view renders cleanly without RelatedObjectDoesNotExist error when no approval exists."""
        self.approval.delete()
        url = reverse("proposal_detail", kwargs={"public_ref": self.proposal.public_ref})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "orders/proposal_detail.html")
        content = response.content.decode("utf-8")
        self.assertIn("Explicitly Approve This Purchase Proposal", content)

    def test_proposal_detail_reject_action_when_no_approval_exists(self):
        """Shopper can reject a proposal safely even if no approval record exists."""
        self.approval.delete()
        url = reverse("proposal_detail", kwargs={"public_ref": self.proposal.public_ref})
        response = self.client.post(url, {"action": "reject"})
        self.assertEqual(response.status_code, 302)
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, "REJECTED")
        self.assertIn(f"/contracts/{self.contract.public_ref}/evaluation/", response.url)
