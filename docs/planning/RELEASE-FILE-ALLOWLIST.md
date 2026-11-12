# TrustCart — Release Staging File Allowlist (v1.0.0-rc1)

**Audit Date:** 2026-11-12T18:52:00+05:30  
**Target Release:** `v1.0.0-rc1`  
**Repository Working Tree:** `D:\TrustCart`  
**Baseline Commit:** `76bc7ce chore: initialize TrustCart engineering workspace`  

---

## 1. Executive Summary

This document establishes the precise, file-by-file allowlist for staging TrustCart's release candidate (`v1.0.0-rc1`) for public GitHub release and hackathon submission.

In strict compliance with project invariants and release boundaries:
- **Zero Secrets**: All private credentials, API keys, tokens, and local databases are strictly excluded.
- **Selective Staging**: `git add .` is explicitly avoided to ensure that only approved, production-grade application files and verification evidence are staged.
- **Reproducibility**: All domain applications, migrations, tests, templates, dependencies, and setup documentation are included to guarantee complete judge reproducibility out of the box.

---

## 2. Section A: Include in Release (Approved Allowlist)

**Total Count: 170 approved files** (8 modified tracked files + 162 untracked release files; plus 1 existing unchanged tracked baseline file `.editorconfig` = 171 files total)

These files represent the complete, verified, working application, legal licensing, dependency definitions, test suites, and hackathon verification reports:

### A. Root Governance, Configuration & Dependencies (11 files)
1. `AGENTS.md` (Operating guide and architecture invariants for AI Cart)
2. `LICENSE` (Finalized standard root MIT License with `Copyright (c) 2026 Naveen`)
3. `README.md` (Main documentation, architecture diagrams, 8-scene video walkthrough, quickstart guide)
4. `TASK_GATES.md` (Phase-gated engineering roadmap with signed-off verifications for P0–P9, G1, and G2)
5. `THIRD-PARTY-LICENSES.md` (Attribution for upstream open-source packages)
6. `.env.example` (Sanitized environment variable configuration template with safe placeholders)
7. `.gitignore` (Repository hygiene rules ignoring `.env`, databases, virtual environments, and caches)
8. `.graphifyignore` (Exclusion patterns for code-only AST knowledge graph extraction)
9. `manage.py` (Standard Django administrative and execution CLI)
10. `pyproject.toml` (Ruff linter rules and project configuration)
11. `requirements.txt` (Pinned dependency declarations for Python 3.14 virtual environment)

### B. Core Application Source Packages (108 files across 9 directories)

#### 1. `catalog/` — Channel3 Product Evidence Domain (19 files)
- `catalog/__init__.py`
- `catalog/admin.py`
- `catalog/apps.py`
- `catalog/client.py` (Channel3 REST API client, live search, schema & image URL normalization)
- `catalog/fixtures.py` (Labeled offline fallback demo fixtures)
- `catalog/models.py` (Channel3CreditLedger, ProductEvidence, and ProductSearchCache models)
- `catalog/services.py` (Product search orchestration service)
- `catalog/urls.py` (Catalog routing)
- `catalog/views.py` (Product discovery and search views)
- `catalog/migrations/__init__.py`
- `catalog/migrations/0001_initial.py` (Credit ledger, product evidence, and cache tables)
- `catalog/migrations/0002_alter_productevidence_offers_and_more.py` (Offers/provenance field alignment)
- `catalog/tests/__init__.py`
- `catalog/tests/test_client_and_search.py` (API mock tests, timeout tests, failure tests)
- `catalog/tests/test_discovery_images.py` (Image normalization, lazy card fallback, eligibility ordering tests)
- `catalog/tests/test_models_and_cache.py` (Decimal precision, ledger & search cache tests)
- `catalog/tests/test_recommendations.py` (Deterministic recommendation logic, Decimal subtotal, and trade-off tests)
- `catalog/templates/catalog/_product_card.html` (Shared candidate card partial with image fallback and eligibility styling)
- `catalog/templates/catalog/product_list.html` (Product candidate discovery UI & budget revision prompt)

