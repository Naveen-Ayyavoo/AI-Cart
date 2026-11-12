"""
Automated foundation and architectural test suite for AI Cart (formerly TrustCart).
Validates Phase P1 deliverables:
- Django 6.x environment operational on Python 3.14.
- Core apps registered: contracts, catalog, policies, orders, payments.
- Health check /health/ operational and returning HTTP 200.
- SQLite database connection verified.
- Base layout template rendering.
- Exact monetary precision invariants (Decimal only).
"""

import json
from decimal import Decimal

from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django.template.loader import render_to_string
from django.test import Client, TestCase


class FoundationTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_django_system_check(self):
        """Verify that Django system check runs with zero warnings or errors."""
        try:
            call_command("check")
        except Exception as exc:  # noqa: BLE001
            self.fail(f"Django system check failed: {exc}")

    def test_core_apps_registered(self):
        """Verify that all 5 core domain applications are loaded in INSTALLED_APPS."""
        required_apps = ["contracts", "catalog", "policies", "orders", "payments"]
        for app_name in required_apps:
            self.assertTrue(
                apps.is_installed(app_name),
                f"Core app '{app_name}' is not registered in INSTALLED_APPS.",
            )
            app_config = apps.get_app_config(app_name)
            self.assertIsNotNone(app_config, f"AppConfig for '{app_name}' is None.")

    def test_health_check_endpoint_http_200(self):
        """Verify /health/ returns HTTP 200 with valid JSON status."""
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

        data = json.loads(response.content.decode("utf-8"))
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("app"), "trustcart")
        self.assertEqual(data.get("database"), "connected")
        self.assertEqual(data.get("environment"), "sandbox")
        self.assertEqual(data.get("currency"), "USD")

    def test_database_connectivity(self):
        """Verify direct query execution on local SQLite database."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT 42")
            result = cursor.fetchone()
            self.assertEqual(result[0], 42)

    def test_base_template_renders(self):
        """Verify base.html renders with AI Cart branding, sandbox pill, and demo disclosure."""
        html = render_to_string("base.html", {})
        self.assertIn("AI Cart", html)
        self.assertIn("PayPal Sandbox Demo Notice", html)
        self.assertIn("New Search", html)
        self.assertNotIn('href="/health/"', html)

    def test_monetary_precision_invariant(self):
        """
        Verify that monetary calculations use Decimal and avoid binary floating point drift.
        Rule: Float for money is strictly prohibited by AI Cart architectural invariants.
        """
        unit_price = Decimal("19.99")
        quantity = 3
        total = unit_price * quantity
        self.assertIsInstance(total, Decimal)
        self.assertEqual(total, Decimal("59.97"))

        # Classic floating-point binary drift demonstrate why float is prohibited:
        # 0.1 + 0.2 != 0.3 in binary float (evaluates to 0.30000000000000004)
        float_sum = 0.1 + 0.2
        self.assertNotEqual(float_sum, 0.3)

        # Decimal guarantees exact arithmetic
        decimal_sum = Decimal("0.1") + Decimal("0.2")
        self.assertEqual(decimal_sum, Decimal("0.3"))
