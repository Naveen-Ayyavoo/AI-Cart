"""PayPal Orders v2 and Webhooks Client for AI Cart (formerly TrustCart) Phase P6.

Strict Sandbox Boundary:
- Strictly restricted to https://api-m.sandbox.paypal.com.
- Live endpoints or credentials strictly rejected (fail closed).
- Server-side OAuth 2.0 token caching and automatic refresh.
- Idempotency via PayPal-Request-Id header on all mutating calls.
- Webhook signature verification via PayPal's public certificate verification API.
- Zero-Spend Policy: 100% standard library (urllib.request), zero paid SDKs.
"""

import base64
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

SANDBOX_BASE_URL = "https://api-m.sandbox.paypal.com"


class PayPalError(Exception):
    """Base exception for PayPal client errors."""


class PayPalConfigurationError(PayPalError):
    """Raised when PayPal configuration violates sandbox boundaries or safety rules."""


class PayPalAuthError(PayPalError):
    """Raised when OAuth token retrieval fails."""


class PayPalAPIError(PayPalError):
    """Raised when PayPal API returns an HTTP or business error response."""

    def __init__(self, message: str, status_code: int | None = None, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


class PayPalTimeoutError(PayPalError):
    """Raised when a PayPal API request times out; enters PENDING_RECONCILIATION."""


class PayPalClient:
    """Production-grade PayPal Orders v2 and Webhooks API client for Sandbox."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
        webhook_id: str | None = None,
        timeout_seconds: int = 15,
    ):
        self.client_id = (client_id if client_id is not None else getattr(settings, "PAYPAL_CLIENT_ID", "")).strip('"').strip("'")
        self.client_secret = (client_secret if client_secret is not None else getattr(settings, "PAYPAL_CLIENT_SECRET", "")).strip('"').strip("'")
        self.base_url = (
            base_url if base_url is not None else getattr(settings, "PAYPAL_BASE_URL", SANDBOX_BASE_URL)
        ).rstrip("/")
        self.webhook_id = (webhook_id if webhook_id is not None else getattr(settings, "PAYPAL_WEBHOOK_ID", "")).strip('"').strip("'")
        self.timeout_seconds = timeout_seconds

        # Enforce strict Sandbox boundary (ADR-0002, ADR-0004)
        if not self.base_url.startswith("https://api-m.sandbox.paypal.com"):
            raise PayPalConfigurationError(
                f"SECURITY VIOLATION: Live or untrusted PayPal endpoint rejected: '{self.base_url}'. "
                f"Only Sandbox ('{SANDBOX_BASE_URL}') is permitted."
            )

        # In-memory OAuth token cache
        self._cached_token: str | None = None
        self._token_expires_at: float = 0.0

    def _get_access_token(self, force_refresh: bool = False) -> str:
        """Retrieve and cache a server-side OAuth 2.0 Bearer access token."""
        now = time.time()
        # Use cached token if valid with 60-second safety buffer
        if not force_refresh and self._cached_token and now < (self._token_expires_at - 60):
            return self._cached_token

        if not self.client_id or not self.client_secret:
            raise PayPalConfigurationError("Missing PayPal client_id or client_secret.")

        token_url = f"{self.base_url}/v1/oauth2/token"
        credentials = f"{self.client_id}:{self.client_secret}".encode()
        basic_auth = base64.b64encode(credentials).decode("ascii")

        headers = {
            "Authorization": f"Basic {basic_auth}",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        body = b"grant_type=client_credentials"

        req = urllib.request.Request(token_url, data=body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self._cached_token = data.get("access_token")
                expires_in = int(data.get("expires_in", 3600))
                self._token_expires_at = now + expires_in
                return self._cached_token
        except urllib.error.HTTPError as e:
            raw_err = e.read().decode("utf-8", errors="replace")
            logger.error("PayPal OAuth failure (HTTP %d): %s", e.code, raw_err)
            raise PayPalAuthError(f"OAuth failed (HTTP {e.code}): {raw_err}") from e
        except urllib.error.URLError as e:
            logger.error("PayPal OAuth network error: %s", e)
            raise PayPalTimeoutError(f"Network error connecting to PayPal OAuth: {e}") from e

    def _execute_request(
        self,
        endpoint: str,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute an authenticated JSON request against PayPal Sandbox."""
        token = self._get_access_token()
        url = f"{self.base_url}{endpoint}"

        req_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if headers:
            req_headers.update(headers)

        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body_bytes = resp.read()
                if not body_bytes:
                    return {}
                return json.loads(body_bytes.decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw_err = e.read().decode("utf-8", errors="replace")
            err_json: dict[str, Any] = {}
            try:
                err_json = json.loads(raw_err)
            except json.JSONDecodeError:
                err_json = {}
            msg = err_json.get("message") or err_json.get("error_description") or raw_err
            logger.error("PayPal API Error [%s %s] HTTP %d: %s", method, endpoint, e.code, raw_err)
            raise PayPalAPIError(f"PayPal API Error (HTTP {e.code}): {msg}", status_code=e.code, details=err_json) from e
        except (TimeoutError, urllib.error.URLError) as e:
            logger.warning("PayPal API Timeout/Network Error [%s %s]: %s", method, endpoint, e)
            raise PayPalTimeoutError(f"Timeout/Network error contacting PayPal on {endpoint}: {e}") from e

    def create_order(
        self,
        reference_id: str,
        custom_id: str,
        title: str,
        sku: str,
        quantity: int,
        unit_price: Decimal,
        base_amount: Decimal,
        shipping_amount: Decimal,
        tax_amount: Decimal,
        total_amount: Decimal,
        currency: str,
        payee_email: str,
        return_url: str,
        cancel_url: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Create a PayPal Orders v2 Order with intent CAPTURE.

        Invariants:
        - Sends unique PayPal-Request-Id idempotency key.
        - Specifies exact amount breakdown using Decimal string formatting.
        - Binds payee to controlled demo merchant account.
        - Sets experience_context to return_url and cancel_url.
        """
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": reference_id,
                    "description": f"AI Cart - {title[:100]}",
                    "custom_id": custom_id,
                    "amount": {
                        "currency_code": currency,
                        "value": f"{total_amount:.2f}",
                        "breakdown": {
                            "item_total": {"currency_code": currency, "value": f"{base_amount:.2f}"},
                            "shipping": {"currency_code": currency, "value": f"{shipping_amount:.2f}"},
                            "tax_total": {"currency_code": currency, "value": f"{tax_amount:.2f}"},
                        },
                    },
                    "items": [
                        {
                            "name": title[:127],
                            "unit_amount": {"currency_code": currency, "value": f"{unit_price:.2f}"},
                            "quantity": str(quantity),
                            "sku": sku[:127] or "DEFAULT",
                            "category": "PHYSICAL_GOODS",
                        }
                    ],
                    "payee": (
                        {"email_address": payee_email}
                        if "@" in payee_email
                        else {"merchant_id": payee_email}
                    ),
                }
            ],
            "payment_source": {
                "paypal": {
                    "experience_context": {
                        "brand_name": "AI Cart Demo Store",
                        "locale": "en-US",
                        "landing_page": "LOGIN",
                        "user_action": "PAY_NOW",
                        "return_url": return_url,
                        "cancel_url": cancel_url,
                    }
                }
            },
        }

        headers = {
            "PayPal-Request-Id": idempotency_key,
        }

        response = self._execute_request(
            endpoint="/v2/checkout/orders",
            method="POST",
            payload=payload,
            headers=headers,
        )
        return response

    def get_order(self, order_id: str) -> dict[str, Any]:
        """Authoritative server-side query to retrieve live order details from PayPal."""
        return self._execute_request(
            endpoint=f"/v2/checkout/orders/{urllib.parse.quote(order_id)}",
            method="GET",
        )

    def capture_order(self, order_id: str, idempotency_key: str) -> dict[str, Any]:
        """Execute server-side payment capture for an approved PayPal order.

        Invariants:
        - Must be called solely server-side.
        - Uses distinct capture idempotency key.
        """
        headers = {
            "PayPal-Request-Id": idempotency_key,
        }
        return self._execute_request(
            endpoint=f"/v2/checkout/orders/{urllib.parse.quote(order_id)}/capture",
            method="POST",
            payload={},
            headers=headers,
        )

    def verify_webhook_signature(
        self,
        transmission_id: str,
        transmission_time: str,
        cert_url: str,
        auth_algo: str,
        transmission_sig: str,
        webhook_id: str,
        raw_event_body: dict[str, Any] | str,
    ) -> bool:
        """Verify an incoming webhook notification cryptographically against PayPal's public certs.

        Invariants:
        - cert_url domain MUST be *.paypal.com to prevent SSRF.
        - Calls official POST /v1/notifications/verify-webhook-signature.
        """
        # SSRF Defense: Validate cert_url hostname ends with .paypal.com
        parsed_cert = urllib.parse.urlparse(cert_url)
        if not (parsed_cert.netloc.endswith(".paypal.com") and parsed_cert.scheme == "https"):
            logger.warning("Rejected malicious webhook cert_url: %s", cert_url)
            return False

        if isinstance(raw_event_body, str):
            try:
                event_obj = json.loads(raw_event_body)
            except json.JSONDecodeError:
                logger.warning("Malformed JSON in webhook event body")
                return False
        else:
            event_obj = raw_event_body

        verify_payload = {
            "auth_algo": auth_algo,
            "cert_url": cert_url,
            "transmission_id": transmission_id,
            "transmission_sig": transmission_sig,
            "transmission_time": transmission_time,
            "webhook_id": webhook_id or self.webhook_id,
            "webhook_event": event_obj,
        }

        try:
            resp = self._execute_request(
                endpoint="/v1/notifications/verify-webhook-signature",
                method="POST",
                payload=verify_payload,
            )
            status = resp.get("verification_status", "").upper()
            logger.info("PayPal verify-webhook-signature response: status=%s", status)
            return status == "SUCCESS"
        except PayPalError as e:
            logger.error("Webhook signature verification failed with error: %s", e)
            return False