#### 2. `contracts/` — Purchase Contract & Gemini Intake Domain (30 files)
- `contracts/__init__.py`
- `contracts/access.py` (Session-scoped contract owner access control)
- `contracts/admin.py`
- `contracts/apps.py`
- `contracts/clarifications.py` (Category-specific optional clarifications and edit-criteria metadata engine)
- `contracts/fixtures.py` (Labeled local demo contract extraction fixtures)
- `contracts/forms.py` (Shopper intake and post-confirmation budget revision forms)
- `contracts/gemini.py` (Gemini Free Tier client with strict Pydantic parsing and `extra="forbid"`)
- `contracts/interpreter.py` (Deterministic natural-language constraint interpreter)
- `contracts/models.py` (PurchaseContract domain model, versioning, `create_revision` approval/proposal invalidation)
- `contracts/schemas.py` (Structured PurchaseContract Pydantic schema definitions)
- `contracts/urls.py` (Contract intake, clarify, and revise-budget routing)
- `contracts/views.py` (Intake, clarification, review, budget revision, and confirmed receipt views)
- `contracts/migrations/__init__.py`
- `contracts/migrations/0001_initial.py` (PurchaseContract table schema)
- `contracts/migrations/0002_purchasecontract_public_ref_owner_session_key.py` (Owner session tracking migration)
- `contracts/migrations/0003_alter_purchasecontract_source.py` (Source provenance migration)
- `contracts/templates/contracts/buy_anyway.html` (Buy anyway policy confirmation UI)
- `contracts/templates/contracts/confirmed.html` (Locked contract confirmation UI)
- `contracts/templates/contracts/review.html` (Unified structured contract review, optional details & editing UI)
- `contracts/tests/__init__.py`
- `contracts/tests/test_adversarial_security.py` (Prompt injection, schema escape, and DOS tests)
- `contracts/tests/test_custom_404.py` (Custom 404 handler, branding, information leak prevention tests)
- `contracts/tests/test_domain_and_gemini.py` (Gemini parsing, schema validation, quota fallback tests)
- `contracts/tests/test_gap_closure_e2e.py` (End-to-end contract gap closure verification)
- `contracts/tests/test_public_urls_and_layout.py` (Public reference routing & layout structure tests)
- `contracts/tests/test_ui_content_hygiene.py` (Brand & UI terminology hygiene tests)
- `contracts/tests/test_ux_corrections_and_integrity.py` (UI integrity & request-to-contract verification)
- `contracts/tests/test_ux_defects.py` (Regression suite covering all 7 UX defects & budget revision approval invalidation)
- `contracts/tests/test_views.py` (Multi-step contract lifecycle view tests)

#### 3. `orders/` — Cryptographic Approval & Fingerprint Domain (18 files)
- `orders/__init__.py`
- `orders/admin.py`
- `orders/apps.py`
- `orders/fingerprint.py` (Canonical 15-parameter SHA-256 cart fingerprinting)
- `orders/models.py` (PurchaseProposal and single-use PurchaseApproval models)
- `orders/services.py` (Proposal assembly and atomic single-use approval token lifecycle)
- `orders/urls.py` (Proposal and approval routing)
- `orders/views.py` (Proposal review and approval confirmation views)
- `orders/migrations/__init__.py`
- `orders/migrations/0001_initial.py` (Proposal and approval table schemas)
- `orders/migrations/0002_alter_purchaseproposal_payee_id.py` (Demo merchant ID schema alignment)
- `orders/migrations/0003_purchaseproposal_approval_public_ref.py` (Approval public ref alignment)
- `orders/templates/orders/approval_detail.html` (Single-use approval receipt UI)
- `orders/templates/orders/proposal_detail.html` (Purchase proposal presentation UI)
- `orders/tests/__init__.py`
- `orders/tests/test_concurrency.py` (Approval token atomic consumption and concurrency tests)
- `orders/tests/test_fingerprint_and_models.py` (Model methods and fingerprint integration tests)
- `orders/tests/test_services_and_views.py` (Proposal service & view regression tests)

