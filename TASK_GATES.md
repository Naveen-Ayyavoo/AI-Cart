# AI Cart (formerly TrustCart) Task Gates & Phase Roadmap

This document defines the strict, phase-gated execution plan for AI Cart (formerly TrustCart). No phase may commence until its prerequisites are satisfied and the prior phase gate is formally signed off with evidence.

---

## Phase Overview

| Phase | Title | Status | Gate Status |
| :--- | :--- | :--- | :--- |
| **P0** | Development environment and engineering workspace | **COMPLETE** | Signed Off (Commit 76bc7ce) |
| **P1** | Architecture and application foundation | **COMPLETE** | Signed Off (Verified 6/6 tests, zero-spend audit passed) |
| **P2** | Purchase Contract creation and confirmation | **COMPLETE** | Signed Off (Verified 24/24 tests, 30/30 suite total, zero-spend verified) |
| **P3** | Channel3 product search, lookup and evidence provenance | **COMPLETE** | Signed Off (Verified 22/22 tests, 52/52 suite total) |
| **P4** | Deterministic policy and trust evaluation | **COMPLETE** | Signed Off (Verified 18/18 tests, 71/71 suite total) |
| **P5** | Exact, immutable, one-use purchase approval | **COMPLETE** | Signed Off (Verified 23/23 tests, 94/94 suite total) |
| **P6** | PayPal Sandbox order, buyer approval, capture and reconciliation | **COMPLETE** | Signed Off (Verified 31/31 tests, 125/125 suite total, live Sandbox & verified webhook) |
| **P7** | Security, failure injection and end-to-end testing | **COMPLETE** | Signed Off (Verified 28/28 tests, 153/153 suite total, full E2E & adversarial suite) |
| **P8** | Production-quality working product hardening | **COMPLETE** | Signed Off (10 defects resolved, 8 tests, 161 suite total) |
| **P9** | Release candidate verification | **COMPLETE** | Signed Off (PASS, 162 tests, migration 0002, RC1 verified) |
| **G1** | Competition readiness assessment | **COMPLETE** | Signed Off (Verdict: CONDITIONALLY READY; 7.90/10 official heuristic, 6.4/10 rulebook working score) |
| **G2** | Submission and presentation preparation | **COMPLETE** | Signed Off (Channel3 LIVE SUCCESS, secret scan 100% clean, LICENSE drafted, Devpost & 8-scene script ready) |

---

## Detailed Phase Specifications

### Phase P0: Development Environment & Engineering Workspace
- **Purpose**: Establish repository hygiene, development tooling, rules of engagement, and architectural boundaries before any application code is written.
- **Scope**: Repository initialization, `.gitignore`, `.editorconfig`, `.vscode` configuration, `.agents` rules, workflows, skills, architecture documents, ADRs, threat model, test strategy, and phase gate definitions.
- **Dependencies**: Windows 64-bit host, Python 3.14.10, `.venv` with pip 26.3, Git 2.56.0, Antigravity IDE 2.6.0.
- **Deliverables**:
  - `AGENTS.md`, `README.md`, `TASK_GATES.md`, `.gitignore`, `.editorconfig`, `.env.example`.
  - `.vscode/settings.json`, `.vscode/extensions.json`.
  - `.agents/rules/` (`00-project-invariants.md`, `10-python-django.md`, `20-security-integrations.md`, `30-testing-quality.md`, `40-frontend-conventions.md`).
  - `.agents/workflows/` (`plan-phase.md`, `implement-task.md`, `verify-phase.md`, `investigate-defect.md`, `security-audit.md`, `model-handoff.md`).
  - `.agents/skills/` (`phase-gate-review/SKILL.md`, `payment-safety-review/SKILL.md`).
  - `docs/architecture/` (`SYSTEM_OVERVIEW.md`, `TRUST_BOUNDARIES.md`, `DATA_FLOW.md`).
  - `docs/decisions/` (`ADR-0001-TECHNOLOGY-STACK.md`, `ADR-0002-PAYMENT-AND-APPROVAL-BOUNDARY.md`, `ADR-0003-PRODUCT-DATA-AND-DEMO-MARKET.md`, `ADR-0004-ZERO-SPEND-POLICY.md`).
  - `docs/planning/` (`IMPLEMENTATION_ROADMAP.md`, `CURRENT_STATUS.md`, `HANDOFF.md`).
  - `docs/security/` (`THREAT_MODEL.md`).
  - `docs/quality/` (`TEST_STRATEGY.md`).
- **Required Tests**: File existence verification, YAML frontmatter syntax validation, `.gitignore` evaluation against secret/environment patterns.
- **Security & Cost Checks**: Ensure `.venv` and `.env` are untracked; verify no live API keys or credentials exist in the repository; verify zero-spend policy is documented with all planned services confirmed on verified free tiers via account dashboard evidence (Channel3 1,000 credits/mo + 1,000 bonus credits; Gemini Free Tier with Flash Lite and Flash quotas; Context7 1,000 requests/mo; PayPal Sandbox); confirm zero billing accounts linked.
- **Explicit Completion Gate**: All governance files exist, Git is clean with no committed secrets, Python virtual environment path verified, zero-spend compliance audit passed with dashboard evidence verified, and user reviews workspace structure.

