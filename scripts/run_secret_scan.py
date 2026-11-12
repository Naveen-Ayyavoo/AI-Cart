"""AI Cart Pre-Commit Secret and Credential Scanner.

Scans the repository candidate files for:
1. Dynamic exact substring matches against active sensitive environment keys in .env.
2. Standard credential regex signatures (Google API keys, Private Key headers, AWS, GitHub, Slack tokens, URIs with passwords).

Safety & Security Rules:
- Never prints actual secret or credential values to console or logs.
- Exits with 0 when 100% clean, exits with 1 if any potential secret leak is detected.
- Explicitly documents false-positive handling and known scanner limitations.
"""

import os
import re
import sys

PATTERNS = {
    "Google API Key": re.compile(r"AIza[0-9A-Za-z-_]{35}"),
    "Private Key": re.compile(r"-----BEGIN (?:RSA|EC|DSA|OPENSSH|PGP|PRIVATE) KEY"),
    "AWS Access Key": re.compile(r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"),
    "GitHub Token": re.compile(r"gh[pousr]_[0-9a-zA-Z]{36}"),
    "Slack Token": re.compile(r"xox[baprs]-[0-9a-zA-Z]{10,48}"),
    "URI with Password": re.compile(r"(?:postgres|mysql|mongodb|redis)://[^:\s]+:[^@\s]+@[^/\s]+"),
}

SENSITIVE_ENV_KEYS = {
    "DJANGO_SECRET_KEY",
    "GEMINI_API_KEY",
    "CHANNEL3_API_KEY",
    "PAYPAL_CLIENT_ID",
    "PAYPAL_CLIENT_SECRET",
    "PAYPAL_WEBHOOK_ID",
}

SKIP_DIRS = {
    ".git",
    ".venv",
    ".ruff_cache",
    "__pycache__",
    "scratch",
    "graphify-out",
    ".graphify-runtime",
}

SKIP_FILES = {
    ".env",
    "db.sqlite3",
    "db.sqlite3-journal",
}

SKIP_EXTENSIONS = (
    ".pyc",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
)


def load_env_secrets(env_path: str = ".env") -> dict[str, str]:
    secrets = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip("\"' ")
                    if k in SENSITIVE_ENV_KEYS and len(v) > 6:
                        secrets[k] = v
    return secrets


def run_scan() -> int:
    env_secrets = load_env_secrets()
    print("=" * 70)
    print("AI CART PRE-COMMIT SECRET AND PRIVACY SCANNER")
    print("=" * 70)
    print(f"Loaded {len(env_secrets)} sensitive environment keys for exact matching:")
    for k in sorted(env_secrets):
        print(f"  - {k} (length: {len(env_secrets[k])} chars, [REDACTED])")

    scanned_count = 0
    skipped_dir_count = 0
    skipped_file_count = 0
    findings = []

    for root, dirs, files in os.walk("."):
        # Filter directories in-place
        orig_dirs = list(dirs)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        skipped_dir_count += len(orig_dirs) - len(dirs)

        for file in files:
            if file in SKIP_FILES or file.endswith(SKIP_EXTENSIONS):
                skipped_file_count += 1
                continue

            filepath = os.path.join(root, file).replace("\\", "/")
            scanned_count += 1

            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # 1. Check regex patterns
                for name, pat in PATTERNS.items():
                    m = pat.search(content)
                    if m:
                        snippet = m.group(0)
                        # False positive handling: allow doc placeholders and test strings
                        if "AIza" in snippet and ("AIzaSyExample" in snippet or "AIzaSyFake" in snippet or "your_" in snippet):
                            continue
                        findings.append((filepath, name, "[REDACTED PATTERN MATCH]"))

                # 2. Check exact env secret strings
                for k, v in env_secrets.items():
                    if v in content:
                        findings.append((filepath, f"Exact .env key match: {k}", "[REDACTED VALUE MATCH]"))

            except (OSError, UnicodeDecodeError) as e:
                print(f"  [WARN] Failed to read {filepath}: {e}")

    print("\nScan Scope & Results:")
    print(f"  Files scanned: {scanned_count}")
    print(f"  Directories skipped (ignored/caches/runtime): {skipped_dir_count}")
    print(f"  Files skipped (binary/sqlite/.env): {skipped_file_count}")
    print(f"  Potential secret leaks detected: {len(findings)}")

    if findings:
        print("\n[ALERT] POTENTIAL SECRET LEAKS DETECTED:")
        for path, cat, _ in findings:
            print(f"  - {path}: {cat}")
        print("\nSCAN RESULT: FAIL")
        return 1
    else:
        print("\n[OK] 100% CLEAN: Zero secrets, private keys, or API tokens detected.")
        print("SCAN RESULT: PASS")
        return 0


if __name__ == "__main__":
    sys.exit(run_scan())