#### 4. `payments/` — PayPal Orders v2 & Webhook Domain (21 files)
- `payments/__init__.py`
- `payments/admin.py`
- `payments/apps.py`
- `payments/client.py` (PayPal Orders v2 REST client restricted to Sandbox endpoints)
- `payments/models.py` (PaymentOrder, PaymentCaptureRecord, WebhookEventRecord)
- `payments/services.py` (Initiation, pre-capture revalidation, server capture, webhook verification)
- `payments/urls.py` (Checkout, callback, and webhook listener routing)
- `payments/views.py` (Checkout return callback, order detail, and webhook listener views)
- `payments/migrations/__init__.py`
- `payments/migrations/0001_initial.py` (Payment order, capture, and webhook tables)
- `payments/migrations/0002_alter_paymentorder_status.py` (PaymentOrder status enumeration migration)
- `payments/templates/payments/cancelled.html` (Buyer cancelled checkout view)
- `payments/templates/payments/failed.html` (Revalidation failure / safety rejection view)
- `payments/templates/payments/history.html` (Payment order history dashboard view)
- `payments/templates/payments/pending.html` (Pending reconciliation status view)
- `payments/templates/payments/receipt.html` (Completed purchase receipt UI)
- `payments/tests/__init__.py`
- `payments/tests/test_adversarial_and_e2e.py` (Adversarial price fluctuation, payee hijack, E2E journey)
- `payments/tests/test_client_and_models.py` (Client error handling and model status lifecycle tests)
- `payments/tests/test_services_and_views.py` (Payment service and checkout views tests)
- `payments/tests/test_webhooks.py` (RSA public cert signature verification, deduplication tests)

#### 5. `policies/` — Deterministic Policy Engine Domain (15 files)
- `policies/__init__.py`
- `policies/admin.py`
- `policies/apps.py`
- `policies/engine.py` (100% deterministic local Python rule engine with exact Decimal arithmetic)
- `policies/models.py` (PolicyEvaluationReport model)
- `policies/services.py` (Evaluation service orchestrating candidate assessment)
- `policies/urls.py` (Evaluation dashboard routing)
- `policies/views.py` (Policy evaluation dashboard view)
- `policies/migrations/__init__.py`
- `policies/migrations/0001_initial.py` (PolicyEvaluationReport table schema)
- `policies/templates/policies/_eval_card.html` (Rule evaluation card partial)
- `policies/templates/policies/evaluation.html` (Rule-by-rule policy audit dashboard UI)
- `policies/tests/__init__.py`
- `policies/tests/test_engine.py` (Budget ceiling, stock, excluded terms, preference scoring tests)
- `policies/tests/test_services_and_views.py` (Policy evaluation service and view tests)

#### 6. `templates/` — Base Layout & User Flow Views (4 files)
- `templates/base.html` (Responsive base shell, contrast-compliant CSS tokens, shared `AICartUI` loading/reset logic, inline SVG mark)
- `templates/home.html` (Modernized shopper intake, sample scenario chips, `<search>` landmark)
- `templates/403.html` (Access denied security error page)
- `templates/404.html` (Branded custom 404 Not Found page with recovery search action)

#### 7. `static/img/` — Brand Vector Identity Assets (2 files)
- `static/img/ai-cart-mark.svg` (Original vector identity brand mark: geometric shopping cart with integrated AI spark)
- `static/img/ai-cart-favicon.svg` (Crisp 32x32 vector favicon for browser tab display)

#### 8. `trustcart/` — Root Project Configuration (9 files)
- `trustcart/__init__.py`
- `trustcart/asgi.py`
- `trustcart/settings.py` (Django settings, security middleware, Decimal constants, app registry)
- `trustcart/urls.py` (Root URL routing table)
- `trustcart/views.py` (Core system health check and custom 404 handler)
- `trustcart/wsgi.py`
- `trustcart/tests/__init__.py`
- `trustcart/tests/test_foundation.py` (Django system check, database, security middleware tests)
- `trustcart/tests/test_verification_runner.py` (Verification runner failure capture, summary reporting, non-zero return code tests)

#### 9. `scripts/` — Verification & Browser Testing Tooling (6 files)
- `scripts/build_master_browser_test.py` (Constructs standalone 84-point layout & responsiveness test suite)
- `scripts/render_all_pages.py` (Static test harness rendering all 12 user-facing templates)
- `scripts/run_all_verifications.py` (Cross-platform integrated runner executing all 7 quality gates)
- `scripts/run_secret_scan.py` (Pre-commit credential and private key verification scanner)
- `scripts/verify_frontend.py` (Responsive design and CSS breakpoint checker)
- `scripts/verify_shopper_journey.py` (10-step end-to-end programmatic shopper journey verification)

