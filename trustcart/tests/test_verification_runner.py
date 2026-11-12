"""Negative and positive unit tests for the integrated verification runner.

Verifies:
- Captures child process return codes accurately.
- Reports actual failed gate and its output.
- Continues collecting gate results across independent steps.
- Exits non-zero (1) if any required gate fails.
- Exits zero (0) if and only if all gates succeed.
- Does not falsely report success on failures.
"""

import sys
from io import StringIO
from unittest.mock import patch

from django.test import SimpleTestCase

from scripts.run_all_verifications import run_gate, run_pipeline


class VerificationRunnerTests(SimpleTestCase):
    """Test suite for scripts/run_all_verifications.py failure handling."""

    def test_run_gate_success(self):
        """A command returning exit code 0 is recorded as a PASS."""
        cmd = [sys.executable, "-c", "import sys; sys.exit(0)"]
        success, code, duration, err = run_gate("Test Step Success", cmd)
        self.assertTrue(success)
        self.assertEqual(code, 0)
        self.assertGreaterEqual(duration, 0.0)
        self.assertEqual(err, "")

    def test_run_gate_captures_non_zero_exit_code_and_stderr(self):
        """A command returning non-zero is captured with its exact exit code and stderr."""
        cmd = [
            sys.executable,
            "-c",
            "import sys; sys.stderr.write('Intentional failure diagnostics\\n'); sys.exit(42)",
        ]
        success, code, _duration, err = run_gate("Controlled Non-Zero Gate", cmd)
        self.assertFalse(success)
        self.assertEqual(code, 42)
        self.assertIn("Intentional failure diagnostics", err)

    def test_pipeline_succeeds_when_all_gates_exit_zero(self):
        """run_pipeline returns exit code 0 when all child processes exit with code 0."""
        gates = [
            ("Passing Step A", [sys.executable, "-c", "import sys; sys.exit(0)"]),
            ("Passing Step B", [sys.executable, "-c", "import sys; sys.exit(0)"]),
        ]
        with patch("sys.stdout", new=StringIO()), patch("sys.stderr", new=StringIO()):
            exit_code = run_pipeline(gates, stop_on_failure=False)
        self.assertEqual(exit_code, 0)

    def test_pipeline_fails_non_zero_on_controlled_child_failure(self):
        """Negative test: pipeline returns exit code 1 when any gate exits non-zero, never falsely claiming success."""
        gates = [
            ("Passing Step 1", [sys.executable, "-c", "import sys; sys.exit(0)"]),
            (
                "Deliberate Failure Step",
                [sys.executable, "-c", "import sys; sys.stderr.write('Gate crashed\\n'); sys.exit(7)"],
            ),
            ("Continuing Step 3", [sys.executable, "-c", "import sys; sys.exit(0)"]),
        ]
        with patch("sys.stdout", new=StringIO()) as mock_out, patch("sys.stderr", new=StringIO()):
            exit_code = run_pipeline(gates, stop_on_failure=False)
            output = mock_out.getvalue()

        # Invariant: Must return non-zero exit code
        self.assertEqual(exit_code, 1)

        # Invariant: Must report the specific failed gate and exit code
        self.assertIn("Deliberate Failure Step", output)
        self.assertIn("Exit Code: 7", output)
        self.assertIn("FAILURES ENCOUNTERED: 1 of 3 gates failed", output)
        self.assertNotIn("ALL 3 QUALITY GATES PASSED CLEANLY", output)
