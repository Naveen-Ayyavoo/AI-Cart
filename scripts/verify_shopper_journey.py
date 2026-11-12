"""
AI Cart 10-Step Shopper Journey Acceptance Verification Script (formerly TrustCart)
Validates the complete end-to-end user experience across all 12 views:
1. Intake (/)
2. Contract Review (/contracts/<id>/review/)
3. Contract Confirmed (/contracts/<id>/confirm/)
4. Catalog Discovery (/contracts/<id>/discovery/)
5. Policy Evaluation (/contracts/<id>/evaluation/)
6. Proposal Detail (/orders/proposals/<id>/)
7. Approve Proposal (POST)
8. Approval Detail (/orders/approvals/<id>/)
9. Checkout Transition (POST /payments/checkout/initiate/<token>/) & Single-Use Idempotency
10. Result States (Receipt, Pending, Cancelled, Failed)
"""

import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "trustcart.settings")
django.setup()

from django.test import Client
from django.urls import reverse

from catalog.models import ProductEvidence
from contracts.models import ContractSource, ContractState, PurchaseContract
from orders.models import DEMO_PAYEE_DISCLOSURE
from payments.models import PaymentCaptureRecord


def run_journey_verification():
    print("=" * 80)
    print("AI Cart 10-Step End-to-End Shopper Journey Verification")
    print("=" * 80)

    client = Client()
    checks_passed = 0
    total_checks = 0

    def assert_check(condition, name, details=""):
        nonlocal checks_passed, total_checks
        total_checks += 1
        if condition:
            checks_passed += 1
            print(f"  [PASS] Step Check {total_checks}: {name} {details}")
        else:
            print(f"  [FAIL] Step Check {total_checks}: {name} - FAILED: {details}")
            sys.exit(1)

    # -------------------------------------------------------------
    # Step 1: Intake View (/)
    # -------------------------------------------------------------
    print("\n--- Step 1: Shopper Intake (Home) ---")
    resp = client.get(reverse("home"))
    assert_check(resp.status_code == 200, "Intake page renders with HTTP 200")
    assert_check("AI Cart" in resp.content.decode(), "Brand name AI Cart present in layout")
    assert_check("Intelligence in Every Click" in resp.content.decode(), "Brand tagline Intelligence in Every Click present in layout")
    assert_check("Load Demo Scenario" in resp.content.decode(), "Demo scenario cards accessible")
    assert_check("Describe What You Want to Purchase" in resp.content.decode(), "Intake instructions present")

    # Negative test: Empty prompt submission validation
    resp_empty = client.post(reverse("contract_create"), {"prompt": ""})
    assert_check(
        resp_empty.status_code == 400 and "Please enter a shopping request or select a sample scenario" in resp_empty.content.decode(),
        "Empty intake validation error informs user with actionable recovery (HTTP 400)"
    )

    # -------------------------------------------------------------
    # Step 2: Contract Review View
    # -------------------------------------------------------------
    print("\n--- Step 2: Contract Review ---")
    contract = PurchaseContract.objects.create(
        raw_prompt="Ergonomic mechanical keyboard under $100 with tactile switches",
        category="Keyboards",
        product_description="Ergonomic keyboard with tactile switches",
        max_budget=Decimal("100.00"),
        currency="USD",
        quantity=1,
        required_specs={"switches": "tactile", "form_factor": "ergonomic"},
        preferred_specs={"backlight": "RGB"},
        excluded_terms=["clicky", "blue switches"],
        ambiguous_requirements=["wrist rest included"],
        source=ContractSource.DEMO_FIXTURE,
        state=ContractState.DRAFT,
        version=1,
    )

    resp_review = client.get(reverse("contract_review", args=[contract.public_ref]))
    assert_check(resp_review.status_code == 200, "Contract review page renders with HTTP 200")
    review_html = resp_review.content.decode()
    assert_check("Essential Purchase Requirements" in review_html, "Essential purchase requirements section visible")
    assert_check("Required Specifications (Must-Have)" in review_html, "Required specs visible in primary area")
    assert_check("Preferred Specifications (Optional)" in review_html, "Preferred specs visible in primary area")
    assert_check("What to exclude" in review_html, "Excluded terms visible in primary area")
    assert_check("Optional details to improve your results" in review_html, "Interactive optional clarification section visible")
    assert_check("Leave any field blank if you do not mind." in review_html, "Optional clarification skip guidance visible")
    assert_check("tc-stage-bar" not in review_html.split("</style>", 1)[-1], "No stage breadcrumbs in review page")

    # -------------------------------------------------------------
    # Step 3: Confirm Contract
    # -------------------------------------------------------------
    print("\n--- Step 3: Contract Confirmation ---")
    resp_confirm = client.post(reverse("contract_confirm", args=[contract.public_ref]))
    assert_check(resp_confirm.status_code == 200, "Contract confirmation returns HTTP 200")
    contract.refresh_from_db()
    assert_check(contract.state == ContractState.CONFIRMED, "Contract state transitioned to CONFIRMED")

    confirmed_html = resp_confirm.content.decode()
    assert_check("Shopping Requirements Confirmed" in confirmed_html, "Confirmed page indicates requirements are confirmed")
    assert_check("Confirming your requirements is not a payment." in confirmed_html, "Confirmation non-payment boundary displayed")
    assert_check("Find Matching Products" in confirmed_html, "Next step to product discovery clearly presented")
    assert_check("Additional options" not in confirmed_html and "SHA-256" not in confirmed_html, "No SHA-256 or Additional options clutter on confirm page")

    # -------------------------------------------------------------
    # Step 4: Catalog Discovery
    # -------------------------------------------------------------
    print("\n--- Step 4: Catalog Discovery ---")
    with patch("catalog.services.Channel3Client") as MockChannel3Client:
        mock_c3 = MagicMock()
        mock_c3.search.return_value = ([
            {
                "product_id": "DEMO-KB-001",
                "title": "ErgoPro Wireless Mechanical Keyboard",
                "brand": "ErgoPro",
                "price": Decimal("79.99"),
                "currency": "USD",
                "stock_status": "IN_STOCK",
                "source_merchant": "Keyboards Co",
            }
        ], True, "Using local test fixture")
        mock_c3.get_product.return_value = ({
            "product_id": "DEMO-KB-001",
            "title": "ErgoPro Wireless Mechanical Keyboard",
            "brand": "ErgoPro",
            "description": "Ergonomic mechanical keyboard with silent tactile switches",
            "price": Decimal("79.99"),
            "currency": "USD",
            "stock_status": "IN_STOCK",
            "source_merchant": "Keyboards Co",
            "merchant_id": "M-KB-01",
            "variant_id": "VAR-01",
            "sku": "SKU-ERGO-01",
            "product_url": "https://example.com/demo/ergopro",
            "image_url": "https://example.com/demo/ergopro.jpg",
            "retrieval_timestamp": django.utils.timezone.now(),
            "raw_evidence": {"source": "channel3_fixture"},
            "is_fixture": True,
        }, True, "Local fixture")
        MockChannel3Client.return_value = mock_c3

        resp_catalog = client.get(reverse("contract_discovery", args=[contract.public_ref]))
        assert_check(resp_catalog.status_code == 200, "Catalog discovery page renders with HTTP 200")
        cat_html = resp_catalog.content.decode()
        assert_check("ErgoPro Wireless Mechanical Keyboard" in cat_html, "Candidate product displayed")
        assert_check("$79.99" in cat_html, "Product price displayed clearly")
        assert_check("Keyboards Co" in cat_html, "Source merchant/seller displayed")
        assert_check("View All Results" in cat_html or "View Full Results" in cat_html, "Link to full evaluation results present")

    product = ProductEvidence.objects.get(product_id="DEMO-KB-001")

    # -------------------------------------------------------------
    # Step 5: Policy Evaluation
    # -------------------------------------------------------------
    print("\n--- Step 5: Policy Evaluation ---")
    resp_policy = client.get(reverse("contract_evaluation", args=[contract.public_ref]))
    assert_check(resp_policy.status_code == 200, "Policy evaluation page renders with HTTP 200")
    pol_html = resp_policy.content.decode()
    assert_check("Results for your request" in pol_html and "Meets Your Requirements" in pol_html, "Shopper evaluation results rendered")

    # -------------------------------------------------------------
    # Step 6: Proposal Detail
    # -------------------------------------------------------------
    print("\n--- Step 6: Purchase Proposal Detail ---")
    from orders.services import ProposalService
    proposal, approval = ProposalService.create_proposal(
        contract=contract,
        product=product,
        shipping_amount=Decimal("0.00"),
        tax_amount=Decimal("6.40"),
        fee_amount=Decimal("0.00"),
        charges_confirmed=True,
        payee_id="PU7K3F65AAQ8U",
    )

    resp_prop = client.get(reverse("proposal_detail", args=[proposal.public_ref]))
    assert_check(resp_prop.status_code == 200, "Proposal detail page renders with HTTP 200")
    prop_html = resp_prop.content.decode()
    assert_check("Policy Verification &amp; Hard Constraints" in prop_html or "Policy Verification & Hard Constraints" in prop_html, "Policy verification summary immediately visible")
    assert_check("$86.39" in prop_html, "Total payable amount immediately visible")
    assert_check("PU7K3F65AAQ8U" in prop_html, "PayPal Sandbox demo payee immediately visible")
    assert_check("Tax &amp; Shipping" in prop_html or "Tax & Shipping" in prop_html, "Tax & shipping uncertainty note present")
    assert_check("SHA-256" not in prop_html, "Raw SHA-256 fingerprint string hidden from shopper view")

    # -------------------------------------------------------------
    # Step 7 & 8: Approve Proposal & View Approval Detail
    # -------------------------------------------------------------
    print("\n--- Step 7 & 8: Proposal Approval & Detail ---")
    resp_approve = client.post(reverse("proposal_detail", args=[proposal.public_ref]), {"action": "approve"})
    assert_check(resp_approve.status_code in (200, 302), "Proposal approval action returns valid status")

    approval.refresh_from_db()
    assert_check(approval.state == "APPROVED", "Approval object state is APPROVED")

    resp_appr_detail = client.get(reverse("approval_detail", args=[approval.public_ref]))
    assert_check(resp_appr_detail.status_code == 200, "Approval detail page renders with HTTP 200")
    appr_html = resp_appr_detail.content.decode()
    assert_check("Approval Token ID:" not in appr_html, "Raw approval token is NOT leaked in visible HTML")
    assert_check("Single-Use" in appr_html, "Single-use lifecycle badge visible")
    assert_check("PU7K3F65AAQ8U" in appr_html, "Demo payee displayed")
    assert_check("Proceed to PayPal Sandbox Checkout" in appr_html, "Call to action button clearly labeled")

    # -------------------------------------------------------------
    # Step 9: Checkout Transition & Single-Use Idempotency
    # -------------------------------------------------------------
    print("\n--- Step 9: Checkout Transition & Single-Use Protection ---")
    import uuid
    test_paypal_id = f"PAYPAL-TEST-{uuid.uuid4().hex[:8].upper()}"
    with patch("payments.services.PayPalClient") as MockPayPalClient:
        mock_instance = MagicMock()
        mock_instance.create_order.return_value = {
            "id": test_paypal_id,
            "status": "CREATED",
            "links": [
                {"rel": "approve", "href": f"https://www.sandbox.paypal.com/checkoutnow?token={test_paypal_id}"}
            ]
        }
        MockPayPalClient.return_value = mock_instance

        # 1st submission: Consumes token and transitions to CREATED
        resp_create = client.post(reverse("payments:checkout_initiate", args=[approval.token]))
        assert_check(resp_create.status_code in (200, 302), "Checkout order initiation returns redirect to PayPal approval")
        approval.refresh_from_db()
        assert_check(approval.state == "CONSUMED", "Approval token transitioned to CONSUMED")

        # 2nd submission: Duplicate attempt must fail closed (idempotency / replay protection)
        resp_replay = client.post(reverse("payments:checkout_initiate", args=[approval.token]))
        assert_check(
            resp_replay.status_code in (302, 400),
            "Duplicate submission of consumed approval token fails closed with redirect/rejection"
        )

    # -------------------------------------------------------------
    # Step 10: Result States
    # -------------------------------------------------------------
    print("\n--- Step 10: Result States Verification ---")
    payment_order = approval.payment_order
    payment_order.status = "COMPLETED"
    payment_order.save()

    test_capture_id = f"CAPTURE-TEST-{uuid.uuid4().hex[:8].upper()}"
    capture = PaymentCaptureRecord.objects.create(
        order=payment_order,
        capture_id=test_capture_id,
        status="COMPLETED",
        amount=Decimal("86.39"),
        currency="USD",
    )

    # 10A: Receipt View
    resp_receipt = client.get(reverse("payments:order_detail", args=[payment_order.paypal_order_id]))
    assert_check(resp_receipt.status_code == 200, "Receipt view renders with HTTP 200")
    receipt_html = resp_receipt.content.decode()
    assert_check(payment_order.paypal_order_id in receipt_html, "PayPal Order ID displayed on receipt")
    assert_check(capture.capture_id in receipt_html, "Capture ID displayed on receipt")
    assert_check(payment_order.create_idempotency_key not in receipt_html, "Internal create idempotency key NOT leaked on receipt")
    assert_check(payment_order.capture_idempotency_key not in receipt_html, "Internal capture idempotency key NOT leaked on receipt")

    # 10B: Cancelled View
    resp_cancel = client.get(reverse("payments:checkout_cancel"), {"token": payment_order.paypal_order_id})
    assert_check(resp_cancel.status_code == 200, "Cancelled view renders with HTTP 200")
    cancel_html = resp_cancel.content.decode()
    assert_check("Cancelled" in cancel_html or "cancelled" in cancel_html, "Cancellation title and explanation rendered")
    assert_check("New Search" in cancel_html, "Recovery navigation link ('New Search') present")
    assert_check("Return to Results" in cancel_html, "Evaluation return link present when token provided")

    # 10C: Direct Template Check: Pending Reconciliation Template
    from django.template.loader import render_to_string
    pending_rendered = render_to_string("payments/pending.html", {
        "title": "Payment Pending Reconciliation",
        "demo_payee_disclosure": DEMO_PAYEE_DISCLOSURE,
    })
    assert_check("Pending Reconciliation" in pending_rendered, "Pending template renders cleanly with title")
    assert_check("Controlled Demo Payee Boundary" in pending_rendered, "Pending template contains demo payee disclosure")

    # 10D: Direct Template Check: Payment Failed Template
    failed_rendered = render_to_string("payments/failed.html", {
        "error_message": "Payment capture was rejected or failed security revalidation.",
        "demo_payee_disclosure": DEMO_PAYEE_DISCLOSURE,
    })
    assert_check("Payment Execution Failed" in failed_rendered, "Failed template renders cleanly with title")
    assert_check("Controlled Demo Payee Boundary" in failed_rendered, "Failed template contains demo payee disclosure")

    print("\n" + "=" * 80)
    print(f"VERDICT: ALL {checks_passed}/{total_checks} CHECKS PASSED (100%)")
    print("Zero live PayPal captures executed. Zero Channel3 credits consumed. Local mock fixtures only.")
    print("=" * 80)


if __name__ == "__main__":
    run_journey_verification()