### C. Architecture, Decisions, Quality, Security & Planning Documentation (30 files across `docs/`)
1. Architecture (`3`):
   - `docs/architecture/DATA_FLOW.md`
   - `docs/architecture/SYSTEM_OVERVIEW.md`
   - `docs/architecture/TRUST_BOUNDARIES.md`
2. Decisions (`4`):
   - `docs/decisions/ADR-0001-TECHNOLOGY-STACK.md`
   - `docs/decisions/ADR-0002-PAYMENT-AND-APPROVAL-BOUNDARY.md`
   - `docs/decisions/ADR-0003-PRODUCT-DATA-AND-DEMO-MARKET.md`
   - `docs/decisions/ADR-0004-ZERO-SPEND-POLICY.md`
3. Security & Quality (`2`):
   - `docs/security/THREAT_MODEL.md`
   - `docs/quality/TEST_STRATEGY.md`
4. Design System (`1`):
   - `docs/design-system/ai-cart/MASTER.md`
5. Planning & Verification Reports (`20` in `docs/planning/`):
   - `docs/planning/CURRENT_STATUS.md`
   - `docs/planning/HANDOFF.md`
   - `docs/planning/IMPLEMENTATION_ROADMAP.md`
   - `docs/planning/P7-VERIFICATION.md`
   - `docs/planning/P8-HARDENING-REPORT.md`
   - `docs/planning/P9-RELEASE-CANDIDATE-REPORT.md`
   - `docs/planning/G1-COMPETITION-READINESS-ASSESSMENT.md`
   - `docs/planning/G2-SUBMISSION-AND-PRESENTATION-REPORT.md`
   - `docs/planning/FINAL-RELEASE-SECURITY-AUDIT.md`
   - `docs/planning/FRONTEND-REMODEL-REPORT.md`
   - `docs/planning/UI-UX-PRO-MAX-ASSESSMENT.md`
   - `docs/planning/AI-CART-REBRAND-REPORT.md`
   - `docs/planning/AI-CART-PRODUCT-DISCOVERY-UX-REPORT.md`
   - `docs/planning/RELEASE-FILE-ALLOWLIST.md`
   - `docs/planning/AI-CART-UX-DEFECT-RESOLUTION-REPORT.md`
   - `docs/planning/AI-CART-RULEBOOK-CONFORMANCE-ASSESSMENT.md`
   - `docs/planning/AI-CART-SHOPPING-FLOW-UX-CORRECTIONS.md`
   - `docs/planning/AI-CART-FINAL-READINESS-ASSESSMENT.md`
   - `docs/planning/PAYPAL-AI-HACKATHON-JUDGE-REVERSE-ENGINEERING-AND-COMPETITIVE-ASSESSMENT.md`
   - `docs/planning/AI-CART-REPOSITORY-CLEANUP-AND-REBRANDING-REPORT.md`

### D. Automated Lifecycle Tooling & Graphify Rules (5 files)
1. `.agents/gsd-core/LICENSE` (Preserved upstream MIT license for GSD Core tool bundle)
2. `.agents/hooks.json` (Native Antigravity lifecycle hooks configuration)
3. `.agents/rules/graphify.md` (Mandatory rules for knowledge graph consultation)
4. `.agents/scripts/graphify-auto.ps1` (PowerShell lifecycle hook script)
5. `.agents/workflows/graphify.md` (Graph extraction and query workflows)

---

## 3. Section B: Exclude from Release (Strict Exclusion List)

**Total Count: 11 Categories / Directories**

These files/directories must NEVER be staged or pushed to the public repository:

