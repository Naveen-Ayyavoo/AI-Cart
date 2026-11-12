"""Views for AI Cart Product Eligibility & Comparison Results."""

from uuid import UUID

from django.contrib import messages
from django.shortcuts import redirect, render

from catalog.views import _resolve_product_image_url
from contracts.access import resolve_contract_or_redirect
from contracts.clarifications import detect_product_profile
from policies.services import PolicyEvaluationService


def contract_evaluation(request, public_ref: str | None = None, contract_id: UUID | None = None):
    """Product eligibility & evaluation view for a confirmed PurchaseContract."""
    contract, redir = resolve_contract_or_redirect(
        request,
        public_ref=public_ref,
        contract_id=contract_id,
        canonical_view_name="contract_evaluation",
    )
    if redir:
        return redir

    # Invariant: Contract must be confirmed
    if contract.state != "CONFIRMED":
        messages.warning(
            request,
            "Please review and confirm your shopping requirements before viewing results.",
        )
        return redirect("contract_review", public_ref=contract.public_ref)

    force_refresh = request.GET.get("refresh") == "1"
    service = PolicyEvaluationService()
    reports = service.evaluate_contract_products(contract, force_refresh=force_refresh)

    profile = detect_product_profile(
        contract.category,
        contract.product_description,
        contract.raw_prompt,
    )
    is_apparel_image = profile in {"apparel_pants", "apparel_tops", "footwear"}

    rule_label_map = {
        "CurrencyMatch": "USD Currency",
        "PositivePrice": "Verified Price",
        "BudgetCeiling": "Budget Limit",
        "StockAvailability": "Availability",
        "ExcludedTerms": "Excluded Terms",
        "CategoryCompatibility": "Product Type",
        "RequiredSpecifications": "Must-Have Features",
    }

    for report in reports:
        report.display_image_url = _resolve_product_image_url(report.product)
        report.is_apparel_image = is_apparel_image
        formatted_rules = []
        for rule in (report.rule_results or []):
            if not isinstance(rule, dict):
                continue
            r_copy = dict(rule)
            r_name = rule.get("rule_name", "")
            r_copy["display_name"] = rule_label_map.get(r_name, r_name.replace("_", " "))
            formatted_rules.append(r_copy)
        report.display_rules = formatted_rules
        report.display_matched_prefs = [
            str(p).replace("_", " ").replace(":", ": ").strip()
            for p in (report.matched_preferences or [])
        ]

    eligible_reports = [r for r in reports if r.outcome == "ELIGIBLE"]
    unknown_reports = [r for r in reports if r.outcome == "UNKNOWN"]
    ineligible_reports = [r for r in reports if r.outcome == "INELIGIBLE"]

    over_budget_reports = [
        r
        for r in ineligible_reports
        if any(
            isinstance(rule, dict)
            and rule.get("rule_name") == "BudgetCeiling"
            and rule.get("outcome") == "FAIL"
            for rule in (r.rule_results or [])
        )
    ]

    context = {
        "contract": contract,
        "category_profile": profile,
        "is_apparel_image": is_apparel_image,
        "reports": reports,
        "eligible_reports": eligible_reports,
        "unknown_reports": unknown_reports,
        "ineligible_reports": ineligible_reports,
        "over_budget_count": len(over_budget_reports),
        "min_over_budget_subtotal": min((r.total_item_price for r in over_budget_reports), default=None),
        "total_count": len(reports),
    }
    return render(request, "policies/evaluation.html", context)
