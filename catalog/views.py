"""Catalog views for AI Cart: Product Discovery, Decision Assistance & Side-by-Side Comparison."""

from decimal import Decimal
from uuid import UUID

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from catalog.client import extract_valid_image_url, is_valid_http_image_url
from catalog.models import ProductEvidence
from catalog.services import ProductSearchService
from contracts.access import resolve_contract_or_redirect
from contracts.clarifications import detect_product_profile
from contracts.interpreter import format_spec_label, format_spec_value
from contracts.models import PurchaseContract
from orders.models import ApprovalError, PurchaseProposal
from orders.services import ProposalService
from policies.engine import PolicyEngine
from policies.models import PolicyEvaluationReport


def _resolve_product_image_url(product: ProductEvidence) -> str:
    """Return validated http/https image URL from product evidence, or '' if missing/invalid."""
    direct = (product.image_url or "").strip()
    if is_valid_http_image_url(direct):
        return direct
    if isinstance(product.raw_evidence, dict):
        return extract_valid_image_url(product.raw_evidence)
    return ""


def _extract_product_highlights(
    product: ProductEvidence,
    contract: PurchaseContract,
    policy_engine: PolicyEngine,
) -> dict:
    """Computes deterministic policy fit, budget remaining, trade-offs, and key attributes for a product.

    Invariants:
    - Item Subtotal = unit_price * quantity
    - Budget Remaining (Items Only) = contract.max_budget - item_subtotal
    - All monetary arithmetic uses Decimal.
    - Base item price is not conflated with shipping or tax (which remain UNCONFIRMED).
    - Trade-offs are derived strictly from contract constraints vs evidence, never fabricated.
    - Missing attributes or invalid image URLs remain unlisted/placeholder rather than guessed.
    """
    eval_res = policy_engine.evaluate(contract, product)
    quantity = contract.quantity or 1
    unit_price = product.price if isinstance(product.price, Decimal) else Decimal(str(product.price or "0.00"))
    item_subtotal = unit_price * Decimal(quantity)

    # Correct budget basis: contract.max_budget represents the total item budget ceiling for the purchase
    budget_remaining = contract.max_budget - item_subtotal

    # Extract verified key attributes only from product evidence using readable labels/values
    features = {}
    if isinstance(product.raw_evidence, dict):
        raw_feat = product.raw_evidence.get("features", {})
        if isinstance(raw_feat, dict):
            for k, v in raw_feat.items():
                if v is not None and str(v).strip():
                    clean_k = format_spec_label(str(k))
                    features[clean_k] = format_spec_value(str(k), str(v).strip())

    # If raw features are absent, use verified model attributes rather than guessing
    if not features:
        if product.brand:
            features["Brand"] = product.brand
        if product.stock_status:
            features["Availability"] = product.stock_status.replace("_", " ").title()

    is_over_budget = any(
        r.rule_name == "BudgetCeiling" and r.outcome == "FAIL"
        for r in eval_res.rule_results
    )
    is_incompatible = any(
        r.rule_name == "CategoryCompatibility" and r.outcome == "FAIL"
        for r in eval_res.rule_results
    )
    is_out_of_stock = product.stock_status == "OUT_OF_STOCK"
    has_blocking_safety_failure = any(
        r.rule_name in ("PositivePrice", "CurrencyMatch", "StockAvailability", "CategoryCompatibility")
        and r.outcome == "FAIL"
        for r in eval_res.rule_results
    )
    can_buy_anyway = eval_res.outcome in ("UNKNOWN", "INELIGIBLE") and not has_blocking_safety_failure

    if eval_res.outcome == "ELIGIBLE":
        status_label = "Meets requirements"
        warning_headline = ""
    elif is_incompatible:
        status_label = "Incompatible product"
        warning_headline = "Does not match the requested product type."
    elif eval_res.outcome == "UNKNOWN":
        status_label = "Needs verification"
        warning_headline = "One or more required features could not be verified."
    else:
        status_label = "Conflicts with requirements"
        warning_headline = "This product conflicts with one or more of your requirements."

    if is_incompatible:
        unavailable_label = "Incompatible Product"
    elif is_out_of_stock:
        unavailable_label = "Out of Stock"
    else:
        unavailable_label = "Unavailable"

    def _humanize_pref_list(entries: list[str]) -> list[str]:
        formatted = []
        for entry in entries or []:
            text = str(entry)
            if ":" in text:
                raw_k, raw_v = text.split(":", 1)
                formatted.append(f"{format_spec_label(raw_k)}: {format_spec_value(raw_k, raw_v)}")
            else:
                formatted.append(text)
        return formatted

    def _humanize_summary(text: str) -> str:
        clean = str(text or "")
        for raw_k in ("noise_cancelling", "noise_canceling", "form_factor", "battery_life", "connectivity", "color"):
            label = format_spec_label(raw_k)
            clean = clean.replace(f"'{raw_k}:", f"'{label}:").replace(f"{raw_k}:", f"{label}:")
        return clean

    # Grounded trade-off derivation (strictly evidence-based)
    if eval_res.outcome in ("INELIGIBLE", "UNKNOWN"):
        tradeoff = _humanize_summary(eval_res.summary)
    elif eval_res.missed_preferences:
        tradeoff = f"Lacks preferred: {', '.join(eval_res.missed_preferences)}"
    elif budget_remaining == Decimal("0.00"):
        tradeoff = "At maximum item budget ceiling ($0.00 item buffer)"
    else:
        tradeoff = "None identified against requirements (shipping & tax unconfirmed)"

    # Grounded match rationale (never describing budget buffer as savings or final total)
    if eval_res.outcome == "ELIGIBLE":
        if budget_remaining > Decimal("0.00"):
            match_reason = f"${budget_remaining:.2f} item budget remaining · Meets all required specs"
        elif budget_remaining == Decimal("0.00"):
            match_reason = "At exact item budget ceiling · Meets all required specs"
        else:
            match_reason = "Meets all required specs"
        if eval_res.matched_preferences:
            match_reason += f" (Matches: {', '.join(_humanize_pref_list(eval_res.matched_preferences))})"
    else:
        match_reason = _humanize_summary(eval_res.summary)

    return {
        "product": product,
        "image_url": _resolve_product_image_url(product),
        "eval_result": eval_res,
        "outcome": eval_res.outcome,
        "status_label": status_label,
        "warning_headline": warning_headline,
        "is_eligible": eval_res.outcome == "ELIGIBLE" and not is_incompatible,
        "is_compatible": not is_incompatible,
        "is_incompatible": is_incompatible,
        "is_over_budget": is_over_budget,
        "can_buy_anyway": can_buy_anyway,
        "unavailable_label": unavailable_label,
        "unit_price": unit_price,
        "quantity": quantity,
        "item_subtotal": item_subtotal,
        "total_price": item_subtotal,
        "budget_remaining": budget_remaining,
        "savings": budget_remaining,
        "shipping_status": "UNCONFIRMED",
        "tax_status": "UNCONFIRMED",
        "features": features,
        "key_specs": list(features.items())[:3],
        "match_reason": match_reason,
        "tradeoff": tradeoff,
        "is_fixture": bool(product.is_fixture),
        "distinctions": [],
        "badge": "",
    }


