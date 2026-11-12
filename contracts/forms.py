"""
Django forms for Purchase Contract intake, editing, and confirmation.
Independent server-side business requirement validation.
"""

import json
from decimal import Decimal
from typing import Any

from django import forms
from django.core.exceptions import ValidationError

from contracts.models import PurchaseContract


class PromptIntakeForm(forms.Form):
    """Shopper natural language prompt intake form with optional collapsed preferences."""

    prompt = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "id": "shopper-prompt-input",
                "class": "tc-textarea",
                "rows": 3,
                "maxlength": "2000",
                "placeholder": "Describe what you need, your budget, and any must-haves (e.g., 'Wireless mechanical keyboard with quiet switches under $100')...",
            }
        ),
        max_length=2000,
        min_length=3,
        error_messages={
            "max_length": "Your shopping request cannot exceed 2,000 characters.",
            "min_length": "Please provide a more descriptive shopping request (at least 3 characters).",
            "required": "Please enter a shopping request or select a sample scenario.",
        },
    )
    max_budget = forms.DecimalField(
        required=False,
        min_value=Decimal("0.01"),
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={
                "id": "refine-max-budget",
                "class": "tc-input tc-input-sm",
                "placeholder": "e.g. 150.00",
                "step": "0.01",
            }
        ),
    )
    excluded_terms = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "id": "refine-excluded-terms",
                "class": "tc-input tc-input-sm",
                "placeholder": "e.g. refurbished, used",
            }
        ),
    )
    quantity = forms.IntegerField(
        required=False,
        min_value=1,
        initial=1,
        widget=forms.NumberInput(
            attrs={
                "id": "refine-quantity",
                "class": "tc-input tc-input-sm",
                "min": "1",
                "value": "1",
            }
        ),
    )
    scenario_key = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )

    def clean_prompt(self) -> str:
        data = self.cleaned_data.get("prompt", "").strip()
        if not data:
            raise ValidationError("Shopping request cannot be blank.")
        if len(data) > 2000:
            raise ValidationError("Shopping request cannot exceed 2,000 characters.")
        return data


class ContractReviewForm(forms.ModelForm):
    """
    Contract review and granular editing form.
    Provides independent server-side validation enforcing business invariants.
    """

    required_specs_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )
    preferred_specs_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )
    excluded_terms_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )
    ambiguous_requirements_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = PurchaseContract
        fields = [
            "category",
            "product_description",
            "max_budget",
            "currency",
            "quantity",
        ]
        widgets = {
            "category": forms.TextInput(attrs={"class": "tc-input", "maxlength": "255"}),
            "product_description": forms.Textarea(attrs={"class": "tc-textarea", "rows": 3}),
            "max_budget": forms.NumberInput(attrs={"class": "tc-input", "step": "0.01", "min": "0.01"}),
            "currency": forms.TextInput(attrs={"class": "tc-input tc-input-readonly", "readonly": "readonly"}),
            "quantity": forms.NumberInput(attrs={"class": "tc-input", "min": "1"}),
        }

    def clean_max_budget(self) -> Decimal:
        budget = self.cleaned_data.get("max_budget")
        if budget is None or budget <= Decimal("0.00"):
            raise ValidationError("Budget ceiling must be greater than $0.00.")
        return budget.quantize(Decimal("0.01"))

    def clean_currency(self) -> str:
        curr = self.cleaned_data.get("currency", "").strip().upper()
        if curr != "USD":
            raise ValidationError("Only USD currency is supported in this demonstration.")
        return "USD"

    def clean_quantity(self) -> int:
        qty = self.cleaned_data.get("quantity")
        if qty is None or qty < 1:
            raise ValidationError("Quantity must be at least 1.")
        return qty

    def clean_required_specs_json(self) -> dict[str, Any]:
        raw = self.cleaned_data.get("required_specs_json", "").strip()
        if not raw:
            return self.instance.required_specs or {}
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValidationError("Required specifications must be a JSON dictionary.")
            return parsed
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON for required specs: {exc!s}") from exc

    def clean_preferred_specs_json(self) -> dict[str, Any]:
        raw = self.cleaned_data.get("preferred_specs_json", "").strip()
        if not raw:
            return self.instance.preferred_specs or {}
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValidationError("Preferred specifications must be a JSON dictionary.")
            return parsed
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON for preferred specs: {exc!s}") from exc

    def clean_excluded_terms_json(self) -> list[str]:
        raw = self.cleaned_data.get("excluded_terms_json", "").strip()
        if not raw:
            return self.instance.excluded_terms or []
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValidationError("Excluded terms must be a JSON list.")
            return [str(x).strip() for x in parsed if str(x).strip()]
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON for excluded terms: {exc!s}") from exc

    def clean_ambiguous_requirements_json(self) -> list[str]:
        raw = self.cleaned_data.get("ambiguous_requirements_json", "").strip()
        if not raw:
            return self.instance.ambiguous_requirements or []
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValidationError("Ambiguous requirements must be a JSON list.")
            return [str(x).strip() for x in parsed if str(x).strip()]
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON for ambiguous requirements: {exc!s}") from exc

    def save(self, commit: bool = True) -> PurchaseContract:
        contract = super().save(commit=False)
        if "required_specs_json" in self.cleaned_data:
            contract.required_specs = self.cleaned_data["required_specs_json"]
        if "preferred_specs_json" in self.cleaned_data:
            contract.preferred_specs = self.cleaned_data["preferred_specs_json"]
        if "excluded_terms_json" in self.cleaned_data:
            contract.excluded_terms = self.cleaned_data["excluded_terms_json"]
        if "ambiguous_requirements_json" in self.cleaned_data:
            contract.ambiguous_requirements = self.cleaned_data["ambiguous_requirements_json"]

        if commit:
            contract.full_clean()
            contract.save()
        return contract


class BudgetRevisionForm(forms.Form):
    """Server-side validation form for creating a revised-budget PurchaseContract version."""

    max_budget = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_digits=10,
        decimal_places=2,
        error_messages={
            "required": "Please enter a valid revised budget amount.",
            "invalid": "Enter a valid dollar amount (for example, 185.00).",
            "min_value": "Budget must be greater than $0.00 USD.",
            "max_digits": "Budget cannot exceed $99,999,999.99 USD.",
            "max_decimal_places": "Budget can have at most two decimal places.",
        },
    )

    def clean_max_budget(self) -> Decimal:
        budget = self.cleaned_data.get("max_budget")
        if budget is None or budget <= Decimal("0.00"):
            raise ValidationError("Revised budget ceiling must be greater than $0.00 USD.")
        return budget.quantize(Decimal("0.01"))
