"""
Views for Purchase Contract intent intake, review, granular editing,
optional category-aware clarification, budget revision, and confirmation.

Phase P2 + UX Defect Resolution Invariants:
- Contract confirmation locks requirements for product discovery; it is NOT payment authorization.
- Confirmed contracts are immutable: edits or budget revisions create a new draft version.
- Every sample demo follows the unified Purchase Contract review -> confirmation -> discovery flow.
- Prominent disclosure of demo fixtures when offline or quota exhausted.
"""

from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from contracts.access import ensure_session_key, resolve_contract_or_redirect
from contracts.clarifications import (
    build_clarification_fields,
    build_edit_criteria_metadata,
    sanitize_clarification_text,
)
from contracts.fixtures import DEMO_SCENARIOS, FALLBACK_DISCLOSURE, get_demo_scenario
from contracts.forms import BudgetRevisionForm, ContractReviewForm, PromptIntakeForm
from contracts.gemini import GeminiContractClient
from contracts.interpreter import (
    detect_contract_contradictions,
    format_spec_label,
    format_spec_value,
    format_specs_display,
)
from contracts.models import ContractSource, ContractState, PurchaseContract


def _scenario_list() -> list[dict[str, str]]:
    return [
        {"key": k, "title": v["title"], "prompt": v["prompt"]}
        for k, v in DEMO_SCENARIOS.items()
    ]


def _build_review_context(
    contract: PurchaseContract,
    form: ContractReviewForm | None = None,
    clarification_errors: dict[str, str] | None = None,
) -> dict:
    is_demo_sample = contract.source == ContractSource.DEMO_FIXTURE
    is_parse_fallback = contract.source == ContractSource.FALLBACK_PARSER
    provenance = contract.extraction_provenance or {}
    fallback_disclosure = provenance.get("disclosure", FALLBACK_DISCLOSURE) if is_demo_sample else ""
    contradictions = detect_contract_contradictions(contract)
    return {
        "contract": contract,
        "form": form or ContractReviewForm(instance=contract),
        "is_fallback": is_demo_sample,
        "is_demo_sample": is_demo_sample,
        "is_parse_fallback": is_parse_fallback,
        "fallback_disclosure": fallback_disclosure,
        "fallback_reason": provenance.get("fallback_reason", ""),
        "contradictions": contradictions,
        "buy_anyway_ack": provenance.get("buy_anyway_acknowledgment"),
        "display_required_specs": format_specs_display(contract.required_specs),
        "display_preferred_specs": format_specs_display(contract.preferred_specs),
        "scenarios": [{"key": k, "title": v["title"]} for k, v in DEMO_SCENARIOS.items()],
        "clarification_fields": build_clarification_fields(contract),
        "clarification_errors": clarification_errors or {},
        "edit_metadata": build_edit_criteria_metadata(contract),
        "last_revision": provenance.get("last_revision"),
    }