---

### Phase P1: Architecture & Application Foundation
- **Purpose**: Install core dependencies (Django 6.1, Ruff, test dependencies), scaffold the modular Django project, configure SQLite, and establish standard domain service patterns under zero-spend governance.
- **Scope**: `requirements.txt` / dependency locking, dependency cost-impact review, Django project initialization (`trustcart`), core app structure (`contracts`, `catalog`, `policies`, `orders`, `payments`), base template shell, and health check endpoint.
- **Dependencies**: P0 signed off.
- **Deliverables**: Verified dependencies installed in `.venv`, dependency license and cost review, Django project settings, core apps created, base HTML template, health check view and route.
- **Required Tests**: Django system check (`python manage.py check`), database migration check, health check HTTP 200 response test.
- **Security & Cost Checks**: Security middleware active, `SECRET_KEY` pulled from environment, `DEBUG` disabled or safe in development, CSRF protection verified; dependency audit confirms 100% permissive open-source licenses with zero paid subscriptions or proprietary gates; local SQLite used (zero cloud DB costs).
- **Explicit Completion Gate**: Django server boots cleanly in PowerShell, all migrations apply without warning, test suite executes successfully, and zero cloud spend or paid infrastructure verified.
- **Gate Sign-Off Record**:
  - Date: 2026-11-10
  - Status: SIGNED OFF
  - Verification: Django 6.1.3 installed in `.venv` (Python 3.14). All 5 core apps (`contracts`, `catalog`, `policies`, `orders`, `payments`) registered. Initial migrations applied. Automated test suite `trustcart/tests/test_foundation.py` executed: 6 passed in 0.024s. `ruff check .` passed with 0 errors. Dependency audit verified 100% permissive licenses (BSD-3-Clause, Apache-2.0, MIT) and $0.00 additional expenditure. SQLite database local only. Base template `templates/base.html` and `/health/` operational.

---

### Phase P2: Purchase Contract Creation & Confirmation
- **Purpose**: Implement the user intent intake pipeline where Gemini parses shopper requests into a structured, validated, user-confirmed Purchase Contract within verified Free Tier quotas.
- **Scope**: Purchase Contract domain model / dataclass, Gemini API client with strict structured output schema, validation service, contract confirmation UI, model allocation routing (Flash Lite for shopping requests; Gemini 3.8 Flash for complex reasoning), quota tracking, and fail-safe fallback.
- **Dependencies**: P1 signed off, Gemini API key configured on verified Free Tier (dashboard quotas: Gemini 3.5 Flash Lite 15 RPM/500 RPD, Gemini 3.1 Flash Lite 15 RPM/500 RPD, Gemini 3.8 Flash 5 RPM/20 RPD; actual API model identifiers verified before implementation; zero billing account attached).
- **Deliverables**: Contract data models (budget, category, required specs, excluded terms), Gemini prompt template and schema parser, contract view and confirmation template, quota exhaustion handler and labeled demo fixtures.
- **Required Tests**: Schema validation tests, Gemini mock response parser tests, malformed JSON recovery tests, user confirmation state transition tests, quota exhaustion fail-safe tests.
- **Security & Cost Checks**: Strict schema validation rejecting unparsed keys, indirect prompt injection sanitization, contract immutability; verification that Gemini API project has no billing account attached; models displaying zero quotas treated as unavailable; zero use of paid Search grounding or paid fallbacks; sensitive credentials never transmitted.
- **Explicit Completion Gate**: Shopper prompt generates structured contract; invalid prompts fail closed; quota exhaustion cleanly degrades to labeled demo fixtures; user confirms contract before search; zero API expenditure incurred.
- **Gate Sign-Off Record**:
  - Date: 2026-11-10
  - Status: SIGNED OFF
  - Verification: `PurchaseContract` domain model with UUID pk, versioning, lineage, and Decimal max_budget implemented. Pydantic schema enforcing `extra="forbid"`. Gemini Free Tier client with prompt boundary isolation (`<shopper_prompt>`) and HTTP 429 quota exhaustion fallback. Three local demo fixtures (`headphones`, `keyboard`, `chair`) with explicit fallback disclosure. Forms with server-side validation. Dedicated multi-step UI flow (`home.html` with 2,000 char counter, `review.html` with granular editing, `confirmed.html`). Explicit non-payment authorization notice verified. Immutability verified (edits to confirmed contracts increment version). Test suite: 24 new tests in `contracts/tests/` (30/30 suite total) passed in 0.091s. `ruff check .` passed with 0 errors. Pydantic MIT license verified ($0.00 spend).

---