| Excluded Item | Reason for Exclusion | Status in Repository |
| :--- | :--- | :--- |
| **`.env`** | Contains live development/testing API keys, client secrets, and tokens. | **EXCLUDED** (Ignored by `.gitignore`) |
| **`db.sqlite3`** | Local binary SQLite database containing development transactions and test state. | **EXCLUDED** (Ignored by `.gitignore`) |
| **`.venv/`** | Local Python virtual environment binaries, site-packages, and wheel caches. | **EXCLUDED** (Ignored by `.gitignore`) |
| **`scratch/`** (in `D:\TrustCart\`) | 19 investigative scripts and logs (`audit_config.py`, `webhook_verify.log`, etc.). | **EXCLUDED** (Ignored by `.gitignore`) |
| **`.graphify-runtime/`** | Machine-specific lockfiles, source SHA-256 fingerprint caches, and diagnostic logs. | **EXCLUDED** (Ignored by `.gitignore`) |
| **`graphify-out/`** | Local AST graph JSON cache (`graph.json`). Rebuilt on-demand locally. | **EXCLUDED** (Ignored by `.gitignore`) |
| **`.ruff_cache/`** | Local linter binary cache. | **EXCLUDED** (Ignored by `.gitignore`) |
| **`**/__pycache__/` & `*.pyc` | Compiled Python bytecode files. | **EXCLUDED** (Ignored by `.gitignore`) |
| **`.env.local` / `.env.production`** | Any uncommitted local or production environment overrides. | **EXCLUDED** (Ignored by `.gitignore`) |
| **Conversation Scratch Scripts** | Local diagnostic scripts stored in IDE brain scratch. | **EXCLUDED** (Outside git tracking) |
| **`.agents/skills/ui-ux-pro-max/` & sub-skills** (`banner-design`, `brand`, `design`, `design-system`, `slides`, `ui-styling`) | Third-party design intelligence skill and bundled datasets evaluated locally; keep out of public release package. | **EXCLUDED** (Local design tool only) |

---

## 4. Section C: Requires Manual Review

**Total Count: 2 Items (1 Directory + 1 Script)**

### 1. `.planning/` Directory (47 markdown files)
- **Contents**:
  - Codebase analysis maps (`.planning/codebase/` — 7 files)
  - Onboarding summary (`.planning/onboarding/` — 1 file)
  - Phase plans, summaries, and contexts for P1–P6 (`.planning/phases/` — 34 files)
  - Core project tracking files (`PROJECT.md`, `ROADMAP.md`, `STATE.md`, `REQUIREMENTS.md`, `config.json` — 5 files)
- **Rationale for Manual Review**:
  - *Option 1: Include in Release (Recommended for Transparency)*: Demonstrates the thorough, autonomous, phase-gated execution methodology of the Google DeepMind Antigravity agent and GSD Core framework. Provides undeniable proof of engineering rigor to hackathon judges.
  - *Option 2: Exclude from Release (Clean Codebase)*: If the user prefers a public repository containing only standard application source code and formal documentation, `.planning/` can be added to `.gitignore` or omitted from the release commit.
- **Decision Required**: User choice before running final staging command.

### 2. `scripts/verify_frontend.py` (Local Frontend Verification Tool)
- **Contents**: Automated verification script validating all 12 user-facing templates, touch targets, and 7 responsive viewport breakpoints.
- **Rationale for Manual Review**:
  - *Option 1: Include in Release*: Provides a convenient standalone verification tool for judges or developers.
  - *Option 2: Exclude from Release*: Can remain a local verification artifact if the repository should contain only standard Django test suites.
- **Decision Required**: User choice before staging.

---

## 5. Security Scanner Inspection & Limitations Documentation

### Inspection of `comprehensive_security_audit.py`:
The read-only audit script `comprehensive_security_audit.py` executed during the security audit operates under the following technical parameters:

1. **Scan Patterns**:
   - **Exact Substring Matching**: Dynamically loads sensitive values from `.env` (`DJANGO_SECRET_KEY`, `GEMINI_API_KEY`, `CHANNEL3_API_KEY`, `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID`) and verifies that zero occurrences exist in any candidate release file.
   - **Regular Expression Signatures**:
     - Google API Key (`AIza[0-9A-Za-z-_]{35}`)
     - Private Key Header (`-----BEGIN (?:RSA|EC|DSA|OPENSSH|PGP|PRIVATE) KEY`)
     - AWS Access Key ID (`(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}`)
     - GitHub Personal Access Token (`gh[pousr]_[0-9a-zA-Z]{36}`)
     - Slack Token (`xox[baprs]-[0-9a-zA-Z]{10,48}`)
     - Generic Password in URI (`[a-zA-Z0-9+.-]+://[^:\s]+:[^@\s]+@[^/\s]+`)
     - Hardcoded Bearer Token (`(?i)\bbearer\s+['\"][a-zA-Z0-9_\-\.]{25,}['\"]`)
2. **Exclusions**:
   - Skips `.env`, `.git/`, `*.pyc`, `*.sqlite3`.
   - Explicitly allowlists 14 public, simulated PayPal Sandbox test identifiers (`PU7K3F65AAQ8U`, `sb-vwssg53834434@personal.example.com`, etc.) and safe template placeholders (`your_gemini_api_key_here`).
3. **Explicit Tool Limitations (Not Equivalent to Gitleaks)**:
   - *No Shannon Entropy Analysis*: Unlike Gitleaks, it does not calculate string randomness/entropy; it will not flag generic high-entropy strings that lack a recognized prefix or exact match.
   - *Limited Rule Library*: Targets 7 primary cloud/payment secret patterns, whereas Gitleaks maintains 150+ curated multi-vendor rule signatures.
   - *Working Tree Only*: Scans files currently on disk; it does not traverse Git commit history or reflog. (This is appropriate for TrustCart because the repository has only 1 initial baseline commit, but is a recognized limitation).
   - *Single-Line Scope*: Operates line-by-line; multi-line formatted keys without headers could evade regex detection.

---

## 6. Verification Against Release Requirements

1. **Root `LICENSE`**: Included (`D:\TrustCart\LICENSE` with `Copyright (c) 2026 Naveen`).
2. **README**: Included (`README.md` with architecture diagrams and 8-scene demo walkthrough).
3. **Application Source Code**: Included (All 5 domain apps: `catalog/`, `contracts/`, `orders/`, `payments/`, `policies/`, plus `trustcart/` and `templates/`).
4. **Database Migrations**: Included (All initial and alteration migrations across all apps; verified applied).
5. **Test Suites**: Included (All 196 automated unit, integration, recommendation semantics, UX/audit regression, runner failure, and adversarial security tests).
6. **Dependency Locking**: Included (`requirements.txt` with pinned versions).
7. **Accidental Exclusions**: **Verified Clear**. Tested all 95 application files via `git check-ignore`; zero required application files are ignored.

---

## 7. Exact Staging Commands for User Execution

To stage **only** the approved release candidate files (excluding all sensitive, temporary, and binary files) without using `git add .`:

### Recommended Option: Include Approved Release Files + `.planning/`

```powershell
# 1. Stage Root Governance, Setup, and Build Files
git add AGENTS.md LICENSE README.md TASK_GATES.md THIRD-PARTY-LICENSES.md .env.example .gitignore .graphifyignore manage.py pyproject.toml requirements.txt

# 2. Stage Core Domain Application Packages
git add catalog/ contracts/ orders/ payments/ policies/ static/ templates/ trustcart/ scripts/

# 3. Stage Documentation & Phase Verification Reports
git add docs/

# 4. Stage Antigravity Automation & Graphify Rules
git add .agents/gsd-core/LICENSE .agents/hooks.json .agents/rules/graphify.md .agents/scripts/graphify-auto.ps1 .agents/workflows/graphify.md

# 5. (Optional) Stage GSD Autonomous Planning Artifacts
git add .planning/
```

### Alternative Option: Staging Without `.planning/` (Clean Source Only)

```powershell
# Stage Root Governance, Setup, and Build Files
git add AGENTS.md LICENSE README.md TASK_GATES.md THIRD-PARTY-LICENSES.md .env.example .gitignore .graphifyignore manage.py pyproject.toml requirements.txt

# Stage Core Domain Application Packages
git add catalog/ contracts/ orders/ payments/ policies/ static/ templates/ trustcart/ scripts/

# Stage Documentation & Verification Reports
git add docs/

# Stage Antigravity Automation & Graphify Rules
git add .agents/gsd-core/LICENSE .agents/hooks.json .agents/rules/graphify.md .agents/scripts/graphify-auto.ps1 .agents/workflows/graphify.md
```

*(Note: These commands are prepared for your review and execution; they have NOT been executed by the agent).*

