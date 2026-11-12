"""
Local demo fixture library for AI Cart (formerly TrustCart).
Zero-Spend Governance (ADR-0004):
When Gemini Free Tier quota is exhausted or offline, the system halts external calls
and cleanly falls back to labeled demo fixtures. Fixture data is never misrepresented
as live Gemini generation.
"""

from decimal import Decimal
from typing import Any

from contracts.models import ContractSource, ContractState, PurchaseContract
from contracts.schemas import PurchaseContractExtraction

FALLBACK_DISCLOSURE = "Sandbox Demo Fixture — Zero-Spend Fallback"

DEMO_SCENARIOS: dict[str, dict[str, Any]] = {
    "headphones": {
        "title": "Wireless Noise-Canceling Headphones under $150",
        "prompt": "I want over-ear wireless headphones with active noise cancellation for under $150. Black preferred with good battery life. No refurbished or wired models.",
        "data": {
            "category": "Electronics > Audio > Headphones",
            "product_description": "Over-ear wireless headphones with active noise cancellation and long battery life",
            "max_budget": Decimal("150.00"),
            "currency": "USD",
            "quantity": 1,
            "required_specs": {
                "connectivity": "Bluetooth",
                "noise_cancelling": "Active",
                "form_factor": "Over-Ear",
            },
            "preferred_specs": {
                "battery_life": ">= 30 hours",
                "color": "Black",
            },
            "excluded_terms": [
                "wired-only",
                "refurbished",
                "on-ear",
            ],
            "ambiguous_requirements": [
                "specific audio codec support (AAC, aptX, or LDAC)",
            ],
        },
    },
    "keyboard": {
        "title": "Mechanical Gaming Keyboard under $100",
        "prompt": "Looking for a tenkeyless mechanical keyboard with tactile switches and RGB lighting for under $100. Must have detachable cable, absolutely no membrane keyboards.",
        "data": {
            "category": "Computers > Accessories > Keyboards",
            "product_description": "Tenkeyless mechanical gaming keyboard with tactile switches",
            "max_budget": Decimal("100.00"),
            "currency": "USD",
            "quantity": 1,
            "required_specs": {
                "switch_type": "Mechanical",
                "layout": "Tenkeyless (TKL)",
            },
            "preferred_specs": {
                "backlight": "RGB",
                "connection": "Detachable USB-C",
            },
            "excluded_terms": [
                "membrane",
                "used",
            ],
            "ambiguous_requirements": [
                "switch brand preference (Cherry MX, Gateron, Outemu)",
            ],
        },
    },
    "chair": {
        "title": "Ergonomic Office Chair under $250",
        "prompt": "Need an ergonomic mesh office chair under $250 with adjustable lumbar support and 3D armrests. No bonded leather or gaming style chairs.",
        "data": {
            "category": "Furniture > Office Chairs",
            "product_description": "Ergonomic mesh desk chair with lumbar support and adjustable armrests",
            "max_budget": Decimal("250.00"),
            "currency": "USD",
            "quantity": 1,
            "required_specs": {
                "material": "Breathable Mesh",
                "lumbar_support": "Adjustable",
            },
            "preferred_specs": {
                "armrests": "3D Adjustable",
                "weight_capacity": ">= 275 lbs",
            },
            "excluded_terms": [
                "gaming style",
                "bonded leather",
            ],
            "ambiguous_requirements": [
                "headrest requirement (integrated vs optional)",
            ],
        },
    },
}


def get_demo_scenario(scenario_key: str, save_to_db: bool = False) -> PurchaseContract:
    """
    Retrieve and validate a predefined demo scenario.
    Returns a PurchaseContract instance marked as DEMO_FIXTURE with disclosure provenance.
    """
    scenario = DEMO_SCENARIOS.get(scenario_key)
    if not scenario:
        available = ", ".join(DEMO_SCENARIOS.keys())
        raise KeyError(
            f"Scenario '{scenario_key}' not found. Available scenarios: {available}"
        )

    # Validate against strict Pydantic extraction schema
    validated = PurchaseContractExtraction(**scenario["data"])

    provenance = {
        "is_fixture": True,
        "scenario_key": scenario_key,
        "disclosure": FALLBACK_DISCLOSURE,
        "scenario_title": scenario["title"],
    }

    kwargs = validated.to_model_kwargs(
        raw_prompt=scenario["prompt"],
        source=ContractSource.DEMO_FIXTURE,
        model_used="demo-fixture-v1",
        provenance=provenance,
    )
    kwargs["state"] = ContractState.DRAFT

    if save_to_db:
        contract = PurchaseContract.objects.create(**kwargs)
    else:
        contract = PurchaseContract(**kwargs)

    contract.full_clean()
    return contract
