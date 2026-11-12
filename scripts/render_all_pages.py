"""
Renders all 12 user-facing templates with realistic data and outputs static HTML files
to scratch/rendered_pages/ for headless Chrome DevTools browser verification.
"""

import os
import sys
import uuid
from decimal import Decimal

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "trustcart.settings")
django.setup()

from django.template.loader import render_to_string
from django.utils import timezone

from catalog.models import ProductEvidence
from contracts.forms import ContractReviewForm, PromptIntakeForm
from contracts.models import ContractState, PurchaseContract
from orders.models import PurchaseApproval, PurchaseProposal
from payments.models import PaymentCaptureRecord, PaymentOrder
from policies.models import PolicyEvaluationReport


def render_all():
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch", "rendered_pages")
    os.makedirs(output_dir, exist_ok=True)

    uid = uuid.uuid4().hex[:8]

    # Setup entities
    contract = PurchaseContract.objects.create(
        raw_prompt="Ergonomic mechanical keyboard for developer under $120",
        category="Keyboards",
        product_description="Mechanical keyboard with quiet brown switches and Bluetooth",
        max_budget=Decimal("120.00"),
        currency="USD",
        quantity=1,
        state=ContractState.CONFIRMED,
        confirmed_at=timezone.now(),
        required_specs={"connectivity": "Wireless", "layout": "ANSI"},
        preferred_specs={"switch_type": "Brown", "backlight": "RGB"},
        excluded_terms=["refurbished", "used"],
    )

    prod = ProductEvidence.objects.create(
        product_id=f"prod_demo_{uid}",
        brand="Keychron",
        title="Keychron Q1 Wireless Custom Mechanical Keyboard",
        description="Premium fully customizable mechanical keyboard with hot-swappable switches and CNC aluminum body.",
        price=Decimal("99.00"),
        currency="USD",
        source_merchant="Keychron Official Store",
        stock_status="IN_STOCK",
        is_fixture=True,
        sku="KEY-Q1-W-BRN",
        raw_evidence={"features": {"layout": "75% ANSI", "connectivity": "Wireless Bluetooth"}},
    )

    prod2 = ProductEvidence.objects.create(
        product_id=f"prod_demo_redragon_{uid}",
        brand="Redragon",
        title="Redragon Antonium K745 Pro",
        description="Ergonomic mechanical gaming keyboard with quiet switches and RGB backlight.",
        price=Decimal("49.99"),
        currency="USD",
        source_merchant="Redragon Shop",
        stock_status="IN_STOCK",
        is_fixture=True,
        sku="RED-K745-PRO",
        raw_evidence={"features": {"switch_type": "Tactile Quiet", "backlight": "RGB Multi-color"}},
    )

    prod3 = ProductEvidence.objects.create(
        product_id=f"prod_demo_ergopro_{uid}",
        brand="ErgoPro",
        title="ErgoPro Wireless Mechanical Keyboard",
        description="Ergonomic wireless keyboard with tactile brown switches.",
        price=Decimal("79.99"),
        currency="USD",
        source_merchant="Keyboards Co",
        stock_status="IN_STOCK",
        is_fixture=True,
        sku="ERGO-KB-01",
        raw_evidence={"features": {"switch_type": "Tactile Brown", "connectivity": "Wireless 2.4GHz"}},
    )

    from catalog.views import _extract_product_highlights
    from contracts.clarifications import (
        build_clarification_fields,
        build_edit_criteria_metadata,
    )
    from policies.engine import PolicyEngine
    engine = PolicyEngine()
    rendered_products = [prod2, prod3, prod]
    dec_items = [_extract_product_highlights(p, contract, engine) for p in rendered_products]
    for i, item in enumerate(dec_items):
        item["index"] = i
    dec_items[0]["distinctions"] = ["Lowest Item Subtotal", "Best Preference Match"]
    dec_items[0]["badge"] = "Lowest Item Subtotal & Best Preference Match"
    dec_items[1]["distinctions"] = []
    dec_items[1]["badge"] = ""
    dec_items[2]["distinctions"] = []
    dec_items[2]["badge"] = ""

    report = PolicyEvaluationReport.objects.create(
        contract=contract,
        product=prod,
        outcome="ELIGIBLE",
        summary="All mandatory rules passed.",
        unit_price=Decimal("99.00"),
        quantity=1,
        total_item_price=Decimal("99.00"),
        budget_ceiling=Decimal("120.00"),
        preference_score=95,
        currency="USD",
        matched_preferences=["switch_type: Brown", "backlight: RGB"],
        rule_results=[
            {
                "rule_name": "CurrencyRule",
                "outcome": "PASS",
                "expected_value": "USD",
                "observed_value": "USD",
                "evidence_source": "Catalog Evidence",
            },
            {
                "rule_name": "BudgetCeilingRule",
                "outcome": "PASS",
                "expected_value": "<= 120.00",
                "observed_value": "99.00",
                "evidence_source": "Pricing Breakdown",
            },
            {
                "rule_name": "StockAvailabilityRule",
                "outcome": "PASS",
                "expected_value": "IN_STOCK",
                "observed_value": "IN_STOCK",
                "evidence_source": "Merchant Inventory",
            },
        ],
    )

    proposal = PurchaseProposal.objects.create(
        contract=contract,
        product=prod,
        policy_report=report,
        source_merchant="Keychron Official Store",
        payee_id="PU7K3F65AAQ8U",
        quantity=1,
        unit_price=Decimal("99.00"),
        base_amount=Decimal("99.00"),
        shipping_amount=Decimal("0.00"),
        tax_amount=Decimal("7.92"),
        fee_amount=Decimal("0.00"),
        total_amount=Decimal("106.92"),
        currency="USD",
        charges_confirmed=True,
        status="APPROVED",
    )
    proposal.cart_fingerprint = proposal.calculate_fingerprint()
    proposal.save()

    approval = PurchaseApproval.objects.create(
        token=f"tok_browser_test_{uid}",
        proposal=proposal,
        cart_fingerprint=proposal.cart_fingerprint,
        state="APPROVED",
        approved_at=timezone.now(),
    )

    pay_order = PaymentOrder.objects.create(
        approval=approval,
        proposal=proposal,
        contract=contract,
        paypal_order_id=f"PP-BROWSER-{uid}",
        status="COMPLETED",
        payee_id="PU7K3F65AAQ8U",
        quantity=1,
        unit_price=Decimal("99.00"),
        base_amount=Decimal("99.00"),
        shipping_amount=Decimal("0.00"),
        tax_amount=Decimal("7.92"),
        fee_amount=Decimal("0.00"),
        total_amount=Decimal("106.92"),
        currency="USD",
        cart_fingerprint=proposal.cart_fingerprint,
        create_idempotency_key=f"CREATE-BROWSER-{uid}",
        capture_idempotency_key=f"CAPTURE-BROWSER-{uid}",
    )

    capture = PaymentCaptureRecord.objects.create(
        order=pay_order,
        capture_id=f"CAP-BROWSER-{uid}",
        status="COMPLETED",
        amount=Decimal("106.92"),
        currency="USD",
        captured_at=timezone.now(),
    )

    # 12 Template Contexts
    page_data = [
        ("01_home.html", "home.html", {
            "form": PromptIntakeForm(),
            "scenarios": [
                {"key": "headphones", "title": "Wireless Headphones", "prompt": "Wireless noise-canceling headphones under $150"},
                {"key": "keyboard", "title": "Mechanical Keyboard", "prompt": "Mechanical keyboard under $100"},
                {"key": "chair", "title": "Ergonomic Chair", "prompt": "Ergonomic chair under $250"},
            ],
        }),
        ("02_contract_review.html", "contracts/review.html", {
            "contract": contract,
            "form": ContractReviewForm(instance=contract),
            "is_fallback": True,
            "scenarios": [],
            "clarification_fields": build_clarification_fields(contract),
            "clarification_errors": {},
            "edit_metadata": build_edit_criteria_metadata(contract),
            "last_revision": None,
        }),
        ("03_contract_confirmed.html", "contracts/confirmed.html", {
            "contract": contract,
        }),
        ("04_catalog_discovery.html", "catalog/product_list.html", {
            "contract": contract,
            "products": rendered_products,
            "decorated_items": dec_items,
            "shortlist_items": [x for x in dec_items if x["is_eligible"]][:3],
            "visible_conflict_items": [x for x in dec_items if not x["is_eligible"] and x["can_buy_anyway"]][:2],
            "additional_items": dec_items[3:],
            "eligible_count": len([x for x in dec_items if x["is_eligible"]]),
            "over_budget_count": 0,
            "min_over_budget_subtotal": None,
            "is_fallback": True,
        }),
        ("05_policy_evaluation.html", "policies/evaluation.html", {
            "contract": contract,
            "total_count": 1,
            "eligible_reports": [report],
            "unknown_reports": [],
            "ineligible_reports": [],
        }),
        ("06_proposal_detail.html", "orders/proposal_detail.html", {
            "contract": contract,
            "product": prod,
            "proposal": proposal,
            "approval": approval,
            "demo_payee_disclosure": "PayPal Sandbox Demo Payee PU7K3F65AAQ8U",
        }),
        ("07_approval_detail.html", "orders/approval_detail.html", {
            "contract": contract,
            "product": prod,
            "proposal": proposal,
            "approval": approval,
            "demo_payee_disclosure": "PayPal Sandbox Demo Payee PU7K3F65AAQ8U",
        }),
        ("08_payment_receipt.html", "payments/receipt.html", {
            "order": pay_order,
            "capture": capture,
            "demo_payee_disclosure": "PayPal Sandbox Demo Payee PU7K3F65AAQ8U",
        }),
        ("09_payment_pending.html", "payments/pending.html", {
            "order": pay_order,
            "title": "Payment Pending Reconciliation",
            "message": "Testing pending state awaiting PayPal confirmation.",
            "demo_payee_disclosure": "PayPal Sandbox Demo Payee PU7K3F65AAQ8U",
        }),
        ("10_payment_cancelled.html", "payments/cancelled.html", {
            "order": pay_order,
            "demo_payee_disclosure": "PayPal Sandbox Demo Payee PU7K3F65AAQ8U",
        }),
        ("11_payment_failed.html", "payments/failed.html", {
            "order": pay_order,
            "error_message": "Pre-capture revalidation failed: price mismatch detected.",
            "demo_payee_disclosure": "PayPal Sandbox Demo Payee PU7K3F65AAQ8U",
        }),
        ("12_base_layout.html", "base.html", {}),
        ("13_custom_404.html", "404.html", {}),
        ("14_custom_403.html", "403.html", {}),
    ]

    rendered_files = []
    for filename, template_name, context in page_data:
        html = render_to_string(template_name, context)
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        rendered_files.append((filename, filepath, len(html)))
        print(f"Rendered {filename:26} ({len(html):,} bytes) -> {filepath}")

    print(f"\nSuccessfully rendered all {len(rendered_files)} pages to {output_dir}")
    return rendered_files


if __name__ == "__main__":
    render_all()