def contract_discovery(request, public_ref: str | None = None, contract_id: UUID | None = None):
    """Product discovery, decision assistance, and comparison view for a confirmed PurchaseContract."""
    contract, redir = resolve_contract_or_redirect(
        request,
        public_ref=public_ref,
        contract_id=contract_id,
        canonical_view_name="contract_discovery",
    )
    if redir:
        return redir

    # Invariant: Contract must be confirmed before initiating product discovery
    if contract.state != "CONFIRMED":
        messages.warning(
            request,
            "Please review and confirm your shopping requirements before viewing product matches.",
        )
        return redirect("contract_review", public_ref=contract.public_ref)

    force_refresh = request.GET.get("refresh") == "1"
    search_service = ProductSearchService()
    products, is_fallback, status_message = search_service.search_for_contract(
        contract, force_refresh=force_refresh
    )

    policy_engine = PolicyEngine()
    decorated_items = [
        _extract_product_highlights(p, contract, policy_engine)
        for p in products
    ]

    # Sort deterministically: ELIGIBLE first (lowest subtotal), then UNKNOWN, then overridable INELIGIBLE, then incompatible
    outcome_rank = {"ELIGIBLE": 0, "UNKNOWN": 1, "INELIGIBLE": 2}
    decorated_items.sort(
        key=lambda it: (
            1 if it["is_incompatible"] else 0,
            outcome_rank.get(it["outcome"], 3),
            -it["eval_result"].preference_score if it["is_eligible"] else 0,
            it["item_subtotal"],
        )
    )

    # Grounded distinction assignment: ONLY truly compatible & eligible within-budget products
    eligible_items = [item for item in decorated_items if item["is_eligible"] and item["is_compatible"]]
    if eligible_items:
        min_subtotal = min(it["item_subtotal"] for it in eligible_items)
        for it in eligible_items:
            if it["item_subtotal"] == min_subtotal:
                it["distinctions"].append("Lowest Item Subtotal")

        pref_scores = [it["eval_result"].preference_score for it in eligible_items]
        max_pref = max(pref_scores) if pref_scores else 0
        if max_pref > 0:
            for it in eligible_items:
                if it["eval_result"].preference_score == max_pref:
                    it["distinctions"].append("Best Preference Match")

    for idx, item in enumerate(decorated_items):
        item["index"] = idx
        if item["is_incompatible"]:
            item["distinctions"] = ["Incompatible"]
        elif item["outcome"] == "UNKNOWN":
            item["distinctions"] = ["Needs Verification"]
        elif not item["is_eligible"]:
            item["distinctions"] = ["Ineligible"]
        item["badge"] = " & ".join(item["distinctions"]) if item["distinctions"] else ""

    over_budget_items = [it for it in decorated_items if it["is_over_budget"]]
    min_over_budget_subtotal = min(
        (it["item_subtotal"] for it in over_budget_items),
        default=None,
    )

    # Strict separation: eligible within-budget matches vs over-budget/unverified vs incompatible/unavailable
    shortlist_items = eligible_items[:3]
    over_budget_and_conflict_items = [
        it for it in decorated_items if not it["is_eligible"] and it["can_buy_anyway"]
    ]
    visible_conflict_items = over_budget_and_conflict_items[:3]
    incompatible_items = [
        it for it in decorated_items if not it["is_eligible"] and not it["can_buy_anyway"]
    ]
    additional_items = (
        eligible_items[3:]
        + over_budget_and_conflict_items[3:]
        + incompatible_items
    )

    profile = detect_product_profile(
        contract.category,
        contract.product_description,
        contract.raw_prompt,
    )
    context = {
        "contract": contract,
        "category_profile": profile,
        "is_apparel_image": profile in {"apparel_pants", "apparel_tops", "footwear"},
        "products": products,
        "decorated_items": decorated_items,
        "shortlist_items": shortlist_items,
        "visible_conflict_items": visible_conflict_items,
        "additional_items": additional_items,
        "eligible_count": len(eligible_items),
        "over_budget_count": len(over_budget_items),
        "incompatible_count": len(incompatible_items),
        "min_over_budget_subtotal": min_over_budget_subtotal,
        "is_fallback": is_fallback,
        "status_message": status_message,
    }
    return render(request, "catalog/product_list.html", context)


