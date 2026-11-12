"""Deterministic policy engine and rule evaluators for AI Cart (formerly TrustCart).

Implements POL-01, POL-02, POL-03, POL-04:
- Deterministic Python logic (zero Gemini reasoning authority).
- Outcomes: ELIGIBLE, INELIGIBLE, UNKNOWN.
- Critical evidence uncertainty fails closed: missing critical facts NEVER produce ELIGIBLE.
- Exact Decimal monetary precision (unit price * quantity, zero float).
- Hard budget boundary checks.
- Audit evidence provenance on every rule decision.
"""

import logging
import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from django.utils import timezone

from catalog.models import ProductEvidence
from contracts.models import PurchaseContract

logger = logging.getLogger(__name__)


@dataclass
class RuleEvaluationRecord:
    """Record of a single policy rule evaluation."""

    rule_name: str
    outcome: str  # "PASS", "FAIL", "UNKNOWN"
    expected_value: Any
    observed_value: Any
    message: str
    evidence_source: str
    retrieval_timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PolicyEvaluationResult:
    """Consolidated deterministic policy evaluation result for a product."""

    outcome: str  # "ELIGIBLE", "INELIGIBLE", "UNKNOWN"
    unit_price: Decimal
    quantity: int
    total_item_price: Decimal
    budget_ceiling: Decimal
    currency: str
    preference_score: int  # 0 to 100
    matched_preferences: list[str]
    missed_preferences: list[str]
    rule_results: list[RuleEvaluationRecord]
    summary: str
    shipping_tax_disclosure: str

    def to_dict(self) -> dict:
        return {
            "outcome": self.outcome,
            "unit_price": str(self.unit_price),
            "quantity": self.quantity,
            "total_item_price": str(self.total_item_price),
            "budget_ceiling": str(self.budget_ceiling),
            "currency": self.currency,
            "preference_score": self.preference_score,
            "matched_preferences": self.matched_preferences,
            "missed_preferences": self.missed_preferences,
            "rule_results": [r.to_dict() for r in self.rule_results],
            "summary": self.summary,
            "shipping_tax_disclosure": self.shipping_tax_disclosure,
        }