def _extract_clarification_updates(
    post_data,
    contract: PurchaseContract,
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Parse and validate optional clarification inputs against category metadata.

    Returns (updated_preferred_specs, updated_required_specs, field_errors).
    Never silently converts optional preferences into hard constraints.
    """
    fields = build_clarification_fields(contract)
    preferred = dict(contract.preferred_specs or {})
    required = dict(contract.required_specs or {})
    errors: dict[str, str] = {}

    for field in fields:
        raw_val = post_data.get(field["field_name"], "")
        val = sanitize_clarification_text(str(raw_val))

        if val == "Other":
            custom_raw = post_data.get(field["custom_field_name"], "")
            val = sanitize_clarification_text(str(custom_raw))

        # Only process if shopper entered/selected a value for this optional field
        if not val:
            continue

        if field["control_type"] == "number":
            try:
                num_val = Decimal(val)
                min_v = Decimal(str(field["min"])) if field.get("min") else Decimal("0.01")
                max_v = Decimal(str(field["max"])) if field.get("max") else Decimal(100000)
                if num_val < min_v or num_val > max_v:
                    errors[field["key"]] = f"Enter a value between {min_v} and {max_v}."
                    continue
                unit = field.get("unit", "").strip()
                formatted_num = str(num_val.normalize())
                val = f"{formatted_num} {unit}".strip() if unit else formatted_num
            except InvalidOperation:
                errors[field["key"]] = "Please enter a valid number."
                continue

        make_required = post_data.get(field["requirement_toggle_name"]) == "on"
        spec_key = field["key"]
        if make_required:
            required[spec_key] = val
            preferred.pop(spec_key, None)
        else:
            if spec_key in required and not post_data.get(f"clarify_present__{spec_key}"):
                required[spec_key] = val
            else:
                preferred[spec_key] = val

    return preferred, required, errors


@require_GET
def home_view(request):
    """AI Cart home page: natural language intent intake form & sample scenarios."""
    form = PromptIntakeForm()
    return render(
        request,
        "home.html",
        {
            "form": form,
            "scenarios": _scenario_list(),
        },
    )


@require_http_methods(["POST"])
def contract_create(request):
    """
    Parses shopper intent into a structured Purchase Contract (DRAFT).
    - Sample demo scenarios route through the unified Purchase Contract review page.
    - If a user selected a chip earlier, navigated back, and edited the prompt,
      their edited prompt is evaluated normally rather than loading a stale fixture.
    """
    form = PromptIntakeForm(request.POST)
    scenario_key = request.POST.get("scenario_key", "").strip()
    submitted_prompt = request.POST.get("prompt", "").strip()

    is_exact_demo_request = (
        scenario_key in DEMO_SCENARIOS
        and (
            not submitted_prompt
            or submitted_prompt == DEMO_SCENARIOS[scenario_key]["prompt"].strip()
        )
    )

    if is_exact_demo_request:
        contract = get_demo_scenario(scenario_key, save_to_db=False)
        if submitted_prompt and form.is_valid():
            max_budget = form.cleaned_data.get("max_budget")
            quantity = form.cleaned_data.get("quantity")
            excluded_raw = form.cleaned_data.get("excluded_terms", "")
            if max_budget:
                contract.max_budget = max_budget
            if quantity and quantity > 1:
                contract.quantity = quantity
            if excluded_raw:
                extra_excl = [t.strip() for t in excluded_raw.split(",") if t.strip()]
                existing_low = {t.lower() for t in contract.excluded_terms}
                for term in extra_excl:
                    if term.lower() not in existing_low:
                        contract.excluded_terms.append(term)
                        existing_low.add(term.lower())
        contract.owner_session_key = ensure_session_key(request)
        contract.full_clean()
        contract.save()
        return redirect("contract_review", public_ref=contract.public_ref)

    if not form.is_valid():
        return render(
            request,
            "home.html",
            {
                "form": form,
                "scenarios": _scenario_list(),
            },
            status=400,
        )

    prompt = form.cleaned_data["prompt"]
    max_budget = form.cleaned_data.get("max_budget")
    excluded_terms_raw = form.cleaned_data.get("excluded_terms")
    quantity = form.cleaned_data.get("quantity")

    extra_parts = []
    if max_budget:
        extra_parts.append(f"budget under ${max_budget}")
    if excluded_terms_raw:
        extra_parts.append(f"exclude {excluded_terms_raw}")
    if quantity and quantity > 1:
        extra_parts.append(f"quantity: {quantity}")

    full_prompt = prompt
    if extra_parts:
        full_prompt = f"{prompt} ({', '.join(extra_parts)})"[:2000]

    client = GeminiContractClient()

    try:
        contract, is_fallback, _status_msg = client.extract_contract(
            full_prompt, save_to_db=True
        )
        updated_fields = ["owner_session_key", "raw_prompt"]
        # Always preserve the shopper's unmodified original wording cleanly
        contract.raw_prompt = prompt
        contract.owner_session_key = ensure_session_key(request)
        if max_budget and contract.max_budget != max_budget:
            contract.max_budget = max_budget
            updated_fields.append("max_budget")
        if quantity and quantity > 1 and contract.quantity != quantity:
            contract.quantity = quantity
            updated_fields.append("quantity")
        if excluded_terms_raw:
            extra_excl = [t.strip() for t in excluded_terms_raw.split(",") if t.strip()]
            merged_excl = list(contract.excluded_terms or [])
            seen = {str(x).lower() for x in merged_excl}
            for t in extra_excl:
                if t.lower() not in seen:
                    merged_excl.append(t)
                    seen.add(t.lower())
            contract.excluded_terms = merged_excl
            updated_fields.append("excluded_terms")
        if contract.source == ContractSource.FALLBACK_PARSER and (max_budget or quantity):
            prov = dict(contract.extraction_provenance or {})
            if max_budget:
                prov["budget_explicitly_stated"] = True
            contract.extraction_provenance = prov
            updated_fields.append("extraction_provenance")
        contract.save(update_fields=updated_fields)

        if not is_fallback:
            messages.success(request, "Shopping requirements prepared cleanly. Please review before confirming.")
        return redirect("contract_review", public_ref=contract.public_ref)
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"Error processing shopping request: {exc!s}")
        return redirect("home")


@require_GET
def contract_review(request, public_ref: str | None = None, contract_id: UUID | None = None):
    """
    Review and granular editing interface for Purchase Contract.
    Allows optional clarification, editing category-appropriate criteria, and explicit confirmation.
    """
    contract, redir = resolve_contract_or_redirect(
        request,
        public_ref=public_ref,
        contract_id=contract_id,
        canonical_view_name="contract_review",
    )
    if redir:
        return redir
    return render(
        request,
        "contracts/review.html",
        _build_review_context(contract),
    )


@require_POST
def contract_clarify(request, public_ref: str | None = None, contract_id: UUID | None = None):
    """
    Server-validated handler for "Optional details to improve your results".
    Saves optional details cleanly as preferred_specs (never silently creating hard constraints).
    If contract is CONFIRMED, creates a new DRAFT version cleanly.
    """
    contract, _ = resolve_contract_or_redirect(
        request,
        public_ref=public_ref,
        contract_id=contract_id,
        canonical_view_name="contract_review",
    )

    if contract.state == ContractState.SUPERSEDED:
        messages.error(request, "This contract version has been superseded. Please use the latest version.")
        latest = contract.revisions.order_by("-version").first()
        if latest:
            return redirect("contract_review", public_ref=latest.public_ref)
        return redirect("home")

    preferred, required, errors = _extract_clarification_updates(request.POST, contract)
    if errors:
        messages.error(request, "Please check the optional detail values highlighted below.")
        return render(
            request,
            "contracts/review.html",
            _build_review_context(contract, clarification_errors=errors),
            status=400,
        )

    if contract.state == ContractState.CONFIRMED:
        new_contract = contract.create_revision(
            reason="optional_clarification",
            preferred_specs=preferred,
            required_specs=required,
        )
        messages.info(
            request,
            f"Saved details as new Draft Version {new_contract.version}. Please review and confirm to update discovery.",
        )
        return redirect("contract_review", public_ref=new_contract.public_ref)

    contract.preferred_specs = preferred
    contract.required_specs = required
    contract.full_clean()
    contract.save(update_fields=["preferred_specs", "required_specs", "updated_at"])
    messages.success(request, "Optional details saved to your shopping preferences.")
    return redirect("contract_review", public_ref=contract.public_ref)


@require_POST
def contract_update(request, public_ref: str | None = None, contract_id: UUID | None = None):
    """
    Saves granular edits to a Purchase Contract.
    Invariance check: If contract is CONFIRMED, creates a new version (version + 1) in DRAFT state.
    Confirmed contracts are never silently modified.
    """
    contract, _ = resolve_contract_or_redirect(
        request,
        public_ref=public_ref,
        contract_id=contract_id,
        canonical_view_name="contract_review",
    )

    if contract.state == ContractState.SUPERSEDED:
        messages.error(request, "This contract version has been superseded and cannot be edited directly.")
        latest = contract.revisions.order_by("-version").first()
        if latest:
            return redirect("contract_review", public_ref=latest.public_ref)
        return redirect("home")

    if contract.state == ContractState.CONFIRMED:
        form = ContractReviewForm(request.POST)
        if form.is_valid():
            new_contract = contract.create_revision(
                reason="criteria_edit",
                category=form.cleaned_data["category"],
                product_description=form.cleaned_data["product_description"],
                max_budget=form.cleaned_data["max_budget"],
                currency=form.cleaned_data["currency"],
                quantity=form.cleaned_data["quantity"],
                required_specs=form.cleaned_data["required_specs_json"],
                preferred_specs=form.cleaned_data["preferred_specs_json"],
                excluded_terms=form.cleaned_data["excluded_terms_json"],
                ambiguous_requirements=form.cleaned_data["ambiguous_requirements_json"],
            )
            messages.info(
                request,
                f"Modifications saved as new Version {new_contract.version}. Please review and reconfirm.",
            )
            return redirect("contract_review", public_ref=new_contract.public_ref)
        return render(
            request,
            "contracts/review.html",
            _build_review_context(contract, form=form),
            status=400,
        )

    # Contract is in DRAFT state; update in-place and mark user-reviewed edit provenance
    form = ContractReviewForm(request.POST, instance=contract)
    if form.is_valid():
        updated = form.save(commit=False)
        prov = dict(updated.extraction_provenance or {})
        prov["user_edited"] = True
        updated.extraction_provenance = prov
        updated.save()
        messages.success(request, "Shopping criteria updated successfully.")
        return redirect("contract_review", public_ref=contract.public_ref)

    return render(
        request,
        "contracts/review.html",
        _build_review_context(contract, form=form),
        status=400,
    )


@require_POST
def contract_revise_budget(request, public_ref: str | None = None, contract_id: UUID | None = None):
    """
    Creates a new DRAFT version with a revised Decimal budget (without mutating
    the confirmed contract, without loosening hard constraints, and without
    authorizing payment). Redirects to contract review for explicit confirmation.
    """
    contract, _ = resolve_contract_or_redirect(
        request,
        public_ref=public_ref,
        contract_id=contract_id,
        canonical_view_name="contract_review",
    )

    if contract.state == ContractState.SUPERSEDED:
        messages.error(request, "This contract version is already superseded.")
        latest = contract.revisions.order_by("-version").first()
        if latest:
            return redirect("contract_review", public_ref=latest.public_ref)
        return redirect("home")

    form = BudgetRevisionForm(request.POST)
    if not form.is_valid():
        err_text = "; ".join(form.errors.get("max_budget", ["Invalid budget amount."]))
        messages.error(request, f"Budget revision failed: {err_text}")
        next_source = request.POST.get("next", "")
        if contract.state == ContractState.CONFIRMED and next_source == "evaluation":
            return redirect("contract_evaluation", public_ref=contract.public_ref)
        if contract.state == ContractState.CONFIRMED and next_source == "discovery":
            return redirect("contract_discovery", public_ref=contract.public_ref)
        return redirect("contract_review", public_ref=contract.public_ref)

    new_budget = form.cleaned_data["max_budget"]

    if contract.state == ContractState.CONFIRMED:
        new_contract = contract.create_revision(
            reason="budget_revision",
            max_budget=new_budget,
        )
        return redirect("contract_review", public_ref=new_contract.public_ref)

    # DRAFT state: update in place safely
    contract.max_budget = new_budget
    contract.full_clean()
    contract.save(update_fields=["max_budget", "updated_at"])
    messages.success(request, f"Updated draft budget to ${new_budget} {contract.currency}.")
    return redirect("contract_review", public_ref=contract.public_ref)


def _format_specs_list(specs_dict: dict | None) -> list[dict[str, str]]:
    if not isinstance(specs_dict, dict):
        return []
    return [
        {"label": str(k).replace("_", " ").strip().title(), "value": str(v).strip()}
        for k, v in specs_dict.items()
        if str(v).strip()
    ]


@require_http_methods(["GET", "POST"])
def contract_confirm(request, public_ref: str | None = None, contract_id: UUID | None = None):
    """Explicit confirmation endpoint.

    Transitions contract to CONFIRMED and locks intent for product discovery.
    Strict Invariant: Confirmation is NOT payment authorization.
    """
    contract, redir = resolve_contract_or_redirect(
        request,
        public_ref=public_ref,
        contract_id=contract_id,
        canonical_view_name="contract_confirm",
    )
    if redir:
        return redir

    def _confirm_context():
        return {
            "contract": contract,
            "display_required_specs": format_specs_display(contract.required_specs),
            "display_preferred_specs": format_specs_display(contract.preferred_specs),
            "buy_anyway_ack": (contract.extraction_provenance or {}).get("buy_anyway_acknowledgment"),
        }

    if request.method == "GET":
        if contract.state == ContractState.CONFIRMED:
            return render(
                request,
                "contracts/confirmed.html",
                _confirm_context(),
            )
        return HttpResponseNotAllowed(["POST"])

    if request.method == "POST":
        if contract.state == ContractState.SUPERSEDED:
            messages.error(request, "Cannot confirm a superseded version.")
            latest = contract.revisions.order_by("-version").first()
            if latest:
                return redirect("contract_review", public_ref=latest.public_ref)
            return redirect("home")

        # If any optional clarifications were supplied cleanly during draft confirm, apply to preferences
        if contract.state == ContractState.DRAFT and any(
            k.startswith("clarify__") for k in request.POST
        ):
            preferred, required, errors = _extract_clarification_updates(request.POST, contract)
            if errors:
                messages.error(request, "Please fix invalid optional detail values before confirming.")
                return render(
                    request,
                    "contracts/review.html",
                    _build_review_context(contract, clarification_errors=errors),
                    status=400,
                )
            contract.preferred_specs = preferred
            contract.required_specs = required
            contract.full_clean()
            contract.save(update_fields=["preferred_specs", "required_specs", "updated_at"])

        try:
            if contract.state != ContractState.CONFIRMED:
                contract.confirm()
            return render(
                request,
                "contracts/confirmed.html",
                _confirm_context(),
            )
        except ValidationError as err:
            messages.error(request, f"Unable to confirm requirements: {err!s}")
            return redirect("contract_review", public_ref=contract.public_ref)

    return HttpResponseNotAllowed(["GET", "POST"])


@require_POST
def contract_retry_parse(request, public_ref: str):
    """Retry smart interpretation for an existing DRAFT request without replacing with unrelated demos."""
    contract, _ = resolve_contract_or_redirect(
        request,
        public_ref=public_ref,
        canonical_view_name="contract_review",
    )
    if contract.state != ContractState.DRAFT:
        messages.error(request, "Only draft shopping plans can re-run automatic interpretation.")
        return redirect("contract_review", public_ref=contract.public_ref)

    client = GeminiContractClient()
    parsed_contract, is_fallback, _msg = client.extract_contract(contract.raw_prompt, save_to_db=False)
    if not is_fallback:
        contract.category = parsed_contract.category
        contract.product_description = parsed_contract.product_description
        contract.max_budget = parsed_contract.max_budget
        contract.quantity = parsed_contract.quantity
        contract.required_specs = parsed_contract.required_specs
        contract.preferred_specs = parsed_contract.preferred_specs
        contract.excluded_terms = parsed_contract.excluded_terms
        contract.ambiguous_requirements = parsed_contract.ambiguous_requirements
        contract.source = ContractSource.GEMINI_LIVE
        contract.model_used = parsed_contract.model_used
        contract.extraction_provenance = parsed_contract.extraction_provenance
        contract.full_clean()
        contract.save()
        messages.success(request, "Re-interpreted your shopping request cleanly.")
    else:
        messages.info(
            request,
            "Smart interpretation is still unavailable. Your exact request wording is preserved; review or adjust details below.",
        )
    return redirect("contract_review", public_ref=contract.public_ref)


@require_http_methods(["GET", "POST"])
def contract_buy_anyway(request, public_ref: str, product_id: str):
    """Auditable shopper resolution workflow for unverified or conflicting products ('Buy Anyway').

    Safety Invariants:
    - NEVER bypasses PolicyEngine UNKNOWN/INELIGIBLE outcomes or PaymentService gates.
    - NEVER mutates the confirmed contract in place.
    - Requires explicit shopper acknowledgment and creates a new DRAFT revision (v+1)
      adjusting ONLY the explicit conflicting/unverified requirement so the shopper can
      reconfirm -> re-evaluate -> create a fresh proposal -> grant fresh approval.
    """
    from catalog.models import ProductEvidence
    from catalog.views import _resolve_product_image_url
    from policies.engine import PolicyEngine

    contract, _ = resolve_contract_or_redirect(
        request,
        public_ref=public_ref,
        canonical_view_name="contract_review",
    )
    if contract.state != ContractState.CONFIRMED:
        messages.warning(request, "Please confirm your current shopping plan before reviewing individual items.")
        return redirect("contract_review", public_ref=contract.public_ref)

    product = get_object_or_404(ProductEvidence, product_id=product_id)
    eval_res = PolicyEngine().evaluate(contract, product)

    if eval_res.outcome == "ELIGIBLE":
        messages.info(request, "This product already meets all of your requirements.")
        return redirect("contract_evaluation", public_ref=contract.public_ref)

    non_overridable_reasons: list[str] = []
    unverified_items: list[dict[str, str]] = []
    conflict_items: list[dict[str, str]] = []

    new_required = dict(contract.required_specs or {})
    new_preferred = dict(contract.preferred_specs or {})
    new_excluded = list(contract.excluded_terms or [])
    new_budget = contract.max_budget
    proposed_changes: list[str] = []

    for rec in eval_res.rule_results:
        if rec.rule_name in ("PositivePrice", "CurrencyMatch", "StockAvailability", "CategoryCompatibility") and rec.outcome == "FAIL":
            non_overridable_reasons.append(rec.message)
        elif rec.rule_name == "BudgetCeiling" and rec.outcome == "FAIL":
            conflict_items.append({
                "title": "Over current item budget limit",
                "detail": f"Item subtotal is ${eval_res.total_item_price} {contract.currency}, which exceeds your ${contract.max_budget} {contract.currency} item limit.",
            })
            if eval_res.total_item_price > new_budget:
                new_budget = eval_res.total_item_price
                proposed_changes.append(f"Raise item budget limit from ${contract.max_budget} to ${new_budget} {contract.currency}")
        elif rec.rule_name == "ExcludedTerms" and rec.outcome == "FAIL":
            matched_lower = str(rec.observed_value or "").replace("Found:", "").strip().lower()
            matched_terms = [t.strip() for t in matched_lower.split(",") if t.strip()]
            removed = [ex for ex in list(new_excluded) if any(m == ex.lower() or m in ex.lower() for m in matched_terms)]
            new_excluded = [ex for ex in new_excluded if ex not in removed]
            conflict_items.append({
                "title": "Conflicts with your excluded terms",
                "detail": rec.message,
            })
            if removed:
                proposed_changes.append(f"Remove {', '.join(removed)} from What to exclude")
        elif rec.rule_name.startswith("RequiredSpec:") and rec.outcome in ("FAIL", "UNKNOWN"):
            raw_spec_key = rec.rule_name.split(":", 1)[1].strip()
            human_label = format_spec_label(raw_spec_key)
            raw_expected = str(rec.expected_value or new_required.get(raw_spec_key, "")).strip()
            if raw_expected.lower().startswith(f"{raw_spec_key.lower()}:"):
                raw_expected = raw_expected.split(":", 1)[1].strip()
            formatted_expected = format_spec_value(raw_spec_key, raw_expected)
            if rec.outcome == "UNKNOWN":
                unverified_items.append({
                    "title": f"{human_label} could not be verified",
                    "detail": f"AI Cart cannot confirm from available product details that this item meets your required '{human_label}: {formatted_expected}'.",
                })
                if raw_spec_key in new_required:
                    val = new_required.pop(raw_spec_key)
                    new_preferred[raw_spec_key] = val
                    proposed_changes.append(f"Move '{human_label}: {format_spec_value(raw_spec_key, val)}' from Must-have to Preferred (keeps your accepted uncertainty on record)")
            else:
                conflict_items.append({
                    "title": f"Conflicts with required {human_label}",
                    "detail": rec.message,
                })
                if raw_spec_key in new_required:
                    val = new_required.pop(raw_spec_key)
                    new_preferred[raw_spec_key] = val
                    proposed_changes.append(f"Move '{human_label}: {format_spec_value(raw_spec_key, val)}' from Must-have to Preferred")
        elif rec.outcome == "UNKNOWN":
            unverified_items.append({
                "title": rec.rule_name.replace("Compatibility", " compatibility"),
                "detail": rec.message,
            })

    can_revise_and_proceed = (not non_overridable_reasons) and (bool(proposed_changes) or bool(unverified_items))
    situation = "UNVERIFIED_SPEC" if eval_res.outcome == "UNKNOWN" else "CONSTRAINT_CONFLICT"

    if request.method == "POST":
        if not can_revise_and_proceed:
            messages.error(request, "This product cannot proceed due to stock, pricing, or currency limits.")
            return redirect("contract_buy_anyway", public_ref=contract.public_ref, product_id=product.product_id)

        ack_risk = request.POST.get("acknowledge_risk") == "on"
        ack_revision = request.POST.get("acknowledge_revision") == "on"
        if not (ack_risk and ack_revision):
            messages.error(request, "Please check both confirmation boxes to acknowledge and prepare the updated shopping plan.")
        else:
            new_contract = contract.create_revision(
                reason="buy_anyway_acknowledgment",
                max_budget=new_budget,
                required_specs=new_required,
                preferred_specs=new_preferred,
                excluded_terms=new_excluded,
            )
            prov = dict(new_contract.extraction_provenance or {})
            prov["user_edited"] = True
            prov["buy_anyway_acknowledgment"] = {
                "situation": situation,
                "acknowledged": True,
                "acknowledged_at": timezone.now().isoformat(),
                "product_id": product.product_id,
                "product_title": product.title,
                "merchant_name": product.source_merchant,
                "unit_price": str(product.price),
                "currency": product.currency,
                "outcome_before_revision": eval_res.outcome,
                "unverified_notes": [u["detail"] for u in unverified_items],
                "conflict_notes": [c["detail"] for c in conflict_items],
                "changes_applied": proposed_changes,
            }
            new_contract.extraction_provenance = prov
            new_contract.save(update_fields=["extraction_provenance"])
            return redirect("contract_review", public_ref=new_contract.public_ref)

    return render(
        request,
        "contracts/buy_anyway.html",
        {
            "contract": contract,
            "product": product,
            "image_url": _resolve_product_image_url(product),
            "eval_res": eval_res,
            "situation": situation,
            "non_overridable_reasons": non_overridable_reasons,
            "unverified_items": unverified_items,
            "conflict_items": conflict_items,
            "proposed_changes": proposed_changes,
            "can_revise_and_proceed": can_revise_and_proceed,
        },
    )