def contract_select_product(request, public_ref: str, product_id: str):
    """Select an eligible product directly from Discovery and proceed to Purchase Summary.

    Runs full deterministic backend PolicyEngine evaluation and persists an authoritative
    PolicyEvaluationReport before calling ProposalService.create_proposal, bypassing any
    unnecessary intermediate evaluation detour while preserving every safety & approval gate.
    """
    contract, redir = resolve_contract_or_redirect(
        request,
        public_ref=public_ref,
        canonical_view_name="contract_discovery",
    )
    if redir:
        return redir

    if request.method != "POST":
        return redirect("contract_discovery", public_ref=contract.public_ref)

    if contract.state != "CONFIRMED":
        messages.warning(
            request,
            "Please review and confirm your shopping requirements before selecting a product.",
        )
        return redirect("contract_review", public_ref=contract.public_ref)

    product = get_object_or_404(ProductEvidence, product_id=product_id)
    eval_res = PolicyEngine().evaluate(contract, product)
    report = PolicyEvaluationReport.objects.create(
        contract=contract,
        product=product,
        outcome=eval_res.outcome,
        unit_price=eval_res.unit_price,
        quantity=eval_res.quantity,
        total_item_price=eval_res.total_item_price,
        budget_ceiling=eval_res.budget_ceiling,
        currency=eval_res.currency,
        preference_score=eval_res.preference_score,
        matched_preferences=eval_res.matched_preferences,
        missed_preferences=eval_res.missed_preferences,
        rule_results=[r.to_dict() for r in eval_res.rule_results],
        summary=eval_res.summary,
        shipping_tax_disclosure=eval_res.shipping_tax_disclosure,
    )

    if eval_res.outcome != "ELIGIBLE":
        has_blocking_failure = any(
            r.rule_name in ("PositivePrice", "CurrencyMatch", "StockAvailability", "CategoryCompatibility")
            and r.outcome == "FAIL"
            for r in eval_res.rule_results
        )
        if not has_blocking_failure:
            return redirect("contract_buy_anyway", public_ref=contract.public_ref, product_id=product.product_id)
        messages.error(
            request,
            f"Cannot select '{product.title}': {eval_res.summary}",
        )
        return redirect("contract_discovery", public_ref=contract.public_ref)

    existing = (
        PurchaseProposal.objects.select_related("approval")
        .filter(contract=contract, product=product, status="PROPOSED")
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

    try:
        proposal, _approval = ProposalService.create_proposal(
            contract=contract,
            product=product,
            policy_report=report,
            shipping_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            fee_amount=Decimal("0.00"),
            charges_confirmed=True,
        )
        return redirect("proposal_detail", public_ref=proposal.public_ref)
    except ApprovalError as exc:
        messages.error(request, f"Unable to prepare purchase summary: {exc!s}")
        return redirect("contract_discovery", public_ref=contract.public_ref)