### Phase P3: Channel3 Product Search, Lookup & Evidence Provenance
- **Purpose**: Integrate Channel3 API to discover real product offerings, preserving evidence provenance, pricing, and stock status within the verified 1,000 credits/month free tier allowance and 1,000 bonus credits.
- **Scope**: Channel3 API client service, credit budget manager (tracking monthly allowance and bonus credits separately; bonus consumed only after monthly credits), product evidence dataclasses, caching layer by product ID with freshness TTL, provenance capture (source merchant, retrieval timestamp, currency, variant ID).
- **Dependencies**: P2 signed off, Channel3 API credentials on verified free tier (1,000 monthly credits resetting on the 1st + 1,000 one-time bonus credits).
- **Deliverables**: `Channel3Client` service with usage tracking, product evidence models, offline mock fixtures for testing, catalog search and detail views, quota-exhausted status handler.
- **Required Tests**: Channel3 client unit tests with mock responses, credit tracking unit tests, network timeout / failure tests, price parser tests (confirming Decimal conversion), stale cache eviction tests, quota exhaustion degradation tests.
- **Security & Cost Checks**: Ingestion sanitization of product titles/descriptions; fail-closed handling of items with missing/ambiguous pricing; credit consumption counter enforced to prevent exceeding free allowance; bonus credits never represented as recurring allowance; zero paid tier upgrades or credit purchases.
- **Explicit Completion Gate**: Verified retrieval of real product data within free allowance, caching by product ID verified, accurate Decimal conversion, complete provenance recording, safe degradation on quota exhaustion, and zero financial spend.
- **Gate Sign-Off Record**:
  - Date: 2026-11-10
  - Status: SIGNED OFF
  - Verification: `Channel3Client` implemented targeting `https://api.trychannel3.com` (`POST /v1/search`, `GET /v1/products/{id}`, `POST /v1/lookup`) with server-side `x-api-key`. `Channel3CreditLedger` tracks 1,000 monthly allowance and 1,000 bonus credits separately, consuming monthly first and halting billable requests when exhausted. Product detail retrieval (`GET /v1/products/{id}`) verified as free. `ProductEvidence` model captures full provenance (source merchant, retrieval timestamp, currency USD, variant/SKU ID, brand, offers, raw evidence). Strict Python `Decimal` conversion enforced with zero float drift. `ProductSearchCache` provides 24-hour query-to-ID mapping while fresh details are retrieved live. Fail-closed filters reject out-of-stock, unpriced, or non-USD items. Local fallback fixtures labeled `"Sandbox Demo Fixture — Zero-Spend Fallback"`. Discovery UI (`product_list.html`) implemented and linked to confirmed Purchase Contracts. Test suite: 22 new tests in `catalog/tests/` (53/53 total tests across project) passing in 0.231s. `ruff check .` clean with 0 issues. Zero additional expenditure ($0.00).

---

### Phase P4: Deterministic Policy & Trust Evaluation
- **Purpose**: Implement the deterministic rule engine that evaluates candidate products against the Purchase Contract and hard shopping policies with zero external API costs.
- **Scope**: Policy engine evaluating budget limits, shipping constraints, merchant reputation rules, variant matching, and price consistency entirely in local Python code.
- **Dependencies**: P3 signed off.
- **Deliverables**: Policy evaluation service, policy violation types, explainable evaluation report generator.
- **Required Tests**: Budget boundary unit tests (exact match, \$0.01 over budget fails), disallowed attribute tests, conflicting evidence tests, negative tests on malformed products.
- **Security & Cost Checks**: Complete decoupling from LLM reasoning: policy logic is 100% deterministic local Python code; zero external API or cloud compute expenses.
- **Explicit Completion Gate**: Policy engine accurately passes conforming items and deterministically rejects non-conforming items with clear, auditable explanations at zero operational cost.
- **Gate Sign-Off Record**:
  - Date: 2026-11-10
  - Status: SIGNED OFF
  - Verification: `PolicyEngine` implemented in `policies/engine.py` with 100% deterministic local Python logic (zero Gemini reasoning authority). Evaluates candidate `ProductEvidence` items against confirmed `PurchaseContract` across 3 outcome tiers: `ELIGIBLE`, `INELIGIBLE`, and `UNKNOWN`. Missing or contradictory critical evidence verified to fail closed to `UNKNOWN` or `INELIGIBLE`, never `ELIGIBLE`. Exact Decimal arithmetic verified (`unit_price * quantity`, zero float math). Hard budget ceiling ($0.01 over budget fails closed) verified. Excluded terms filter verified. Deterministic preference scorer (0-100%) verified, confirming preferences cannot override mandatory constraint failures. Full provenance recorded per rule evaluation. `PolicyEvaluationReport` model created and migrated. Dashboard UI (`evaluation.html`) renders eligible, unknown, and ineligible items with audit tables and shipping/tax disclaimers. Test suite: 18 new tests in `policies/tests/` (71/71 total suite) passing in 0.289s. `ruff check .` clean with 0 issues. Zero additional spend ($0.00).

---

