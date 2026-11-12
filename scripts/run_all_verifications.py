"""Cross-platform integrated verification runner for AI Cart.

Runs all quality and verification gates sequentially with clean exit codes,
independent of operating system shell syntax differences (e.g. PowerShell vs bash).

Gates executed:
1. Django System Check (`manage.py check`)
2. Model Migration Consistency (`manage.py makemigrations --check`)
3. Full Django Automated Test Suite (`manage.py test`)
4. Ruff Linter & Code Quality (`ruff check .`)
5. Static Page Re-rendering (`scripts/render_all_pages.py`)
6. Master Browser Responsiveness Suite Rebuild (`scripts/build_master_browser_test.py`)
7. End-to-End Shopper Journey Verification (`scripts/verify_shopper_journey.py`)
"""

import os
import subprocess
import sys
import time


def run_gate(title: str, command: list[str]) -> tuple[bool, int, float, str]:
    """Execute a single verification gate and capture its outcome, returncode, duration, and error output."""
    print("\n================================================================================")
    print(f"RUNNING GATE: {title}")
    print(f"Command: {' '.join(command)}")
    print("================================================================================")

    start = time.time()
    res = subprocess.run(command, check=False, text=True, capture_output=True)
    duration = time.time() - start

    if res.stdout:
        print(res.stdout.strip())
    if res.stderr:
        print(res.stderr.strip(), file=sys.stderr)

    if res.returncode == 0:
        print(f"\n[PASS] {title} succeeded in {duration:.2f}s (exit code 0)")
        return True, 0, duration, ""
    else:
        err_msg = res.stderr.strip() if res.stderr else res.stdout.strip()
        print(f"\n[FAIL] {title} failed with exit code {res.returncode}", file=sys.stderr)
        return False, res.returncode, duration, err_msg


def run_pipeline(gates: list[tuple[str, list[str]]], stop_on_failure: bool = False) -> int:
    """Execute all verification gates, collecting results and returning exit code 0 iff all succeed."""
    print("AI Cart Integrated Verification Pipeline Starting...")
    results = []
    failed = []

    for title, cmd in gates:
        success, code, duration, err = run_gate(title, cmd)
        results.append((title, success, code, duration))
        if not success:
            failed.append((title, code, err))
            if stop_on_failure:
                print(f"\nPipeline halted on failure in: {title}", file=sys.stderr)
                break

    print("\n" + "=" * 80)
    print("INTEGRATED VERIFICATION PIPELINE SUMMARY")
    print("=" * 80)
    for title, success, code, duration in results:
        status_label = "[PASS]" if success else "[FAIL]"
        print(f"  {status_label:<8} {title:<45} (Exit Code: {code}, {duration:.2f}s)")

    if failed:
        print("\n" + "-" * 80)
        print(f"FAILURES ENCOUNTERED: {len(failed)} of {len(gates)} gates failed")
        for title, code, err in failed:
            print(f"  • {title}: Exited with code {code}")
        print("=" * 80)
        return 1

    print("\n" + "=" * 80)
    print(f"ALL {len(gates)} QUALITY GATES PASSED CLEANLY (Exit Code 0)")
    print("Verification pipeline completed with zero errors.")
    print("=" * 80)
    return 0


def main():
    python_exe = sys.executable
    venv_dir = os.path.dirname(python_exe)
    ruff_exe = os.path.join(venv_dir, "ruff.exe") if os.name == "nt" else os.path.join(venv_dir, "ruff")

    gates = [
        ("Django System Check", [python_exe, "manage.py", "check"]),
        ("Model Migration Consistency", [python_exe, "manage.py", "makemigrations", "--check"]),
        ("Full Django Test Suite", [python_exe, "manage.py", "test"]),
        ("Ruff Linter", [ruff_exe, "check", "."]),
        ("Static Page Re-rendering", [python_exe, "scripts/render_all_pages.py"]),
        ("Master Browser Test Rebuild", [python_exe, "scripts/build_master_browser_test.py"]),
        ("10-Step Shopper Journey Verification", [python_exe, "scripts/verify_shopper_journey.py"]),
    ]

    exit_code = run_pipeline(gates, stop_on_failure=False)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
