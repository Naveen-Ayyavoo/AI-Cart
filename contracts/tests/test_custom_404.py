"""
Comprehensive verification of AI Cart custom 404 Not Found error handling.
Validates:
1. Unknown URLs return HTTP 404.
2. Custom 404 template (404.html) is rendered.
3. Response contains expected user-facing copy and title.
4. Response includes working navigation (Start New Shopping Search, Go Back).
5. Page does not expose internal error information, stack traces, IDs, or secrets.
6. Existing valid application routes remain unaffected.
7. The actual 404 handler works with DEBUG=False.
8. Unknown public-reference URLs and invalid route parameters fail closed safely with 404.
"""

from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from trustcart.views import custom_404_view


class Custom404DirectViewTests(SimpleTestCase):
    """Direct unit tests for custom_404_view callable."""

    def test_custom_404_view_returns_404_status_and_content(self):
        client = Client()
        response = custom_404_view(client.get("/nonexistent-direct/").wsgi_request)
        self.assertEqual(response.status_code, 404)
        content = response.content.decode("utf-8")
        self.assertIn("Page not found", content)
        self.assertIn(
            "We couldn't find the page you're looking for. It may have moved, expired or the address may be incorrect.",
            content,
        )
        self.assertIn("Start New Shopping Search", content)
        self.assertIn("Go Back", content)
        self.assertIn("404", content)
        self.assertIn("AI Cart", content)


@override_settings(DEBUG=False)
class Custom404DebugFalseTests(TestCase):
    """End-to-end HTTP tests with DEBUG=False verifying handler404 dispatch."""

    def setUp(self):
        self.client = Client()

    def test_unknown_url_returns_404_and_renders_custom_template(self):
        response = self.client.get("/nonexistent-page-xyz-12345/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        content = response.content.decode("utf-8")

        # Heading and copy
        self.assertIn("Page not found", content)
        self.assertIn(
            "We couldn't find the page you're looking for. It may have moved, expired or the address may be incorrect.",
            content,
        )
        self.assertIn("<title>Page Not Found — AI Cart</title>", content)

        # Actions
        self.assertIn("Start New Shopping Search", content)
        self.assertIn('href="/"', content)
        self.assertIn("Go Back", content)
        self.assertIn("window.history.back()", content)

        # 404 badge indicator
        self.assertIn("404", content)

        # Branding
        self.assertIn("AI Cart", content)
        self.assertIn("Intelligence in Every Click", content)
        self.assertIn("Sandbox Demo Notice", content)

    def test_page_does_not_expose_internal_error_or_debug_info(self):
        response = self.client.get("/totally/broken/path/../secret.env")
        content = response.content.decode("utf-8")

        # No stack traces or Python exceptions
        self.assertNotIn("Traceback (most recent call last)", content)
        self.assertNotIn("django.core.exceptions", content)
        self.assertNotIn("DoesNotExist", content)
        self.assertNotIn("ValueError", content)
        self.assertNotIn("KeyError", content)

        # No file system paths or internal code references
        self.assertNotIn("D:\\TrustCart", content)
        self.assertNotIn("C:\\Users", content)
        self.assertNotIn(".venv", content)
        self.assertNotIn("views.py", content)
        self.assertNotIn("urls.py", content)

        # No sensitive secrets
        self.assertNotIn("PAYPAL_", content)
        self.assertNotIn("CHANNEL3_", content)
        self.assertNotIn("GEMINI_", content)
        self.assertNotIn("SECRET_KEY", content)

    def test_unknown_public_references_fail_closed_with_404(self):
        unknown_urls = [
            "/contracts/unknown-item-PC-000000/review/",
            "/contracts/unknown-item-PC-000000/confirm/",
            "/contracts/unknown-item-PC-000000/discovery/",
            "/contracts/unknown-item-PC-000000/evaluation/",
            "/orders/proposals/unknown-item-PP-000000/",
            "/orders/approvals/unknown-item-PA-000000/",
            "/payments/orders/PP-UNKNOWN-000000/",
        ]
        for url in unknown_urls:
            response = self.client.get(url)
            self.assertEqual(
                response.status_code,
                404,
                f"Expected 404 for unknown reference URL: {url}, got {response.status_code}",
            )
            content = response.content.decode("utf-8")
            self.assertIn("Page not found", content)
            self.assertNotIn("Traceback", content)
            self.assertNotIn("DoesNotExist", content)

    def test_invalid_parameters_and_path_traversal_fail_closed_safely(self):
        malformed_urls = [
            "/contracts/../../../etc/passwd/review/",
            "/contracts/<script>alert(1)</script>/review/",
            "/orders/proposals/'%20OR%201=1--/",
        ]
        for url in malformed_urls:
            response = self.client.get(url)
            self.assertIn(
                response.status_code,
                [400, 404],
                f"Expected 400 or 404 for malformed URL {url}, got {response.status_code}",
            )
            content = response.content.decode("utf-8")
            self.assertNotIn("Traceback", content)
            self.assertNotIn("OperationalError", content)

        # Query param injection test returns 200 safely without SQL errors
        safe_resp = self.client.get("/payments/history/?status=INVALID_STATUS_INJECTION%27")
        self.assertEqual(safe_resp.status_code, 200)
        self.assertNotIn("Traceback", safe_resp.content.decode("utf-8"))

    def test_existing_valid_application_routes_remain_unaffected(self):
        # Home page returns 200
        home_resp = self.client.get(reverse("home"))
        self.assertEqual(home_resp.status_code, 200)
        self.assertIn("AI Cart — Intelligence in Every Click", home_resp.content.decode("utf-8"))

        # Health endpoint returns 200
        health_resp = self.client.get(reverse("health_check"))
        self.assertEqual(health_resp.status_code, 200)
        self.assertEqual(health_resp.json().get("status"), "ok")

        # Payment history returns 200
        history_resp = self.client.get(reverse("payments:history"))
        self.assertEqual(history_resp.status_code, 200)
