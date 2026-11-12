"""Concurrency, race-condition, and atomic conditional update tests for purchase approval consumption.

Covers:
- APPR-05 (Atomic single-use consumption and race condition prevention)
- Clarification 6 (Concurrent-consumption tests)
- Conditional atomic database UPDATE criteria:
  * Exact approval record
  * state == APPROVED
  * expires_at > current time
  * consumed_at IS NULL
  * Expected cart fingerprint
  * state -> CONSUMED with consumed_at timestamp
  * Exactly one row updated
  * Fail-closed handling for database lock errors
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.db import OperationalError, connections
from django.test import TransactionTestCase
from django.utils import timezone

from catalog.models import ProductEvidence
from contracts.models import PurchaseContract
from orders.models import (
    ApprovalAlreadyConsumedError,
    ApprovalError,
    ApprovalExpiredError,
    ApprovalInvalidError,
    ApprovalLockError,
    PurchaseApproval,
)
from orders.services import ApprovalService, ProposalService
from policies.models import PolicyEvaluationReport


class ApprovalConcurrencyTests(TransactionTestCase):
    """Test race-condition, conditional update, and concurrent-consumption resistance."""

    def setUp(self):
        self.contract = PurchaseContract.objects.create(
            raw_prompt="Keychron C3 Pro TKL mechanical keyboard",
            category="Mechanical Keyboards",
            product_description="Tenkeyless mechanical keyboard with red linear switches",
            max_budget=Decimal("50.00"),
            currency="USD",
            quantity=1,
            state="CONFIRMED",
            confirmed_at=timezone.now(),
        )

        self.product = ProductEvidence.objects.create(
            product_id="test_keychron_c3",
            brand="Keychron",
            title="Keychron C3 Pro TKL",
            description="Tenkeyless mechanical keyboard.",
            price=Decimal("36.99"),
            currency="USD",
            source_merchant="Amazon",
            stock_status="IN_STOCK",
        )

        self.policy_report = PolicyEvaluationReport.objects.create(
            contract=self.contract,
            product=self.product,
            outcome="ELIGIBLE",
            unit_price=Decimal("36.99"),
            quantity=1,
            total_item_price=Decimal("36.99"),
            budget_ceiling=Decimal("50.00"),
            currency="USD",
            preference_score=100,
        )

        self.proposal, self.approval = ProposalService.create_proposal(
            contract=self.contract,
            product=self.product,
            policy_report=self.policy_report,
            charges_confirmed=True,
        )
        self.approval = ApprovalService.approve_proposal(self.proposal.id)

    def test_concurrent_consumption_race_condition(self):
        """When 10 concurrent threads attempt to consume the same approval token simultaneously,

        EXACTLY ONE must succeed; all other 9 attempts must be rejected.
        Each thread uses its own dedicated database connection.
        """
        token = self.approval.token
        num_workers = 10
        success_count = 0
        rejected_count = 0

        def attempt_consume(worker_id: int):
            # Ensure this thread starts with its own clean, separate database connection
            for conn in connections.all(initialized_only=True):
                conn.close()

            try:
                ApprovalService.consume_approval(token, order_reference=f"THREAD-{worker_id}")
                return True, "SUCCESS"
            except (ApprovalAlreadyConsumedError, ApprovalLockError, OperationalError) as e:
                # Lock contention or atomic conditional state transition blocked duplicate consumption
                return False, f"REJECTED: {type(e).__name__}"
            except ApprovalError as e:
                return False, f"OTHER_ERROR: {e!s}"
            finally:
                # Clean up connection for this thread
                for conn in connections.all(initialized_only=True):
                    conn.close()

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(attempt_consume, i) for i in range(num_workers)]
            for future in as_completed(futures):
                success, _reason = future.result()
                if success:
                    success_count += 1
                else:
                    rejected_count += 1

        # Invariant check: Exactly 1 consumer succeeded
        self.assertEqual(success_count, 1, f"Expected exactly 1 successful consumption, got {success_count}")
        self.assertEqual(rejected_count, num_workers - 1)

        # Database state check
        approval = PurchaseApproval.objects.get(token=token)
        self.assertEqual(approval.state, "CONSUMED")
        self.assertIsNotNone(approval.consumed_at)

        # Check audit log: exactly one CONSUMED event recorded
        consumed_events = [e for e in approval.audit_log if e.get("event") == "CONSUMED"]
        self.assertEqual(len(consumed_events), 1)

    def test_conditional_atomic_update_criteria(self):
        """Verify the exact conditions required for atomic conditional update:

        - State must be APPROVED.
        - Token cannot be expired (expires_at > current time).
        - consumed_at must be NULL.
        - Cart fingerprint must match.
        """
        token = self.approval.token

        # 1. State must be APPROVED (pending state rejected)
        _pending_prop, pending_appr = ProposalService.create_proposal(
            contract=self.contract,
            product=self.product,
            policy_report=self.policy_report,
            charges_confirmed=True,
        )
        with self.assertRaises(ApprovalInvalidError):
            pending_appr.consume(order_reference="ORD-PENDING")

        # 2. Expired approval cannot be consumed (expires_at <= now)
        exp_prop, exp_appr = ProposalService.create_proposal(
            contract=self.contract,
            product=self.product,
            policy_report=self.policy_report,
            charges_confirmed=True,
        )
        exp_appr = ApprovalService.approve_proposal(exp_prop.id)
        exp_appr.expires_at = timezone.now() - timedelta(seconds=1)
        exp_appr.save(update_fields=["expires_at"])
        with self.assertRaises(ApprovalExpiredError):
            exp_appr.consume(order_reference="ORD-EXPIRED")

        # 3. Tampered cart fingerprint rejected
        tamper_prop, tamper_appr = ProposalService.create_proposal(
            contract=self.contract,
            product=self.product,
            policy_report=self.policy_report,
            charges_confirmed=True,
        )
        tamper_appr = ApprovalService.approve_proposal(tamper_prop.id)
        # Tamper proposal out of band
        tamper_prop.base_amount = Decimal("99.99")
        tamper_prop.save(update_fields=["base_amount"])
        with self.assertRaises(ApprovalInvalidError):
            tamper_appr.consume(order_reference="ORD-TAMPER")

        # 4. Successful conditional update sets state to CONSUMED and records consumed_at
        appr_obj = PurchaseApproval.objects.get(token=token)
        appr_obj.consume(order_reference="ORD-CONDITIONAL-SUCCESS")
        appr_obj.refresh_from_db()
        self.assertEqual(appr_obj.state, "CONSUMED")
        self.assertIsNotNone(appr_obj.consumed_at)

        # 5. Subsequent attempt fails because consumed_at is NOT NULL and state is NOT APPROVED
        with self.assertRaises(ApprovalAlreadyConsumedError):
            appr_obj.consume(order_reference="ORD-SECOND-ATTEMPT")

    def test_database_lock_error_fails_closed(self):
        """When a database lock error (OperationalError) occurs during consumption,

        it MUST fail closed by raising ApprovalLockError without marking the token consumed.
        """
        token = self.approval.token

        with (
            patch("orders.models.PurchaseApproval.consume", side_effect=OperationalError("database table is locked")),
            self.assertRaises(ApprovalLockError),
        ):
            ApprovalService.consume_approval(token, order_reference="ORD-LOCK-FAIL")

        # Verify state is untouched and remains APPROVED
        refreshed = PurchaseApproval.objects.get(token=token)
        self.assertEqual(refreshed.state, "APPROVED")
        self.assertIsNone(refreshed.consumed_at)