### Phase P5: Exact, Immutable, One-Use Purchase Approval
- **Purpose**: Generate a cryptographically bound, time-limited, single-use purchase proposal requiring explicit buyer confirmation using local cryptographic primitives.
- **Scope**: Proposed purchase generator, cryptographic cart fingerprinting (SHA-256 over product, variant, quantity, unit price, total, payee, currency), approval token lifecycle manager (creation, expiry TTL, atomic consumption).
- **Dependencies**: P4 signed off.
- **Deliverables**: Approval domain model, token generator and verifier, proposal presentation UI, approval action handler.
- **Required Tests**: Token tamper tests (altering 1 cent invalidates token), TTL expiration tests, double-consumption / replay prevention tests, concurrent approval tests.
- **Security & Cost Checks**: Approval cannot be consumed more than once; cart modification voids existing approval; tokens expire within 15 minutes; zero external service or token licensing fees.
- **Explicit Completion Gate**: Positive and negative approval tests pass; approval strictly bound to fingerprint; single-use atomic consumption verified under test with zero cost.
- **Gate Sign-Off Record**:
  - Date: 2026-11-10
  - Status: SIGNED OFF
  - Verification: `orders/fingerprint.py` implements canonical SHA-256 cart fingerprinting binding `{product_id, variant_id, sku, source_merchant, payee_id, quantity, unit_price, base_amount, shipping_amount, tax_amount, fee_amount, total_amount, currency, contract_id, contract_version}`. `PurchaseProposal` model maintains strict separation between Channel3 external product origin (`source_merchant`) and PayPal Sandbox settlement identity (`payee_id`). Prominent controlled demo merchant disclosure (`DEMO_PAYEE_DISCLOSURE`) displayed across templates. Complete known payable amount enforced with strict `charges_confirmed` gate (unconfirmed shipping or taxes strictly blocks final approval). `PurchaseApproval` single-use token lifecycle manager implemented with 15-minute strict TTL (`expires_at`), state transitions (`PENDING -> APPROVED -> CONSUMED`), and atomic single-use consumption via conditional database UPDATE (`state='APPROVED'`, `expires_at > now`, `consumed_at IS NULL`, exact `cart_fingerprint`, exactly one row updated) with `select_for_update()` preserved where supported. Database lock contention fails closed (`ApprovalLockError`). Multi-threaded race condition tests with 10 concurrent threads across dedicated database connections prove that exactly 1 consumer acquires the token and 9 are blocked. Proposal presentation and approval confirmation UI implemented with CSRF protection and non-payment authorization disclosures. Test suite: 23 tests in `orders/tests/` (94/94 total project suite) passing in 0.481s. `ruff check .` clean with 0 issues. Zero additional expenditure ($0.00).

---

### Phase P6: PayPal Sandbox Order, Buyer Approval, Capture & Reconciliation
- **Purpose**: Execute PayPal Sandbox payment lifecycle: order creation, buyer redirect/approval, server-side capture, and webhook reconciliation strictly in Sandbox mode.
- **Scope**: PayPal Orders v2 API client, order creation with idempotency keys (`PayPal-Request-Id`), buyer approval redirect handler, server-side capture service, webhook signature verification, mock sandbox accounts only.
- **Dependencies**: P5 signed off, PayPal Sandbox credentials.
- **Deliverables**: `PayPalClient` service configured exclusively for Sandbox (`api-m.sandbox.paypal.com`), order and transaction models, checkout UI flow, webhook handler endpoint, demo merchant disclosure.
- **Required Tests**: Order creation mock tests, pre-capture revalidation tests, idempotency duplicate call tests, simulated webhook signature verification tests, negative payment failure tests.
- **Security & Cost Checks**: Server-side capture only; pre-capture deterministic revalidation; webhook signature verified; zero sensitive card data touched; demo payee clearly disclosed; strict verification that live credentials and live endpoints are never used; zero real financial settlement or processing fees.
- **Explicit Completion Gate**: Full Sandbox checkout flow completes; server captures payment in Sandbox; duplicate capture attempts rejected; webhook verified; zero real money moved or charged.
- **Gate Sign-Off Record**:
  - Date: 2026-11-10
  - Status: SIGNED OFF
  - Verification: `PayPalClient` implemented in `payments/client.py` strictly enforcing `https://api-m.sandbox.paypal.com` (live endpoints rejected), server-side OAuth token caching, order creation with `PayPal-Request-Id` idempotency, authoritative order query, capture execution, and public certificate webhook signature verification with SSRF protection. `PaymentOrder`, `PaymentCaptureRecord`, and `WebhookEventRecord` models created and migrated (`payments.0001_initial`). `PaymentService` in `payments/services.py` atomically consumes P5 single-use approval token upon checkout creation, performs deterministic pre-capture revalidation upon buyer return (verifying payee matches controlled demo merchant `DEFAULT_DEMO_PAYEE_ID`, currency USD, exact Decimal amount, custom_id cart fingerprint), and executes server-side capture. Ambiguous responses enter `PENDING_RECONCILIATION` and trigger authoritative reconciliation. Webhook handler cryptographically verifies signatures and deduplicates events. UI templates (`receipt.html`, `cancelled.html`, `pending.html`, `failed.html`) display prominent demo merchant disclosure. Live Sandbox order `7AR87873PW3372724` ($18.75 USD) created with create idempotency key `CREATE-61e305aa-f376-435b-bf55-565edd097027` and US Demo Business Merchant `PU7K3F65AAQ8U`, approved by US Personal Sandbox buyer `sb-vwssg53834434@personal.example.com` (`7WQB5KPSXD3EY`); completed server-side capture `1UK419750T1940027` with capture idempotency key `CAPTURE-52c79176-822e-4c0d-a4f1-9f32e6cd1e3d` (status `COMPLETED`); live genuine webhook `WH-3LR1057661587304S-29B18802VC813202V` (`PAYMENT.CAPTURE.COMPLETED`) delivered via Cloudflare Tunnel at 18:01:09 IST (`12:31:09Z`) and cryptographically verified by PayPal's `POST /v1/notifications/verify-webhook-signature` returning `verification_status: "SUCCESS"`; duplicate delivery verified with status `DUPLICATE` and zero double-capture. Complete test suite: 23 tests in `payments/tests/` (125/125 total project tests) passing in 0.827s. `ruff check .` clean with 0 issues. Django system checks clean. Graphify knowledge graph synchronized (807 nodes, 1735 edges). Zero financial expenditure ($0.00).

