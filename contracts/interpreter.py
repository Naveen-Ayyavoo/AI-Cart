"""
Deterministic shopper request preservation, contradiction detection, and
human-readable specification formatting for AI Cart Purchase Contracts.

Invariants:
- Zero external API calls, zero spend.
- Never silently replaces an unrecognized or failed prompt with an unrelated demo contract.
- Only extracts facts explicitly stated in the shopper prompt; never invents specs.
- Preserves raw structured backend keys while providing natural shopper-facing presentation.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

SPEC_LABEL_MAP: dict[str, str] = {
    "connectivity": "Connectivity",
    "connection": "Connectivity",
    "noise_cancelling": "Noise cancellation",
    "noise_canceling": "Noise cancellation",
    "form_factor": "Design",
    "battery_life": "Battery life",
    "color": "Colour",
    "colour": "Colour",
    "condition": "Condition",
    "storage": "Storage",
    "ram": "Memory (RAM)",
    "screen_size": "Screen size",
    "carrier": "Carrier / Lock status",
    "switch_type": "Switch type",
    "layout": "Layout",
    "backlight": "Backlighting",
    "material": "Material",
    "lumbar_support": "Lumbar support",
    "armrests": "Armrests",
    "weight_capacity": "Weight capacity",
    "shoe_size": "Shoe size",
    "width": "Width",
    "fit": "Fit",
    "size": "Size",
}

DOMAIN_KEYWORD_GROUPS: list[tuple[str, str, tuple[str, ...]]] = [
    ("smartphones", "Electronics > Smartphones", ("iphone", "galaxy s", "pixel phone", "smartphone", "cell phone", "mobile phone", "android phone", "pro max")),
    ("laptops", "Computers > Laptops", ("laptop", "macbook", "notebook", "thinkpad", "ultrabook", "chromebook")),
    ("keyboards", "Computers > Accessories > Keyboards", ("keyboard", "keychron", "tenkeyless", "tkl")),
    ("headphones", "Electronics > Audio > Headphones", ("headphone", "headphones", "earbud", "earbuds", "earphone", "earphones", "headset", "airpods")),
    ("chairs", "Furniture > Office Chairs", ("office chair", "ergonomic chair", "desk chair", "chair")),
    ("footwear", "Apparel & Footwear > Shoes", ("running shoe", "shoes", "sneaker", "sneakers", "boots", "sandals")),
    ("apparel_pants", "Apparel > Clothing > Pants", ("pants", "trousers", "jeans", "chinos", "joggers", "shorts")),
    ("apparel_tops", "Apparel > Clothing", ("shirt", "jacket", "hoodie", "sweater", "coat")),
    ("kitchen", "Home & Kitchen", ("coffee maker", "espresso", "air fryer", "blender", "kettle", "toaster", "cookware")),
]

BUDGET_PATTERNS: list[re.Pattern[str]] = [
    # "$1,000", "$1000.00", "$ 150"
    re.compile(r"\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)"),
    # "1000$", "1,000.50 $"
    re.compile(r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*\$"),
    # "1000 usd", "1000 dollars"
    re.compile(r"\b([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*(?:usd|dollars?)\b", re.IGNORECASE),
    # "under 1000", "below 500", "max 250", "up to 1000"
    re.compile(r"\b(?:under|below|max|maximum|budget(?:\s+of)?|up\s+to|less\s+than)\s+\$?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)\b", re.IGNORECASE),
]

BRAND_NORMALIZATIONS: dict[str, str] = {
    "iphone": "iPhone",
    "ipad": "iPad",
    "macbook": "MacBook",
    "airpods": "AirPods",
    "samsung": "Samsung",
    "pixel": "Pixel",
    "sony": "Sony",
    "bose": "Bose",
    "jbl": "JBL",
    "keychron": "Keychron",
    "usb-c": "USB-C",
    "anc": "ANC",
}


def extract_explicit_budget(prompt: str) -> Decimal | None:
    """Extract an explicitly stated USD budget amount from prompt text, or None if absent."""
    if not prompt:
        return None
    for pat in BUDGET_PATTERNS:
        m = pat.search(prompt)
        if m:
            raw_num = m.group(1).replace(",", "").strip()
            try:
                val = Decimal(raw_num).quantize(Decimal("0.01"))
                if val > Decimal("0.00"):
                    return val
            except (InvalidOperation, ValueError):
                continue
    return None


def _detect_domain(text: str) -> tuple[str, str]:
    low = (text or "").lower()
    for domain_key, cat_label, kws in DOMAIN_KEYWORD_GROUPS:
        for kw in kws:
            if re.search(rf"\b{re.escape(kw)}\b", low):
                return domain_key, cat_label
    return "general", "General Merchandise"


def _has_negated_term(low_prompt: str, term: str) -> bool:
    neg_pat = rf"\b(?:no|not|without|exclude|excluding|avoid|never|non[-\s]?)\s*{re.escape(term)}\b"
    return bool(re.search(neg_pat, low_prompt))


def _has_positive_term(low_prompt: str, term: str) -> bool:
    for m in re.finditer(rf"\b{re.escape(term)}\b", low_prompt):
        prefix = low_prompt[max(0, m.start() - 24) : m.start()]
        if not re.search(r"\b(?:no|not|without|exclude|excluding|avoid|never|non)\s*[-]?$", prefix.strip()):
            return True
    return False


def _clean_product_title(prompt: str) -> str:
    """Derive a readable product title strictly from the shopper prompt without altering product identity."""
    text = re.sub(r"\s+", " ", (prompt or "").strip())
    # Remove parenthetical suffix injected internally by views if re-parsed
    text = re.sub(r"\s*\((?:budget under|exclude|quantity:)[^)]*\)\s*$", "", text, flags=re.IGNORECASE)
    # Remove leading filler verbs
    text = re.sub(
        r"^(?:i\s+want(?:\s+to\s+buy)?|i\s+need|looking\s+for|find\s+me|search\s+for|get\s+me)\s+(?:a|an|some)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Remove explicit exclusion phrases ("no wired", "exclude membrane")
    text = re.sub(
        r"\b(?:with\s+)?(?:no|not|without|exclude|excluding|avoid)\s+[^,.!?;]+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Remove trailing budget phrases ("for under $1000", "under 1000$", "budget $150")
    text = re.sub(
        r"\b(?:for\s+)?(?:under|below|max|maximum|up\s+to|less\s+than)\s+\$?\s*[0-9][0-9,]*(?:\.[0-9]{1,2})?\s*\$?(?:\s*usd)?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\$\s*[0-9][0-9,]*(?:\.[0-9]{1,2})?|[0-9][0-9,]*(?:\.[0-9]{1,2})?\s*\$", "", text)
    text = re.sub(r"\s+", " ", text).strip(" ,.;:-")
    if not text:
        return (prompt or "").strip()[:160]

    words = text.split()
    out_words = []
    for w in words:
        lw = w.lower()
        if lw in BRAND_NORMALIZATIONS:
            out_words.append(BRAND_NORMALIZATIONS[lw])
        elif len(w) <= 3 and w.isalpha() and lw not in {"pro", "max", "air", "for", "and", "red", "new"}:
            out_words.append(w)
        elif w.islower():
            out_words.append(w.capitalize())
        else:
            out_words.append(w)
    return " ".join(out_words)[:200]


def parse_explicit_shopper_request(
    raw_prompt: str,
    max_budget_override: Decimal | None = None,
    quantity_override: int | None = None,
) -> dict[str, Any]:
    """Deterministically extract ONLY explicitly stated product identity, category,
    budget, condition preferences, and exclusions from a shopper prompt.

    Never pulls unrelated demo products, categories, or fabricated specifications.
    """
    prompt = (raw_prompt or "").strip()
    low = prompt.lower()

    _domain_key, category = _detect_domain(prompt)
    product_description = _clean_product_title(prompt)

    explicit_budget = extract_explicit_budget(prompt)
    effective_budget = max_budget_override or explicit_budget
    budget_explicitly_stated = effective_budget is not None
    if effective_budget is None or effective_budget <= Decimal("0.00"):
        # Positive Decimal placeholder required by schema, flagged clearly for review confirmation
        effective_budget = Decimal("100.00")

    qty = quantity_override if (quantity_override and quantity_override >= 1) else 1
    qty_match = re.search(r"\b([1-9][0-9]?)\s*(?:units?|pcs?|pieces?|pairs?|packs?)\b", low)
    if not quantity_override and qty_match:
        qty = int(qty_match.group(1))

    required_specs: dict[str, str] = {}
    preferred_specs: dict[str, str] = {}
    excluded_terms: list[str] = []

    # Condition polarity check (never invert positive 'refurbished' into an exclusion)
    for cond_term, cond_label in (
        ("refurbished", "Refurbished"),
        ("renewed", "Renewed"),
        ("open box", "Open-box"),
        ("used", "Used"),
    ):
        if _has_negated_term(low, cond_term):
            excluded_terms.append(cond_term)
        elif _has_positive_term(low, cond_term):
            preferred_specs["condition"] = cond_label

    # Additional explicit negative exclusions (only if explicitly negated)
    neg_phrases = re.findall(r"\b(?:no|without|exclude|excluding|avoid)\s+([a-z0-9][a-z0-9\-\s]{1,28})", low)
    for phrase in neg_phrases:
        cleaned = re.split(r"\b(?:and|or|models?|ones?)\b|[,.!?;]", phrase)[0].strip()
        if cleaned and cleaned not in excluded_terms and cleaned not in {"refurbished", "used", "renewed", "open box"}:
            excluded_terms.append(cleaned)

    # Extract only connectivity / form-factor if explicitly stated in the prompt
    if re.search(r"\bbluetooth\b", low) and not _has_negated_term(low, "bluetooth"):
        required_specs["connectivity"] = "Bluetooth"
    elif re.search(r"\bwireless\b", low) and not _has_negated_term(low, "wireless"):
        preferred_specs["connectivity"] = "Wireless"

    if re.search(r"\bover[-\s]ear\b", low) and not _has_negated_term(low, "over-ear"):
        preferred_specs["form_factor"] = "Over-Ear"
    elif re.search(r"\bon[-\s]ear\b", low) and not _has_negated_term(low, "on-ear"):
        preferred_specs["form_factor"] = "On-Ear"

    if re.search(r"\b(?:active\s+noise[-\s]cancell?(?:ing|ation)|anc)\b", low):
        preferred_specs["noise_cancelling"] = "Active"

    # Storage size if smartphone/laptop prompt explicitly states one (e.g., 256GB, 512 GB, 1TB)
    storage_match = re.search(r"\b(64|128|256|512)\s*gb\b|\b(1|2)\s*tb\b", low)
    if storage_match:
        if storage_match.group(1):
            preferred_specs["storage"] = f"{storage_match.group(1)} GB"
        elif storage_match.group(2):
            preferred_specs["storage"] = f"{storage_match.group(2)} TB"

    ambiguous_requirements: list[str] = []
    if _domain_key == "smartphones":
        if "storage" not in preferred_specs and "storage" not in required_specs:
            ambiguous_requirements.append("storage")
        if "carrier" not in preferred_specs and "carrier" not in required_specs and not re.search(r"\bunlocked\b", low):
            ambiguous_requirements.append("carrier")

    return {
        "category": category,
        "product_description": product_description,
        "max_budget": effective_budget,
        "currency": "USD",
        "quantity": qty,
        "required_specs": required_specs,
        "preferred_specs": preferred_specs,
        "excluded_terms": excluded_terms,
        "ambiguous_requirements": ambiguous_requirements,
        "budget_explicitly_stated": budget_explicitly_stated,
    }


def detect_contract_contradictions(contract) -> list[str]:
    """Compare raw shopper prompt against structured PurchaseContract fields.

    Returns a non-empty list of human-readable contradiction descriptions when a
    material mismatch exists (e.g. prompt wants 'refurbished' but contract excludes
    it, prompt seeks 'iPhone' but contract describes 'headphones', or initial AI
    budget conflicts with explicit prompt ceiling without a user edit/revision).
    """
    from contracts.models import ContractSource

    prompt = (getattr(contract, "raw_prompt", "") or "").strip()
    if not prompt:
        return []

    provenance = getattr(contract, "extraction_provenance", None) or {}
    # Explicit demonstration samples chosen from homepage chips represent fixed scenarios cleanly
    if getattr(contract, "source", "") == ContractSource.DEMO_FIXTURE and not provenance.get("fallback_reason"):
        return []

    user_edited = bool(
        provenance.get("user_edited")
        or provenance.get("last_revision")
        or getattr(contract, "parent_contract_id", None)
    )
    low_prompt = prompt.lower()
    contradictions: list[str] = []

    # 1. Condition / negative-constraint polarity contradiction
    excluded_low = [str(t).strip().lower() for t in (contract.excluded_terms or []) if str(t).strip()]
    for cond in ("refurbished", "renewed", "used", "open box"):
        if _has_positive_term(low_prompt, cond) and any(cond in ex for ex in excluded_low) and not user_edited:
            contradictions.append(
                f"Your original request mentions '{cond}', which conflicts with excluding '{cond}'."
            )

    # 2. Product domain mismatch contradiction (e.g. iPhone prompt turned into Headphones)
    prompt_domain, _ = _detect_domain(prompt)
    contract_domain, _ = _detect_domain(f"{contract.category} {contract.product_description}")
    if (
        prompt_domain != "general"
        and contract_domain != "general"
        and prompt_domain != contract_domain
        and not user_edited
    ):
        contradictions.append(
            f"The structured product ({contract.product_description or contract.category}) "
            f"does not match the product requested in your search ('{prompt[:80]}')."
        )

    # 3. Unedited budget ceiling contradiction against explicit prompt cap
    explicit_budget = extract_explicit_budget(prompt)
    if explicit_budget is not None and not user_edited and contract.max_budget != explicit_budget:
        contradictions.append(
            f"The structured item budget (${contract.max_budget} USD) does not match "
            f"the budget stated in your request (${explicit_budget} USD)."
        )

    return contradictions


def format_spec_label(raw_key: str) -> str:
    """Convert raw machine specification keys into natural shopper-facing labels."""
    clean = re.sub(r"[\s\-]+", "_", str(raw_key or "").strip().lower())
    if clean in SPEC_LABEL_MAP:
        return SPEC_LABEL_MAP[clean]
    return clean.replace("_", " ").strip().capitalize() or "Feature"


def format_spec_value(raw_key: str, raw_value: Any) -> str:
    """Format specification values into natural shopper-friendly wording."""
    val = str(raw_value or "").strip()
    if not val:
        return ""
    key = re.sub(r"[\s\-]+", "_", str(raw_key or "").strip().lower())
    val_low = val.lower()

    if key in ("noise_cancelling", "noise_canceling") and val_low == "active":
        return "Active noise cancellation"
    if key in ("connectivity", "connection") and val_low == "bluetooth":
        return "Bluetooth connectivity"
    if key == "form_factor" and val_low in ("over-ear", "over ear"):
        return "Over-ear"
    if key == "form_factor" and val_low in ("on-ear", "on ear"):
        return "On-ear"
    if key == "form_factor" and val_low in ("in-ear", "in ear"):
        return "In-ear"

    # ">= 30 hours" -> "30+ hours", ">= 275 lbs" -> "275+ lbs"
    ge_match = re.match(r"^>=\s*(.+)$", val)
    if ge_match:
        inner = ge_match.group(1).strip()
        num_unit = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*(.*)$", inner)
        if num_unit:
            suffix = f" {num_unit.group(2).strip()}" if num_unit.group(2).strip() else ""
            return f"{num_unit.group(1)}+{suffix}"
        return f"{inner}+"

    return val


def format_specs_display(specs_dict: dict | None) -> list[dict[str, str]]:
    """Return list of {'key', 'label', 'value', 'raw_value'} dicts for templates."""
    if not isinstance(specs_dict, dict):
        return []
    out = []
    for k, v in specs_dict.items():
        if v is None or not str(v).strip():
            continue
        out.append(
            {
                "key": str(k),
                "label": format_spec_label(str(k)),
                "value": format_spec_value(str(k), v),
                "raw_value": str(v).strip(),
            }
        )
    return out

