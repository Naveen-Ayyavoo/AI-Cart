"""Services for AI Cart (formerly TrustCart) Phase P5: Proposal Creation, Pre-Approval Revalidation, and Approval Lifecycle.

Implements APPR-01, APPR-02, APPR-03, APPR-04, APPR-05:
- Revalidates fresh evidence, contract version, policy eligibility, and budget before proposal creation.
- Enforces separate Channel3 merchant and PayPal demo payee identities.
- Blocks approval when critical payable charges are unknown.
- Atomically transitions approval tokens using database row locks.
- Architectural invariant: Approval NEVER captures PayPal directly (capture is P6 server-side only).
"""

import logging
from decimal import Decimal
from uuid import UUID

from django.db import OperationalError

from catalog.models import ProductEvidence
from contracts.models import PurchaseContract
from orders.models import (
    DEFAULT_DEMO_PAYEE_ID,
    ApprovalError,
    ApprovalInvalidError,
    ApprovalLockError,
    PurchaseApproval,
    PurchaseProposal,
)
from policies.engine import PolicyEngine
from policies.models import PolicyEvaluationReport

logger = logging.getLogger(__name__)


class ProposalService:
    """Creates and revalidates purchase proposals."""

    @classmethod
    def create_proposal(
        cls,
        contract: PurchaseContract,
        product: ProductEvidence,
        policy_report: PolicyEvaluationReport | None = None,
        shipping_amount: Decimal = Decimal("0.00"),
        tax_amount: Decimal = Decimal("0.00"),
        fee_amount: Decimal = Decimal("0.00"),
        charges_confirmed: bool = True,
        payee_id: str = DEFAULT_DEMO_PAYEE_ID,
    ) -> tuple[PurchaseProposal, PurchaseApproval]:
        """Create a cryptographically bound PurchaseProposal and pending PurchaseApproval.

        Pre-proposal revalidations:
        - Contract must be in CONFIRMED state.
        - Product must be in IN_STOCK status.
        - Policy evaluation must be ELIGIBLE.
        - Total payable must be <= contract max_budget.
        """
        # 1. Contract state revalidation
        if contract.state != "CONFIRMED":
            raise ApprovalError(f"Contract v{contract.version} is not in CONFIRMED state (currently {contract.state}).")

        # 2. Product availability revalidation
        if product.stock_status != "IN_STOCK":
            raise ApprovalError(f"Product '{product.title}' is not in stock ({product.stock_status}).")

        # 3. Policy evaluation revalidation
        if policy_report is None:
            policy_report = PolicyEvaluationReport.objects.filter(contract=contract, product=product).first()

        if policy_report:
            if policy_report.contract_id != contract.id or policy_report.product_id != product.id:
                raise ApprovalError("Policy evaluation report does not belong to the specified contract and product.")
            if policy_report.outcome != "ELIGIBLE":
                raise ApprovalError(f"Product '{product.title}' is not ELIGIBLE under policy (status: {policy_report.outcome}).")
        else:
            # Run deterministic engine on the fly
            engine = PolicyEngine()
            result = engine.evaluate(contract, product)
            if result.outcome != "ELIGIBLE":
                raise ApprovalError(f"Product '{product.title}' failed policy validation: {result.summary}")

        # 4. Monetary calculations (Decimal only)
        quantity = contract.quantity or 1
        unit_price = product.price if isinstance(product.price, Decimal) else Decimal(str(product.price))
        base_amount = unit_price * Decimal(quantity)
        total_amount = base_amount + shipping_amount + tax_amount + fee_amount

        # 5. Budget ceiling revalidation
        if total_amount > contract.max_budget:
            raise ApprovalError(f"Total proposal amount ${total_amount} exceeds contract budget ceiling ${contract.max_budget}.")

        # 6. Build Proposal and compute cart fingerprint
        proposal = PurchaseProposal(
            contract=contract,
            product=product,
            policy_report=policy_report,
            source_merchant=product.source_merchant,
            payee_id=payee_id,
            variant_id=product.variant_id or "",
            sku=product.sku or "",
            quantity=quantity,
            unit_price=unit_price,
            base_amount=base_amount,
            shipping_amount=shipping_amount,
            tax_amount=tax_amount,
            fee_amount=fee_amount,
            total_amount=total_amount,
            currency=contract.currency or "USD",
            charges_confirmed=charges_confirmed,
            status="PROPOSED",
        )
        proposal.cart_fingerprint = proposal.calculate_fingerprint()
        proposal.full_clean()
        proposal.save()

        # 7. Create Pending Approval token bound to fingerprint
        approval = PurchaseApproval.create_pending_approval(proposal)

        return proposal, approval


class ApprovalService:
    """Manages the atomic approval and consumption lifecycle."""

    @classmethod
    def approve_proposal(
        cls,
        proposal_id: UUID,
        shopper_ip: str | None = None,
    ) -> PurchaseApproval:
        """Buyer explicitly grants approval for a proposal.

        Enforces:
        - Critical charges must be confirmed (unknown charges block approval).
        - Contract version and parameters must match fingerprint.
        - Transitions PENDING -> APPROVED.
        - Invariant: Does NOT execute PayPal capture.
        """
        proposal = PurchaseProposal.objects.select_related("contract", "product", "approval").get(id=proposal_id)

        # Gate check: Critical charges must be confirmed
        if not proposal.charges_confirmed:
            raise ApprovalInvalidError(
                "Cannot approve proposal: Critical payable charges (shipping or taxes) are unknown. "
                "Final approval is blocked until all mandatory charges are confirmed."
            )

        # Revalidate fingerprint
        if not proposal.verify_fingerprint():
            raise ApprovalInvalidError("Proposal parameters have been altered; fingerprint verification failed.")

        # Revalidate contract version and status
        if proposal.contract.state != "CONFIRMED":
            raise ApprovalInvalidError("Underlying Purchase Contract is no longer confirmed.")

        approval = proposal.approval
        approval.approve(shopper_ip=shopper_ip)
        return approval

    @classmethod
    def consume_approval(
        cls,
        token: str,
        order_reference: str = "",
    ) -> PurchaseApproval:
        """Atomically consume an approved token during checkout.

        Single-use: Replay attempts raise ApprovalAlreadyConsumedError.
        Database lock errors fail closed by raising ApprovalLockError,
        preventing repeated or accidental external operations.
        """
        try:
            approval = PurchaseApproval.objects.select_related(
                "proposal", "proposal__contract"
            ).get(token=token)
        except PurchaseApproval.DoesNotExist:
            raise ApprovalInvalidError(f"Approval token '{token}' not found.")

        try:
            approval.consume(order_reference=order_reference)
        except OperationalError as err:
            logger.warning(
                "Database lock error during approval consumption; failing closed: %s",
                err,
            )
            raise ApprovalLockError(
                f"Database lock contention prevented consumption: {err}"
            ) from err

        return approval