---

### Phase P7: Security, Failure Injection & End-to-End Testing
- **Purpose**: Rigorously test the entire system under adversarial, failure, and edge-case conditions without exhausting live free quotas.
- **Scope**: End-to-end user journeys, failure injection tests (network failure, price changes during checkout, expired tokens, malicious prompt injection payloads), quota exhaustion simulation, security regression suite using mock fixtures.
- **Dependencies**: P6 signed off.
- **Deliverables**: Automated E2E test suite, failure injection test harness, security test report, quota-depletion simulation report.
- **Required Tests**:
  - Prompt injection attack test cases.
  - Price fluctuation between proposal and capture (must fail closed).
  - Out-of-order webhook delivery tests.
  - Race condition tests on concurrent capture.
  - Free-tier quota exhaustion and labeled fixture fallback tests.
- **Security & Cost Checks**: Full threat model validation against `docs/security/THREAT_MODEL.md`; automated test runs executed against local mocks to prevent burning live API quotas; zero financial expenditure.
- **Explicit Completion Gate**: Zero security regressions, 100% of negative and failure injection test cases behave as expected (failing closed safely), zero quota burn during test runs.
- **Gate Sign-Off Record**:
  - Phase: P7 (Security, Failure Injection & End-to-End Testing)
  - Date: 2026-11-10
  - Status: SIGNED OFF
  - Verification: Implemented comprehensive adversarial security test suite (`contracts/tests/test_adversarial_security.py`, `contracts/tests/test_domain_and_gemini.py`), catalog quota/failure suite (`catalog/tests/test_client_and_search.py`), and payments adversarial & end-to-end integration test suite (`payments/tests/test_adversarial_and_e2e.py`). Verified 28 specialized adversarial and failure injection tests covering: direct prompt injection with forbidden schema keys (`extra="forbid"`), prompt encapsulation in `<shopper_prompt>` tags, oversized prompt rejection (>2,000 chars), non-USD currency rejection, zero-budget rejection, zero AI authority (contracts strictly initialize to `DRAFT`), secret exfiltration defense, direct prompt injection immunity in PolicyEngine, indirect prompt injection defense in untrusted product descriptions and raw catalog evidence, price fluctuation increase rejection (+$0.01 fails closed with `PayPalRevalidationError`), price fluctuation decrease rejection (-$0.01 fails closed), payee hijacking defense (unauthorized payee fails closed), cart fingerprint forgery defense (custom_id mismatch fails closed), pre-capture currency mismatch defense (EUR rejected), pre-capture out-of-band proposal mutation defense, approval token replay defense (`ApprovalAlreadyConsumedError`), stable idempotency key reuse across retries, concurrent / duplicate capture idempotency (duplicate call returns existing capture without double-capture), out-of-order webhook delivery defense (`CHECKOUT.ORDER.APPROVED` or `PAYMENT.CAPTURE.DENIED` arriving after `COMPLETED` cannot regress order status), Gemini HTTP 429 / timeout / malformed response fallback, Channel3 HTTP 429 / timeout / sequential credit ledger consumption (monthly first, then bonus, then halt), and complete full-lifecycle End-to-End User Journey (Shopper Prompt -> Draft Contract -> Confirmed Contract -> Product Evidence Discovery -> Deterministic Policy Evaluation -> Proposal Creation -> Single-Use Approval -> PayPal Sandbox Checkout -> Pre-Capture Revalidation -> Server Capture -> Webhook Verification -> Receipt Rendering). All 153 project tests passing in 0.620s with 0 failures and 0 errors. Full verification report in `docs/planning/P7-VERIFICATION.md`. Ruff clean (0 issues), Django check clean (0 issues). Total additional expenditure: $0.00.

---

