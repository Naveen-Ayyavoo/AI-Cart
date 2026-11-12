"""
Session ownership authorization, canonical readable public reference generation,
and safe UUID-to-public-URL resolution helpers for AI Cart.

Security invariants:
- `public_ref` slugs are non-sequential, collision-checked, and derived strictly
  from structured category/brand metadata — NEVER from raw shopper prompts (zero PII).
- `public_ref` is an identifier, NEVER an authorization token. Server-side session
  ownership (`PurchaseContract.owner_session_key`) is enforced before redirecting
  legacy UUID URLs or serving contract/proposal/approval/order details.
"""

import re
import secrets

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.text import slugify

PUBLIC_REF_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def build_safe_slug_prefix(structured_label: str, fallback: str = "shopping-request") -> str:
    """Create a short, ASCII lowercase URL slug strictly from structured category/product metadata."""
    text = (structured_label or "").strip()
    if not text:
        return fallback

    # Prefer leaf or last two hierarchy segments (e.g. "Apparel > Women's Soft Twill Pant")
    if ">" in text:
        parts = [p.strip() for p in text.split(">") if p.strip()]
        if len(parts) >= 2 and len(parts[-1]) < 10:
            text = " ".join(parts[-2:])
        elif parts:
            text = parts[-1]

    # Strip apostrophes so "Women's" -> "womens" instead of "women-s"
    text = re.sub(r"[\u2018\u2019']", "", text)
    base = slugify(text)[:44].strip("-")
    return base or fallback


def generate_unique_public_ref(
    prefix_code: str,
    structured_label: str,
    model_cls,
    fallback: str = "shopping-request",
) -> str:
    """Generate a stable, unique, collision-checked readable public reference."""
    base = build_safe_slug_prefix(structured_label, fallback=fallback)
    for _ in range(32):
        suffix = "".join(secrets.choice(PUBLIC_REF_ALPHABET) for _ in range(6))
        candidate = f"{base}-{prefix_code}-{suffix}"
        if not model_cls.objects.filter(public_ref=candidate).exists():
            return candidate
    # Extended fallback entropy if exhausted
    suffix = "".join(secrets.choice(PUBLIC_REF_ALPHABET) for _ in range(10))
    return f"{base}-{prefix_code}-{suffix}"


def ensure_session_key(request: HttpRequest) -> str:
    """Ensure the active Django request has a persistent session key."""
    if not request.session.session_key:
        request.session.save()
    return str(request.session.session_key)


def authorize_contract_access(
    request: HttpRequest,
    contract,
    *,
    bind_if_unowned: bool = True,
) -> None:
    """Enforce session ownership on a PurchaseContract (fail closed HTTP 403)."""
    session_key = ensure_session_key(request)
    if not contract.owner_session_key:
        if bind_if_unowned:
            contract.owner_session_key = session_key
            contract.save(update_fields=["owner_session_key"])
        return
    if contract.owner_session_key != session_key:
        raise PermissionDenied("This shopping session belongs to another browser or user.")


def redirect_canonical(
    request: HttpRequest,
    view_name: str,
    public_ref: str,
) -> HttpResponse:
    """Redirect legacy UUID requests cleanly to canonical public_ref route preserving query params."""
    url = reverse(view_name, kwargs={"public_ref": public_ref})
    qs = request.META.get("QUERY_STRING", "")
    if qs:
        url = f"{url}?{qs}"
    return redirect(url)


def resolve_contract_or_redirect(
    request: HttpRequest,
    *,
    public_ref: str | None = None,
    contract_id=None,
    canonical_view_name: str,
):
    """Fetch PurchaseContract by public_ref or UUID, enforce session access, and redirect UUID GETs."""
    from contracts.models import PurchaseContract

    if public_ref is not None:
        contract = get_object_or_404(PurchaseContract, public_ref=public_ref)
        authorize_contract_access(request, contract)
        return contract, None

    contract = get_object_or_404(PurchaseContract, id=contract_id)
    authorize_contract_access(request, contract)
    if request.method == "GET":
        return contract, redirect_canonical(request, canonical_view_name, contract.public_ref)
    return contract, None

