"""Policy evaluation orchestration service for AI Cart (formerly TrustCart).

Implements POL-01, POL-02, POL-03, POL-04:
- Evaluates candidate ProductEvidence items against a confirmed PurchaseContract.
- Persists PolicyEvaluationReport records for full auditability.
- Server-side revalidation guarantees zero trust in browser-supplied data.
"""

import logging

from django.utils import timezone

from catalog.services import ProductSearchService
from contracts.models import PurchaseContract
from policies.engine import PolicyEngine
from policies.models import PolicyEvaluationReport

logger = logging.getLogger(__name__)


class PolicyEvaluationService:
    """Orchestrates deterministic policy evaluation across candidate products for a contract."""

    def __init__(
        self,
        engine: PolicyEngine | None = None,
        search_service: ProductSearchService | None = None,
    ):
        self.engine = engine or PolicyEngine()
        self.search_service = search_service or ProductSearchService()

    def evaluate_contract_products(
        self,
        contract: PurchaseContract,
        force_refresh: bool = False,
    ) -> list[PolicyEvaluationReport]:
        """Evaluate all candidate products for a confirmed contract.

        Revalidates contract state and product evidence server-side.
        """
        if contract.state != "CONFIRMED":
            raise ValueError(f"Contract v{contract.version} must be CONFIRMED before policy evaluation.")

        # Discover or load candidate products
        products, _is_fallback, _msg = self.search_service.search_for_contract(
            contract, force_refresh=force_refresh
        )

        reports: list[PolicyEvaluationReport] = []
        now = timezone.now()

        for product in products:
            result = self.engine.evaluate(contract, product)

            report, _ = PolicyEvaluationReport.objects.update_or_create(
                contract=contract,
                product=product,
                defaults={
                    "outcome": result.outcome,
                    "unit_price": result.unit_price,
                    "quantity": result.quantity,
                    "total_item_price": result.total_item_price,
                    "budget_ceiling": result.budget_ceiling,
                    "currency": result.currency,
                    "preference_score": result.preference_score,
                    "rule_results": [r.to_dict() for r in result.rule_results],
                    "matched_preferences": result.matched_preferences,
                    "missed_preferences": result.missed_preferences,
                    "summary": result.summary,
                    "shipping_tax_disclosure": result.shipping_tax_disclosure,
                    "evaluated_at": now,
                },
            )
            reports.append(report)

        # Sort: ELIGIBLE first (by preference score desc, total price asc), then UNKNOWN, then INELIGIBLE
        outcome_order = {"ELIGIBLE": 0, "UNKNOWN": 1, "INELIGIBLE": 2}
        reports.sort(key=lambda r: (outcome_order.get(r.outcome, 3), -r.preference_score, r.total_item_price))

        return reports