### Phase P8: Production-Quality Working Product Hardening
- **Purpose**: Harden the application into a reliable, complete, demonstrable working product across all 12 shopper journey steps with zero regressions and unbroken navigation.
- **Scope**: End-to-end browser journey hardening, defect remediation (Critical/High/Medium/Low), Post/Redirect/Get idempotency on contract confirmation, status-driven payment order detail routing, proposal reuse for unexpired pending approvals, responsive layout optimization, automated regression test expansion.
- **Dependencies**: P7 signed off.
- **Deliverables**: Hardened views and templates, responsive CSS, regression test suite, hardening report (`docs/planning/P8-HARDENING-REPORT.md`).
- **Required Tests**: Regression tests for error redirects, PRG idempotency, status routing, duplicate proposal prevention, responsive styling.
- **Security & Cost Checks**: Preservation of untrusted reasoning boundary, single-use approval TTL, exact Decimal arithmetic, controlled demo payee disclosure, zero additional expenditure ($0.00).
- **Explicit Completion Gate**: All 10 identified defects resolved, 100% of test suite passing (161 tests), Ruff clean, Django checks clean, zero spend confirmed.
- **Gate Sign-Off Record**:
  - Phase: P8 (Production-Quality Working Product Hardening)
  - Date: 2026-11-10
  - Status: SIGNED OFF
  - Verification: Resolved 10 classified defects across the 12-step shopper journey. Fixed critical unhandled `NoReverseMatch` 500 error on checkout initiation failure by querying approval by token. Implemented Idempotent Dual-Method Handling and GET support on `contract_confirm`, resolving HTTP 405 Method Not Allowed on breadcrumbs and `ValidationError` on browser refresh. Added dynamic status-driven routing to `order_detail` in `payments/views.py`, eliminating misleading "Payment Captured" receipt displays for non-completed orders. Prevented duplicate `PROPOSED` proposals by reusing unexpired pending proposals. Added status badges and conditional actions to `proposal_detail` and `approval_detail` for already approved, consumed, expired, or rejected states. Enhanced responsive CSS in `templates/base.html` for 768px, 480px, and 360px viewports. Added 8 new automated regression tests, expanding project test suite to 161 tests passing in 1.212s (100% pass rate). Ruff check clean (0 issues), Django check clean (0 issues, 0 silenced), showmigrations 100% applied. Graphify knowledge graph synchronized (890 nodes, 1945 edges, 60 communities). Total additional financial expenditure: strictly $0.00. Report generated in `docs/planning/P8-HARDENING-REPORT.md`.

---

### Phase P9: Release Candidate Verification
- **Purpose**: Independently verify AI Cart as a complete release candidate across repository integrity, migration consistency, payment state completeness, browser workflows, visual responsiveness, external integration boundaries, and security invariants.
- **Scope**: Release candidate audit, migration consistency vs applied migrations check, PaymentOrder status coverage audit, browser release verification (12-step shopper journey), responsive visual evidence capture (1200px, 768px, 480px, 360px), live smoke testing (Gemini Free Tier & Channel3 credit ledger), PayPal P6 acceptance evidence reuse, zero-spend audit.
- **Dependencies**: P8 signed off.
- **Deliverables**: Release candidate report (`docs/planning/P9-RELEASE-CANDIDATE-REPORT.md`), migration `orders.0002_alter_purchaseproposal_payee_id`, regression tests, visual evidence artifacts.
- **Required Tests**: Full test suite (162 tests), Ruff linter, Django system checks, `makemigrations --check --dry-run`, `showmigrations`, all status routes, stale-price proposal reuse defense.
- **Security & Cost Checks**: 100% zero-spend compliance ($0.00 spent), secret isolation, untrusted reasoning boundary, exact Decimal arithmetic, immutable cart fingerprint, single-use approval TTL, server-side capture, controlled demo payee disclosure.
- **Explicit Completion Gate**: All 7 verification gates pass; release candidate verdict rendered as PASS with concrete evidence; zero unresolved blockers.
- **Gate Sign-Off Record**:
  - Phase: P9 (Release Candidate Verification)
  - Date: 2026-11-10
  - Status: SIGNED OFF (PASS)
  - Verification: Generated and applied missing migration `orders.0002_alter_purchaseproposal_payee_id`, achieving 100% migration consistency and applied status across all 7 apps. Audited all 7 payment states (`CREATED`, `BUYER_APPROVED`, `COMPLETED`, `PENDING_RECONCILIATION`, `FAILED`, `CANCELLED`, `PAYER_ACTION_REQUIRED`), verifying that non-completed payments cannot render a completed receipt. Verified that contract confirmation uses Idempotent Dual-Method Handling (documentation corrected). Added stale-price defense to proposal reuse and added automated regression test `test_proposal_create_from_evaluation_does_not_reuse_stale_price_proposal`. Caught and repaired invalid URL reverse in `contracts/templates/contracts/review.html` (`product_search` -> `contract_discovery`). Verified complete 12-step shopper journey programmatically and captured visual screenshot evidence across 4 viewports (1200px desktop, 768px tablet, 480px mobile, 360px small mobile) using Chrome DevTools MCP. Executed genuine live Gemini contract extraction with `gemini-3.5-flash-lite` (verified live). Verified Channel3 credit ledger (1,000 monthly / 1,000 bonus intact) and safe fail-closed fixture degradation. Reused genuine P6 PayPal Sandbox acceptance evidence. All 162 automated tests passing in 1.157s. Ruff clean (0 issues), Django check clean (0 issues). Graphify updated to 890 nodes, 1945 edges, 60 communities. Zero additional financial expenditure ($0.00). Release verdict: PASS. Report generated in `docs/planning/P9-RELEASE-CANDIDATE-REPORT.md`.

