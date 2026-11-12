"""
Pydantic extraction schemas for Gemini structured outputs.
Enforces strict typing, rejects unrecognized keys with extra="forbid",
and guarantees exact Decimal monetary precision.
"""

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PurchaseContractExtraction(BaseModel):
    """
    Validated structured output from Google Gemini contract parser.
    Configured with extra='forbid' to reject hallucinated or unparsed keys.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    category: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Target product category hierarchy, e.g. 'Electronics > Audio > Headphones'",
    )
    product_description: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Detailed description of what the shopper wants to purchase",
    )
    max_budget: Decimal = Field(
        ...,
        description="Maximum budget ceiling expressed as exact Decimal in USD",
    )
    currency: Literal["USD"] = Field(
        default="USD",
        description="Transaction currency, strictly USD for US demo market",
    )
    quantity: int = Field(
        default=1,
        ge=1,
        description="Number of units requested by shopper (minimum 1)",
    )
    required_specs: dict[str, Any] = Field(
        default_factory=dict,
        description="Non-negotiable required technical or physical specifications",
    )
    preferred_specs: dict[str, Any] = Field(
        default_factory=dict,
        description="Desirable preferred specifications or nice-to-haves",
    )
    excluded_terms: list[str] = Field(
        default_factory=list,
        description="Brands, attributes, or conditions to strictly exclude (e.g. refurbished, wired)",
    )
    ambiguous_requirements: list[str] = Field(
        default_factory=list,
        description="Aspects of shopper intent that were ambiguous and surfaced for explicit review",
    )

    @field_validator("max_budget")
    @classmethod
    def validate_positive_budget(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0.00"):
            raise ValueError("max_budget must be strictly greater than $0.00")
        # Quantize to 2 decimal places to match USD currency
        return v.quantize(Decimal("0.01"))

    def to_model_kwargs(
        self,
        raw_prompt: str,
        source: str = "GEMINI_LIVE",
        model_used: str = "",
        provenance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Convert validated extraction into keyword arguments for PurchaseContract."""
        return {
            "raw_prompt": raw_prompt,
            "category": self.category,
            "product_description": self.product_description,
            "max_budget": self.max_budget,
            "currency": self.currency,
            "quantity": self.quantity,
            "required_specs": self.required_specs,
            "preferred_specs": self.preferred_specs,
            "excluded_terms": self.excluded_terms,
            "ambiguous_requirements": self.ambiguous_requirements,
            "source": source,
            "model_used": model_used,
            "extraction_provenance": provenance or {},
        }
