"""Views for AI Cart (formerly TrustCart) Phase P5: Purchase Proposal Review, Explicit Buyer Confirmation, and Approval Receipt."""

from decimal import Decimal
from uuid import UUID

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from contracts.access import authorize_contract_access, redirect_canonical
from orders.models import (
    DEMO_PAYEE_DISCLOSURE,
    ApprovalError,
    PurchaseApproval,
    PurchaseProposal,
)
from orders.services import ApprovalService, ProposalService
from policies.models import PolicyEvaluationReport


def _get_client_ip(request) -> str:
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "127.0.0.1")


def proposal_create_from_evaluation(request, report_id: UUID):
    """Create a structured PurchaseProposal and pending approval from an ELIGIBLE policy report."""
    report = get_object_or_404(
        PolicyEvaluationReport.objects.select_related("contract", "product"),
        id=report_id,
    )
    authorize_contract_access(request, report.contract)

    if report.outcome != "ELIGIBLE":
        messages.error(
            request,
            f"Cannot prepare purchase summary: Product '{report.product.title}' does not meet all requirements ({report.outcome}).",
        )
        return redirect("contract_evaluation", public_ref=report.contract.public_ref)

    if report.contract.state != "CONFIRMED":
        messages.error(
            request,
            "Please confirm your shopping requirements before selecting a product.",
        )
        return redirect("contract_review", public_ref=report.contract.public_ref)

    # Re-use existing unexpired pending proposal for this contract and product
    existing = (
        PurchaseProposal.objects.select_related("approval")
        .filter(contract=report.contract, product=report.product, status="PROPOSED")
        .order_by("-created_at")
        .first()
    )
    if (
        existing
        and hasattr(existing, "approval")
        and existing.approval
        and existing.approval.state == "PENDING"
        and not existing.approval.is_expired()
        and existing.unit_price == report.unit_price
        and existing.base_amount == report.total_item_price
        and existing.verify_fingerprint()
    ):
        return redirect("proposal_detail", public_ref=existing.public_ref)

    # In our verified zero-spend demo, standard free shipping and 0 tax are confirmed
    proposal, _approval = ProposalService.create_proposal(
        contract=report.contract,
        product=report.product,
        policy_report=report,
        shipping_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        fee_amount=Decimal("0.00"),
        charges_confirmed=True,
    )

    return redirect("proposal_detail", public_ref=proposal.public_ref)


def proposal_detail(request, public_ref: str | None = None, proposal_id: UUID | None = None):
    """Proposal presentation view requiring explicit positive buyer confirmation."""
    if public_ref is not None:
        proposal = get_object_or_404(
            PurchaseProposal.objects.select_related("contract", "product"),
            public_ref=public_ref,
        )
        authorize_contract_access(request, proposal.contract)
    else:
        proposal = get_object_or_404(
            PurchaseProposal.objects.select_related("contract", "product"),
            id=proposal_id,
        )
        authorize_contract_access(request, proposal.contract)
        if request.method == "GET":
            return redirect_canonical(request, "proposal_detail", proposal.public_ref)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "approve":
            # If already approved and not expired, redirect directly to approval detail
            existing_approval = getattr(proposal, "approval", None)
            if (
                existing_approval
                and existing_approval.state == "APPROVED"
                and not existing_approval.is_expired()
            ):
                messages.info(request, "This purchase selection is already approved.")
                return redirect("approval_detail", public_ref=existing_approval.public_ref)

            try:
                ip = _get_client_ip(request)
                approval = ApprovalService.approve_proposal(proposal.id, shopper_ip=ip)
                messages.success(request, "Purchase summary confirmed and ready for PayPal Sandbox.")
                return redirect("approval_detail", public_ref=approval.public_ref)
            except ApprovalError as e:
                messages.error(request, f"Approval failed: {e!s}")
        elif action == "reject":
            approval = getattr(proposal, "approval", None)
            if approval:
                approval.state = "REJECTED"
                approval.append_audit_event("REJECTED", "Shopper explicitly rejected the proposed purchase.")
                approval.save()
            proposal.status = "REJECTED"
            proposal.save()
            messages.info(request, "Purchase selection cancelled.")
            return redirect("contract_evaluation", public_ref=proposal.contract.public_ref)

    latest_contract = (
        proposal.contract.revisions.order_by("-version").first()
        if proposal.contract.state == "SUPERSEDED"
        else None
    )
    context = {
        "proposal": proposal,
        "approval": getattr(proposal, "approval", None),
        "contract": proposal.contract,
        "latest_contract": latest_contract,
        "product": proposal.product,
        "demo_payee_disclosure": DEMO_PAYEE_DISCLOSURE,
    }
    return render(request, "orders/proposal_detail.html", context)


def approval_detail(request, public_ref: str | None = None, approval_id: UUID | None = None):
    """Displays locked purchase approval summary and readiness for PayPal Sandbox checkout."""
    if public_ref is not None:
        approval = get_object_or_404(
            PurchaseApproval.objects.select_related("proposal", "proposal__contract", "proposal__product"),
            public_ref=public_ref,
        )
        authorize_contract_access(request, approval.proposal.contract)
    else:
        approval = get_object_or_404(
            PurchaseApproval.objects.select_related("proposal", "proposal__contract", "proposal__product"),
            id=approval_id,
        )
        authorize_contract_access(request, approval.proposal.contract)
        if request.method == "GET":
            return redirect_canonical(request, "approval_detail", approval.public_ref)

    payment_order = getattr(approval, "payment_order", None)
    latest_contract = (
        approval.proposal.contract.revisions.order_by("-version").first()
        if approval.proposal.contract.state == "SUPERSEDED"
        else None
    )

    context = {
        "approval": approval,
        "proposal": approval.proposal,
        "contract": approval.proposal.contract,
        "latest_contract": latest_contract,
        "product": approval.proposal.product,
        "payment_order": payment_order,
        "is_expired": approval.is_expired(),
        "demo_payee_disclosure": DEMO_PAYEE_DISCLOSURE,
    }
    return render(request, "orders/approval_detail.html", context)