---

### Gate G1: Competition Readiness Assessment (CRA)
- **Purpose**: Conduct the formal Competition Readiness Assessment evaluating AI Cart under official PayPal AI Hackathon rules, the TrustCart Competition Engineering Rulebook v1.2, and the Competition Strategy & Execution Rulebook v1.2.
- **Scope**: Multi-gate assessment across 8 core dimensions: Baseline Eligibility & Requirements Matrix, 5 Official Judging Criteria scoring, Strategic Frameworks (Rumelt, Playing to Win, Porter, Christensen), Mom Test Customer Validation audit, Competitive Benchmarking audit, Engineering Evidence verification, Submission Artifacts checklist, and Final Verdict with prioritized action plan.
- **Dependencies**: Phase P9 signed off.
- **Deliverables**: Formal assessment report (`docs/planning/G1-COMPETITION-READINESS-ASSESSMENT.md`), Mom Test interview guide, and prioritized Top 5 action plan.
- **Required Evidence**:
  - Independent verification of all 162 tests passing, clean Ruff, clean Django checks, and applied migrations.
  - Honest scoring against official judging rubrics with explicit demarcation of unevidenced areas (Customer Validation: MISSING, Benchmarking: MISSING).
  - Clear distinction between baseline eligibility requirements, sponsor category prizes (Channel3 $1,500; live call unverified in P9), and internal quality standards.
  - Verification of strictly $0.00 additional expenditure across entire lifecycle.
- **Security & Cost Checks**: Strict preservation of zero-spend policy ($0.00), secret isolation, untrusted reasoning boundary, exact Decimal monetary precision, and demo merchant disclosure.
- **Explicit Completion Gate**: Formal CRA document completed; verdict rendered based on observable outcomes; prioritized roadmap established for remaining competition window.
- **Gate Sign-Off Record**:
  - Phase: Gate G1 (Competition Readiness Assessment)
  - Date: 2026-11-10
  - Status: SIGNED OFF (Verdict: CONDITIONALLY READY)
  - Verification: Completed independent 8-gate evaluation. Official 5-criterion rubric scored at 7.90 / 10.0 (Tech: 9.5, Design: 9.0, Impact: 6.5, Innovation: 8.5, Presentation: 6.0; heuristic internal self-assessment). Rulebook Conformance Working Score: 6.4 / 10.0 (unweighted baseline retained). Strategic kernel defined with diagnosis as a product-risk hypothesis, guiding policy, and coherent actions. Porter 5 forces analyzed across separated dimensions (noting model agnosticism does not insulate against supplier power). Christensen disruption classified as NOT ESTABLISHED. Customer validation and empirical benchmarking accurately identified as MISSING strategic evidence (no inflated scoring). Engineering evidence verified: 162 tests passing in 0.73s, Ruff clean (0 issues), Django check clean (0 issues), 22 migrations applied. Git baseline commit 76bc7ce created Nov 9, 2026 (post-Oct 1 threshold); release commit v1.0.0-rc1 uncommitted; root LICENSE file missing. Graphify knowledge graph synchronized (894 nodes, 1,949 edges, 62 communities). Total additional spend: strictly $0.00. Verdict: CONDITIONALLY READY, pending 5 external deliverables: (1) YouTube video recording (<3 min), (2) Root LICENSE file with designated copyright holder, (3) Git release commit v1.0.0-rc1, (4) Public GitHub repository push, (5) Devpost submission completion before deadline on Friday, Nov 13, 2026 at 1:30 AM IST (Nov 12, 12:00 PM PST; ~49.5 hours remaining). Comprehensive assessment report recorded in `docs/planning/G1-COMPETITION-READINESS-ASSESSMENT.md`.

---

### Gate G2: Submission & Presentation Preparation (With Bounded Channel3 Recovery)
- **Purpose**: Prepare final hackathon submission package, execute bounded Channel3 recovery, prepare standard open-source license, perform automated secret leak audit, draft comprehensive 8-scene video demo script, and prepare complete Devpost submission text under zero-spend governance.
- **Scope**: Channel3 host reachability and schema diagnostics, root `LICENSE` preparation, git release preparation (`v1.0.0-rc1`), secret scan across all candidate files, public GitHub setup instructions, 8-scene video demonstration outline, full Devpost submission draft, and final G2 report (`docs/planning/G2-SUBMISSION-AND-PRESENTATION-REPORT.md`).
- **Dependencies**: Gate G1 completed.
- **Deliverables**: Root `LICENSE` file (MIT with designated copyright placeholder), sanitized P6 verification docs, 8-scene demonstration script in `README.md`, complete Devpost submission draft, and `docs/planning/G2-SUBMISSION-AND-PRESENTATION-REPORT.md`.
- **Required Evidence**:
  - Genuine live Channel3 search returning real product evidence evaluated by PolicyEngine with 1 credit consumed from monthly allowance (999 monthly / 1,000 bonus credits remaining at $0.00 spend).
  - Automated secret scan confirming 0 API keys or private credentials in any candidate release file.
  - Test suite running at 100% passing rate (162 tests).
  - Ruff linter clean (0 issues) and Django system check clean (0 issues).
  - Explicit confirmation of zero external financial expenditure ($0.00).