class PolicyEngine:
    """Deterministic policy engine evaluating ProductEvidence against a confirmed PurchaseContract."""

    SHIPPING_TAX_DISCLOSURE = (
        "Base item cost calculated from catalog evidence. "
        "Seller shipping rates, state sales tax, and import duties are not confirmed; "
        "total final checkout affordability cannot be guaranteed until merchant checkout."
    )

    def evaluate(
        self,
        contract: PurchaseContract,
        product: ProductEvidence,
    ) -> PolicyEvaluationResult:
        """Run all mandatory rules and preference scoring deterministically."""
        records: list[RuleEvaluationRecord] = []

        now_str = timezone.now().isoformat()
        evidence_source = product.source_merchant or ("Local Fixture" if product.is_fixture else "Channel3 API")

        # 1. Currency Rule
        currency_record = self._check_currency(contract, product, evidence_source, now_str)
        records.append(currency_record)

        # 2. Positive Decimal Price Rule
        price_record = self._check_positive_price(product, evidence_source, now_str)
        records.append(price_record)

        # 3. Budget Ceiling Rule (unit price * quantity)
        unit_price = product.price if isinstance(product.price, Decimal) else Decimal(str(product.price or "0.00"))
        quantity = contract.quantity or 1
        total_item_price = unit_price * Decimal(quantity)

        budget_record = self._check_budget_ceiling(
            total_item_price, contract.max_budget, contract.currency, evidence_source, now_str
        )
        records.append(budget_record)

        # 4. Availability Rule
        stock_record = self._check_availability(product, evidence_source, now_str)
        records.append(stock_record)

        # 5. Excluded Terms Rule
        excluded_record = self._check_excluded_terms(contract, product, evidence_source, now_str)
        records.append(excluded_record)

        # 6. Category Compatibility Rule
        category_record = self._check_category_compatibility(contract, product, evidence_source, now_str)
        records.append(category_record)

        # 7. Required Specifications Rule
        required_specs_records = self._check_required_specs(contract, product, evidence_source, now_str)
        records.extend(required_specs_records)

        # 8. Preference Scoring
        pref_score, matched_prefs, missed_prefs = self._evaluate_preferences(contract, product)

        # Determine Final Consolidated Outcome:
        # Invariant: If ANY rule FAIL -> INELIGIBLE
        # Invariant: If NO rule FAIL, but ANY rule UNKNOWN -> UNKNOWN (Missing critical facts never produce ELIGIBLE)
        # Invariant: If ALL rules PASS -> ELIGIBLE
        has_failure = any(r.outcome == "FAIL" for r in records)
        has_unknown = any(r.outcome == "UNKNOWN" for r in records)

        if has_failure:
            outcome = "INELIGIBLE"
            fail_reasons = [r.message for r in records if r.outcome == "FAIL"]
            summary = f"Ineligible: {'; '.join(fail_reasons)}"
        elif has_unknown:
            outcome = "UNKNOWN"
            unknown_reasons = [r.message for r in records if r.outcome == "UNKNOWN"]
            summary = f"Uncertain: {'; '.join(unknown_reasons)}"
        else:
            outcome = "ELIGIBLE"
            summary = f"Eligible: Meets all {len(records)} mandatory constraints with {pref_score}% preference match."

        return PolicyEvaluationResult(
            outcome=outcome,
            unit_price=unit_price,
            quantity=quantity,
            total_item_price=total_item_price,
            budget_ceiling=contract.max_budget,
            currency=contract.currency,
            preference_score=pref_score,
            matched_preferences=matched_prefs,
            missed_preferences=missed_prefs,
            rule_results=records,
            summary=summary,
            shipping_tax_disclosure=self.SHIPPING_TAX_DISCLOSURE,
        )

    def _check_currency(
        self,
        contract: PurchaseContract,
        product: ProductEvidence,
        source: str,
        timestamp: str,
    ) -> RuleEvaluationRecord:
        expected = contract.currency or "USD"
        observed = product.currency or "Unknown"

        if observed.upper() == expected.upper():
            return RuleEvaluationRecord(
                rule_name="CurrencyMatch",
                outcome="PASS",
                expected_value=expected,
                observed_value=observed,
                message=f"Currency matches expected {expected}.",
                evidence_source=source,
                retrieval_timestamp=timestamp,
            )
        return RuleEvaluationRecord(
            rule_name="CurrencyMatch",
            outcome="FAIL",
            expected_value=expected,
            observed_value=observed,
            message=f"Currency mismatch: expected {expected}, observed {observed}.",
            evidence_source=source,
            retrieval_timestamp=timestamp,
        )

    def _check_positive_price(
        self,
        product: ProductEvidence,
        source: str,
        timestamp: str,
    ) -> RuleEvaluationRecord:
        price = product.price
        if price is not None and isinstance(price, Decimal) and price > Decimal("0.00"):
            return RuleEvaluationRecord(
                rule_name="PositivePrice",
                outcome="PASS",
                expected_value="> 0.00",
                observed_value=str(price),
                message=f"Price is a valid positive Decimal: ${price}.",
                evidence_source=source,
                retrieval_timestamp=timestamp,
            )
        return RuleEvaluationRecord(
            rule_name="PositivePrice",
            outcome="FAIL",
            expected_value="> 0.00",
            observed_value=str(price),
            message="Item price is missing, non-positive, or unpriced.",
            evidence_source=source,
            retrieval_timestamp=timestamp,
        )

    def _check_budget_ceiling(
        self,
        total_price: Decimal,
        max_budget: Decimal,
        currency: str,
        source: str,
        timestamp: str,
    ) -> RuleEvaluationRecord:
        diff = total_price - max_budget
        if diff <= Decimal("0.00"):
            return RuleEvaluationRecord(
                rule_name="BudgetCeiling",
                outcome="PASS",
                expected_value=f"<= ${max_budget} {currency}",
                observed_value=f"${total_price} {currency}",
                message=f"Total price ${total_price} is within budget ceiling ${max_budget} {currency}.",
                evidence_source=source,
                retrieval_timestamp=timestamp,
            )
        return RuleEvaluationRecord(
            rule_name="BudgetCeiling",
            outcome="FAIL",
            expected_value=f"<= ${max_budget} {currency}",
            observed_value=f"${total_price} {currency}",
            message=f"Total price ${total_price} exceeds maximum budget ceiling ${max_budget} by ${diff} {currency}.",
            evidence_source=source,
            retrieval_timestamp=timestamp,
        )

    def _check_availability(
        self,
        product: ProductEvidence,
        source: str,
        timestamp: str,
    ) -> RuleEvaluationRecord:
        status = (product.stock_status or "UNKNOWN").upper()
        if status == "IN_STOCK":
            return RuleEvaluationRecord(
                rule_name="StockAvailability",
                outcome="PASS",
                expected_value="IN_STOCK",
                observed_value=status,
                message="Product is confirmed in stock.",
                evidence_source=source,
                retrieval_timestamp=timestamp,
            )
        if status == "OUT_OF_STOCK":
            return RuleEvaluationRecord(
                rule_name="StockAvailability",
                outcome="FAIL",
                expected_value="IN_STOCK",
                observed_value=status,
                message="Product is out of stock.",
                evidence_source=source,
                retrieval_timestamp=timestamp,
            )
        return RuleEvaluationRecord(
            rule_name="StockAvailability",
            outcome="UNKNOWN",
            expected_value="IN_STOCK",
            observed_value=status,
            message="Product stock availability is unverified.",
            evidence_source=source,
            retrieval_timestamp=timestamp,
        )

    def _check_excluded_terms(
        self,
        contract: PurchaseContract,
        product: ProductEvidence,
        source: str,
        timestamp: str,
    ) -> RuleEvaluationRecord:
        excluded = contract.excluded_terms or []
        if not excluded:
            return RuleEvaluationRecord(
                rule_name="ExcludedTerms",
                outcome="PASS",
                expected_value="No excluded terms defined",
                observed_value="None",
                message="No negative constraints specified.",
                evidence_source=source,
                retrieval_timestamp=timestamp,
            )

        # Collect text corpus from product
        corpus_parts = [
            product.brand or "",
            product.title or "",
            product.description or "",
            product.variant_id or "",
            product.sku or "",
            str(product.raw_evidence or ""),
        ]
        corpus = " ".join(corpus_parts).lower()

        found_violations = []
        for term in excluded:
            term_clean = term.strip().lower()
            if term_clean and term_clean in corpus:
                found_violations.append(term)

        if found_violations:
            return RuleEvaluationRecord(
                rule_name="ExcludedTerms",
                outcome="FAIL",
                expected_value=f"Exclude: {', '.join(excluded)}",
                observed_value=f"Found: {', '.join(found_violations)}",
                message=f"Product violates negative constraint; contains excluded term(s): {', '.join(found_violations)}.",
                evidence_source=source,
                retrieval_timestamp=timestamp,
            )

        return RuleEvaluationRecord(
            rule_name="ExcludedTerms",
            outcome="PASS",
            expected_value=f"Exclude: {', '.join(excluded)}",
            observed_value="None found",
            message=f"No excluded terms detected ({len(excluded)} checked).",
            evidence_source=source,
            retrieval_timestamp=timestamp,
        )

    ACCESSORY_OR_PART_TERMS = (
        "case",
        "cover",
        "bumper",
        "folio",
        "pouch",
        "sleeve",
        "shell",
        "skin",
        "decal",
        "screen protector",
        "tempered glass",
        "protector",
        "holster",
        "holder",
        "mount",
        "cradle",
        "stand",
        "dock",
        "tripod",
        "strap",
        "band",
        "lanyard",
        "adapter",
        "dongle",
        "splitter",
        "cable",
        "cord",
        "charger",
        "charging pad",
        "power bank",
        "replacement battery",
        "replacement screen",
        "replacement part",
        "lcd replacement",
        "digitizer",
        "back glass",
        "earpad",
        "ear cushion",
        "headband cover",
        "headband pad",
        "keycap",
        "switch opener",
        "wrist rest",
        "desk mat",
        "chair mat",
        "caster",
        "gas lift",
        "armrest pad",
        "dummy phone",
        "prop phone",
        "empty box",
    )

    DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
        "smartphones": ("iphone", "galaxy", "pixel", "smartphone", "cell phone", "mobile phone", "oneplus"),
        "headphones": ("headphone", "earphone", "earbud", "headset"),
        "keyboards": ("keyboard", "tenkeyless", "tkl"),
        "laptops": ("laptop", "notebook", "macbook", "ultrabook", "thinkpad", "chromebook"),
        "chairs": ("office chair", "ergonomic chair", "desk chair", "mesh chair", "task chair"),
        "footwear": ("shoe", "sneaker", "boot", "sandal", "running shoe", "footwear"),
    }

    def _check_category_compatibility(
        self,
        contract: PurchaseContract,
        product: ProductEvidence,
        source: str,
        timestamp: str,
    ) -> RuleEvaluationRecord:
        req_category = (contract.category or "").lower().strip()
        req_desc = (contract.product_description or "").lower().strip()
        req_prompt = (contract.raw_prompt or "").lower().strip()
        req_corpus = f"{req_category} {req_desc} {req_prompt}"

        prod_title = (product.title or "").lower()
        prod_desc = (product.description or "").lower()
        raw_ev = product.raw_evidence if isinstance(product.raw_evidence, dict) else {}
        prod_cat_meta = " ".join(
            str(raw_ev.get(k, "") or "")
            for k in ("category", "product_type", "subcategory", "type")
        ).lower()
        title_and_type = f"{prod_title} {prod_cat_meta}".strip()
        prod_raw = str(product.raw_evidence or "").lower()
        combined_prod = f"{prod_title} {prod_desc} {prod_raw}"

        # 1. Fail closed on accessories, cases, covers, and replacement parts unless explicitly requested
        for term in self.ACCESSORY_OR_PART_TERMS:
            pat = rf"\b{re.escape(term)}(?:es|s)?\b"
            if re.search(pat, title_and_type) and not re.search(pat, req_corpus):
                return RuleEvaluationRecord(
                    rule_name="CategoryCompatibility",
                    outcome="FAIL",
                    expected_value=contract.category or contract.product_description,
                    observed_value=f"Accessory/part mismatch ({term})",
                    message=(
                        f"Incompatible product type: item is an accessory or part ('{term}'), "
                        f"not the requested {contract.product_description or contract.category}."
                    ),
                    evidence_source=source,
                    retrieval_timestamp=timestamp,
                )

        # Also catch explicit compatibility/replacement framing in description ("case for iphone", "replacement for iphone")
        for_device_pat = (
            r"\b(?:case|cover|protector|charger|cable|adapter|replacement|screen|battery|parts?)\s+"
            r"(?:for|fits|compatible\s+with)\s+(?:iphone|apple|samsung|galaxy|pixel|macbook|laptop|headphones|keyboard|chair)\b"
        )
        if re.search(for_device_pat, f"{prod_title} {prod_desc}") and not any(
            re.search(rf"\b{re.escape(t)}(?:es|s)?\b", req_corpus)
            for t in ("case", "cover", "protector", "charger", "cable", "adapter", "replacement", "battery", "screen")
        ):
            return RuleEvaluationRecord(
                rule_name="CategoryCompatibility",
                outcome="FAIL",
                expected_value=contract.category or contract.product_description,
                observed_value="Accessory/replacement listing",
                message=(
                    f"Incompatible product type: listing appears to be an accessory or replacement component "
                    f"for {contract.product_description or contract.category}, not the device itself."
                ),
                evidence_source=source,
                retrieval_timestamp=timestamp,
            )

        # 2. Cross-domain mismatch check (e.g., requesting Smartphone vs Headphones/Laptop product)
        req_domain = next(
            (dom for dom, kws in self.DOMAIN_KEYWORDS.items() if any(re.search(rf"\b{re.escape(kw)}s?\b", req_corpus) for kw in kws)),
            None,
        )
        if req_domain:
            other_domains = [
                dom for dom, kws in self.DOMAIN_KEYWORDS.items()
                if dom != req_domain and any(re.search(rf"\b{re.escape(kw)}s?\b", title_and_type) for kw in kws)
            ]
            req_domain_hit = any(re.search(rf"\b{re.escape(kw)}s?\b", title_and_type) for kw in self.DOMAIN_KEYWORDS[req_domain])
            if other_domains and not req_domain_hit:
                return RuleEvaluationRecord(
                    rule_name="CategoryCompatibility",
                    outcome="FAIL",
                    expected_value=contract.category or contract.product_description,
                    observed_value=f"Different category ({other_domains[0]})",
                    message=(
                        f"Incompatible product type: item belongs to '{other_domains[0]}', "
                        f"not requested '{req_domain}'."
                    ),
                    evidence_source=source,
                    retrieval_timestamp=timestamp,
                )

        # 3. Positive keyword compatibility check
        cat_words = [w for w in req_category.replace("/", " ").replace("&", " ").replace(">", " ").split() if len(w) > 3]
        desc_words = [w for w in req_desc.split() if len(w) > 3]

        matches = [w for w in cat_words + desc_words if w in combined_prod]

        if matches:
            return RuleEvaluationRecord(
                rule_name="CategoryCompatibility",
                outcome="PASS",
                expected_value=contract.category,
                observed_value=f"Matched keywords: {', '.join(set(matches))}",
                message=f"Product is compatible with requested category '{contract.category}'.",
                evidence_source=source,
                retrieval_timestamp=timestamp,
            )

        return RuleEvaluationRecord(
            rule_name="CategoryCompatibility",
            outcome="UNKNOWN",
            expected_value=contract.category,
            observed_value=product.title,
            message=f"Category compatibility for '{contract.category}' could not be definitively verified.",
            evidence_source=source,
            retrieval_timestamp=timestamp,
        )

    def _check_required_specs(
        self,
        contract: PurchaseContract,
        product: ProductEvidence,
        source: str,
        timestamp: str,
    ) -> list[RuleEvaluationRecord]:
        specs = contract.required_specs or {}
        if not specs:
            return [
                RuleEvaluationRecord(
                    rule_name="RequiredSpecs",
                    outcome="PASS",
                    expected_value="No required specs",
                    observed_value="None",
                    message="No required specifications specified.",
                    evidence_source=source,
                    retrieval_timestamp=timestamp,
                )
            ]

        records = []
        corpus_parts = [
            product.title or "",
            product.description or "",
            product.brand or "",
            product.variant_id or "",
            product.sku or "",
            str(product.raw_evidence or ""),
        ]
        corpus = " ".join(corpus_parts).lower()

        for spec_key, spec_val in specs.items():
            val_str = str(spec_val).strip().lower()

            # Check if value keywords exist in product evidence
            val_tokens = [tok for tok in val_str.replace("/", " ").replace("-", " ").split() if len(tok) >= 3]
            match_found = any(tok in corpus for tok in val_tokens) if val_tokens else (val_str in corpus)

            rule_label = f"RequiredSpec:{spec_key}"
            if match_found:
                records.append(
                    RuleEvaluationRecord(
                        rule_name=rule_label,
                        outcome="PASS",
                        expected_value=f"{spec_key}: {spec_val}",
                        observed_value="Verified in product evidence",
                        message=f"Required specification '{spec_key}: {spec_val}' is satisfied.",
                        evidence_source=source,
                        retrieval_timestamp=timestamp,
                    )
                )
            else:
                # Critical requirement cannot be verified: fails closed to UNKNOWN
                records.append(
                    RuleEvaluationRecord(
                        rule_name=rule_label,
                        outcome="UNKNOWN",
                        expected_value=f"{spec_key}: {spec_val}",
                        observed_value="Not found in title, description, or attributes",
                        message=f"Critical required spec '{spec_key}: {spec_val}' could not be verified from available evidence.",
                        evidence_source=source,
                        retrieval_timestamp=timestamp,
                    )
                )

        return records

    def _evaluate_preferences(
        self,
        contract: PurchaseContract,
        product: ProductEvidence,
    ) -> tuple[int, list[str], list[str]]:
        """Compute transparent deterministic preference score (0 to 100)."""
        prefs = contract.preferred_specs or {}
        if not prefs:
            return 100, [], []

        corpus = f"{product.title} {product.description} {product.brand} {product.raw_evidence}".lower()
        matched = []
        missed = []

        for pref_key, pref_val in prefs.items():
            val_tokens = [tok for tok in str(pref_val).lower().replace("/", " ").split() if len(tok) >= 3]
            matched_flag = any(tok in corpus for tok in val_tokens) if val_tokens else (str(pref_val).lower() in corpus)

            label = f"{pref_key}: {pref_val}"
            if matched_flag:
                matched.append(label)
            else:
                missed.append(label)

        total_prefs = len(prefs)
        score = int((len(matched) / total_prefs) * 100) if total_prefs > 0 else 100
        return score, matched, missed