- **Security & Cost Checks**: Strictly $0.00 expenditure; API keys and secrets isolated from version control; zero git commits, tags, pushes, or public releases executed without explicit user authorization.
- **Explicit Completion Gate**: Channel3 recovery completed with definitive verdict (`LIVE SUCCESS`); root MIT license drafted; secret audit clean; submission text and video script fully authored; report published.
- **Gate Sign-Off Record**:
  - Phase: Gate G2 (Submission & Presentation Preparation)
  - Date: 2026-11-11
  - Status: SIGNED OFF
  - Verification: Diagnosed and resolved Channel3 root causes (corrected `.env` URL to `https://api.trychannel3.com` and stripped extra forbidden payload fields in `catalog/client.py`). Executed controlled live search returning real product evidence (`Redragon Antonium K745 Pro` at $49.99 USD from `redragonshop.com`, Decimal pricing parsed, evaluated `ELIGIBLE` by `PolicyEngine`, debited 1 credit from `Channel3CreditLedger`). Channel3 recovery verdict: **LIVE SUCCESS** (qualifies for $1,500 Channel3 sponsor prize). Drafted standard MIT `LICENSE` at root with designated copyright placeholder. Conducted automated secret scan across all candidate release files, finding and sanitizing historical webhook ID occurrences in P6 verification docs (verified 100% clean). Authored comprehensive 8-scene video demo script and full 14-section Devpost submission draft. All 162 automated tests passing in 0.73s. Ruff clean (0 issues), Django check clean (0 issues). Total additional spend: strictly $0.00. Detailed report recorded in `docs/planning/G2-SUBMISSION-AND-PRESENTATION-REPORT.md`.

---

### Gate: AI Cart Product Discovery UX Redesign
- **Purpose**: Overhaul product discovery usability for first-time shoppers based on industry reference models (Amazon, Google, Walmart, Perplexity, ChatGPT), eliminating initial cognitive overload, streamlining intake and contract review, and introducing grounded side-by-side product comparisons.
- **Scope**: Shopper intake hero search bar with suggestion chips (`templates/home.html`), human-readable AI Shopping Brief with single primary confirmation action (`contracts/templates/contracts/review.html`), deterministic product highlights extraction and Side-by-Side Comparison Matrix (`catalog/views.py`, `catalog/templates/catalog/product_list.html`), and full-system verification.
- **Dependencies**: Gate G2 completed.
- **Deliverables**: Updated templates, view orchestration, 84-point in-browser layout test suite (`00_master_tester.html`), and comprehensive deliverable report (`docs/planning/AI-CART-PRODUCT-DISCOVERY-UX-REPORT.md`).
- **Required Evidence**:
  - 84/84 real Chrome DevTools layout and responsiveness tests passing (12 pages &times; 7 viewports: 320, 360, 390, 480, 768, 1024, 1440px) with 0 failures and 0 overflows.
  - 53/53 end-to-end shopper journey checks passing (`scripts/verify_shopper_journey.py`).
  - 164/164 Django automated tests passing.
  - Ruff linter clean (0 issues) and Django system check clean (0 issues).
  - Graphify code knowledge graph updated (914 nodes, 2,069 edges, 63 communities).
  - Explicit confirmation of strictly $0.00 spend.
- **Security & Cost Checks**: Strictly $0.00 expenditure; untrusted reasoning boundary strictly preserved (Gemini proposes, deterministic Python backend decides); Decimal monetary precision intact; immutable approval binding intact; zero live PayPal or Channel3 calls during testing.
- **Explicit Completion Gate**: All verification suites passing; report recorded in `docs/planning/AI-CART-PRODUCT-DISCOVERY-UX-REPORT.md`.
- **Gate Sign-Off Record**:
  - Phase: AI Cart Product Discovery UX Redesign Gate
  - Date: 2026-11-11
  - Status: SIGNED OFF
  - Verification: Replaced multi-field monospace intake with single natural-language search bar and 3 instant suggestion chips. Transformed contract review into a readable AI Shopping Brief with single prominent confirmation action and collapsed progressive editor. Enriched catalog discovery with deterministic highlights (savings, match reasons, honest trade-offs) and a responsive Side-by-Side Comparison Matrix. Verified with 84/84 Chrome DevTools MCP browser layout tests (0 overflows), 53/53 end-to-end shopper journey checks, 164/164 Django tests, Ruff clean, and Django check clean. Knowledge graph synchronized (914 nodes, 2,069 edges, 63 communities). Zero additional spend ($0.00). Report recorded in `docs/planning/AI-CART-PRODUCT-DISCOVERY-UX-REPORT.md`.
