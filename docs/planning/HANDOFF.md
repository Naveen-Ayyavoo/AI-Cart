# AI Cart Model Handoff State
> **Intelligence in Every Click** *(Formerly developed under working name TrustCart)*

**Date & Time**: 2026-11-13T00:45:00+05:30<br>
**Active Gate**: Final Release Manifest Corrections & History Security Certification Complete — **READY FOR FINAL MANUAL RELEASE REVIEW**<br>
**Current Phase Gate Status**: Phases P0–P9, Gate G1/G2, UX Defect Resolution, Conformance Audit, Gap Closure, Layout Corrections, Custom 404, Pre-Commit Hygiene, Complete Rebranding, Manifest Corrections, and Git History Certification COMPLETE; Official Hackathon Submission **BLOCKED PENDING USER ACTIONS** (Release Commit/GitHub Push, `<3 min` Demo Video, Devpost Form before Nov 13 1:30 AM IST)<br>
**Test Suite**: 227 passed in 22.14s (100% pass rate, 0 failures, 0 errors; offline isolated `$0.00`)<br>
**Browser & Accessibility Verification**: `100` live Chrome screenshots (`final-404` pass across `27` routes & `7` viewports `320–1648px`, `200%` zoom reflow at `640px`, `forced-colors`, `0` console/5xx/contrast/dupLink/overflow issues; custom 404 verified at 1440px, 1024px, 390px, 320px)<br>
**Shopper Journey Suite**: 56/56 checks passed across 10 E2E stages<br>
**Secret Scan**: 1,287 files scanned across repository tree + all 909 Git history blobs; 0 leaks of credentials, keys, or private data<br>
**Allowlist Status**: Reconciled to exact 170 newly approved paths + 1 baseline `.editorconfig` = 171 total files in `RELEASE-FILE-ALLOWLIST.md`<br>
**Graphify Knowledge Graph**: 1,202 nodes, 2,829 edges, 84 communities<br>
**Total Expenditure**: Strictly $0.00 (Zero-Spend Policy Verified)

---

## 1. Completed Work

### Phase P0: Workspace & Governance Initialization (Complete & Committed)
- Initialized local Git repository on branch `main` with baseline commit `76bc7ce`.
- Configured repository hygiene, `.gitignore`, `.editorconfig`, `.env.example`, `.vscode/settings.json`.
- Established architecture specs, ADR-0001 through ADR-0004, threat model, test strategy, and task gates.
- Zero-spend policy verified with dashboard evidence for Gemini Free Tier, Channel3, Context7, and PayPal Sandbox.
- GSD Core v1.20.1 onboarded with full codebase mapping.

### Phase P1: Architecture & Application Foundation (Complete & Signed Off)
- Pinned and verified dependencies in `requirements.txt` (Django 6.1.3, python-dotenv 1.2.4, ruff 0.17.4; 100% open-source permissive licenses; $0.00 spend).
- Scaffolded modular Django project `trustcart` with 5 decoupled domain applications (`contracts`, `catalog`, `policies`, `orders`, `payments`).
- Configured `trustcart/settings.py` (local SQLite `db.sqlite3` [gitignored], security middleware, template/static directories, Decimal monetary constants).
- Built base layout template `templates/base.html` and operational `/health/` monitoring endpoint.
- Signed off Phase P1 in `TASK_GATES.md`, `ROADMAP.md`, `STATE.md`, and `REQUIREMENTS.md`.

### Phase P2: Purchase Contract Creation & Confirmation (Complete & Signed Off)
- Created `PurchaseContract` model with versioning, lineage, Decimal `max_budget`, and 2,000 char prompt limit.
- Pydantic schema validation with `extra="forbid"`.
- Gemini client with Free Tier model allocation (`gemini-3.5-flash-lite` routine, `gemini-3.8-flash` complex) and HTTP 429 quota exhaustion fallback.
- Multi-step UI workflow: intake (`home.html`), review & edit (`review.html`), and locked contract receipt (`confirmed.html`).
- Non-payment authorization disclosure and CSRF protection on contract confirmation.

### Phase P3: Channel3 Product Search, Lookup & Evidence Provenance (Complete & Signed Off)
- Channel3 API client interfacing with `https://api.trychannel3.com` (`POST /v1/search`, `GET /v1/products/{id}`, `POST /v1/lookup`) with server-side `x-api-key`.
- `Channel3CreditLedger` tracks 1,000 monthly allowance and 1,000 bonus credits separately, consuming monthly first and halting billable requests when exhausted. Product detail calls are free.
- `ProductEvidence` model captures full provenance with strict Python `Decimal` prices.
- `ProductSearchCache` provides 24-hour query-to-ID mapping while fresh details are retrieved live.
- Fail-closed filters reject out-of-stock, unpriced, or non-USD items.
- Local fallback fixtures labeled `"Sandbox Demo Fixture — Zero-Spend Fallback"`.

### Phase P4: Deterministic Policy & Trust Evaluation (Complete & Signed Off)
- **Engine Architecture (`policies/engine.py`)**:
  - `PolicyEngine`, `RuleEvaluationRecord`, and `PolicyEvaluationResult` implemented in 100% deterministic local Python logic.
  - Evaluation outcomes: `ELIGIBLE`, `INELIGIBLE`, and `UNKNOWN`.
  - Missing or contradictory critical evidence fails closed to `UNKNOWN`, never `ELIGIBLE`.
  - Currency rule (USD only).
  - Positive Decimal price rule.
  - Budget ceiling rule: `total_price = unit_price * quantity <= max_budget` ($0.01 over fails closed).
  - Stock availability rule (`IN_STOCK` passes, `OUT_OF_STOCK` fails, `UNKNOWN` produces unknown).
  - Excluded terms rule: scans brand, title, description, and raw evidence.
  - Category compatibility rule.
  - Required specifications rule: critical required specs must be verified in evidence; unverified critical specs produce `UNKNOWN`.
  - Deterministic preference scoring (0-100%): preferences cannot override mandatory constraint failures.
  - Full provenance tracking on every rule decision.
  - Mandatory shipping and tax disclaimer.
- **Data Model & Persistence (`policies/models.py`)**:
  - `PolicyEvaluationReport` capturing contract, product, outcome, unit price, quantity, total price, budget ceiling, preference score, matched/missed preferences, and serialized rule results.
  - Applied migration `policies.0001_initial`.
- **Service & Dashboard UI (`policies/services.py`, `policies/views.py`, `evaluation.html`)**:
  - `PolicyEvaluationService` orchestrates evaluation of candidate products for confirmed contracts.
  - Server-side revalidation guarantees zero trust in browser-supplied data.
  - Dashboard UI displays distinct outcome tiers (Eligible in green, Uncertain in amber, Ineligible in red) with rule-by-rule audit inspection tables.
  - Primary navigation links wired from candidate product list to policy dashboard.
- **Automated Test Suite**:
  - 18 comprehensive tests in `policies/tests/` (13 engine unit tests + 5 service/view integration tests).
  - Full test suite passing (**71/71 tests in 0.289s**), Ruff clean (**0 issues**), Django checks clean (**0 issues**).
  - Signed off Phase P4 in `TASK_GATES.md`, `ROADMAP.md`, `STATE.md`, and `REQUIREMENTS.md`.

### Phase P5: Exact, Immutable, One-Use Purchase Approval (Complete & Signed Off)
- Implemented canonical SHA-256 cart fingerprinting in `orders/fingerprint.py` binding `{product_id, variant_id, sku, source_merchant, payee_id, quantity, unit_price, base_amount, shipping_amount, tax_amount, fee_amount, total_amount, currency, contract_id, contract_version}`.
- Modeled `PurchaseProposal` (`orders/models.py`) strictly separating external catalog product origin (`source_merchant`) from PayPal Sandbox settlement identity (`payee_id`).
- Implemented complete payable breakdown (`base_amount`, `shipping_amount`, `tax_amount`, `fee_amount`, `total_amount`) with strict `charges_confirmed` gate (unconfirmed shipping or taxes blocks final approval).
- Modeled `PurchaseApproval` with 15-minute strict TTL (`expires_at`), state machine (`PENDING -> APPROVED -> CONSUMED`), and atomic single-use consumption via `select_for_update()`.
- Implemented tamper voiding (`ApprovalInvalidError`), replay protection (`ApprovalAlreadyConsumedError`), and TTL expiration checks (`ApprovalExpiredError`).
- Verified race-condition resistance: 10 concurrent threads simultaneously competing to consume the same token resulted in exactly 1 success and 9 rejections.
- Implemented proposal presentation UI and approval receipt UI with CSRF protection and prominent `DEMO_PAYEE_DISCLOSURE`.
- Implemented atomic conditional database UPDATE (`state='APPROVED'`, `expires_at > now`, `consumed_at IS NULL`, exact `cart_fingerprint`, exactly 1 row updated; `select_for_update` preserved where supported) and fail-closed lock handling (`ApprovalLockError`).
- 23 automated tests in `orders/tests/` (94/94 total tests across project passing in 0.481s), Ruff clean, Django checks clean.

### Phase P6: PayPal Sandbox Order, Buyer Approval, Capture & Reconciliation (Complete & Signed Off)
- Implemented `PayPalClient` in `payments/client.py` strictly restricted to `https://api-m.sandbox.paypal.com` (rejecting live endpoints), with server-side OAuth 2.0 token caching, order creation with `PayPal-Request-Id` idempotency, authoritative order query, server capture, and webhook signature verification with SSRF defense.
- Modeled `PaymentOrder`, `PaymentCaptureRecord`, and `WebhookEventRecord` (`payments/models.py`), linking consumed `PurchaseApproval` to PayPal Orders v2 transactions. Applied migration `payments.0001_initial`.
- Implemented `PaymentService` (`payments/services.py`):
  - `initiate_checkout`: Consumes single-use approval token atomically via conditional database update; generates stable, distinct idempotency keys for creation and capture; creates PayPal order; returns Sandbox approve redirect URL.
  - `complete_checkout`: Never trusts query redirect parameters; queries PayPal Orders v2 authoritatively via `GET /v2/checkout/orders/{id}`; performs deterministic Pre-Capture Revalidation (payee matches configured demo merchant, currency == `USD`, exact Decimal amount, custom_id == `cart_fingerprint`); executes server-side capture via `POST /v2/checkout/orders/{id}/capture` with dedicated `capture_idempotency_key`; marks order `COMPLETED` (PAID) only upon authoritative `COMPLETED` capture status.
  - Fault tolerance: Ambiguous responses or network timeouts enter `PENDING_RECONCILIATION` and query PayPal authoritatively before retrying.
  - `handle_webhook`: Cryptographically verifies signatures against PayPal public certificates, deduplicates events on `event_id`, and dispatches state updates for `CHECKOUT.ORDER.APPROVED`, `PAYMENT.CAPTURE.COMPLETED`, and `PAYMENT.CAPTURE.DENIED`.
- Implemented views (`payments/views.py`), templates (`receipt.html`, `cancelled.html`, `pending.html`, `failed.html`), and action buttons with prominent `DEMO_PAYEE_DISCLOSURE`.
- **Live Acceptance Evidence (US Sandbox & Live Webhook)**:
  - US Sandbox Business Merchant: `PU7K3F65AAQ8U` (`sb-rkzmd53830818@business.example.com`).
  - US Sandbox Personal Buyer: `7WQB5KPSXD3EY` (`sb-vwssg53834434@personal.example.com`).
  - Live PayPal Order: `7AR87873PW3372724` ($18.75 USD) created from local `PaymentOrder` `16d5f41d-258e-4e9d-9d9b-bc1e2221a01d` (create idempotency key `CREATE-61e305aa-f376-435b-bf55-565edd097027`, capture key `CAPTURE-52c79176-822e-4c0d-a4f1-9f32e6cd1e3d`).
  - Buyer approved the order via Sandbox portal; pre-capture verified payee, amount, currency, and cart fingerprint.
  - Authoritative Server Capture: `1UK419750T1940027` completed and marked `COMPLETED` (PAID).
  - Genuine Webhook Delivery: Received `WH-3LR1057661587304S-29B18802VC813202V` (`PAYMENT.CAPTURE.COMPLETED`) via Cloudflare Tunnel. Cryptographically verified against PayPal `POST /v1/notifications/verify-webhook-signature` returning `verification_status: "SUCCESS"`; status transitioned to `PROCESSED`.
  - Deduplication: Repeated delivery correctly marked as `status="DUPLICATE"` with zero duplicate capture.
  - Historical Indian sandbox transaction `db0c6346-8988-420e-9ca5-273dd9ceef45` (`27865393PA075990R`) preserved.
- 23 automated tests in `payments/tests/` (125/125 total tests across project passing in 0.827s), Ruff clean, Django checks clean. Zero financial expenditure ($0.00).

### Phase P7: Security, Failure Injection & End-to-End Testing (Complete & Signed Off)
- **Adversarial Security Test Suite (`contracts/tests/test_adversarial_security.py`)**:
  - Pydantic strict schema validation: injected extra keys rejected via `extra="forbid"`.
  - Prompt tag injection defense: shopper input strictly wrapped in `<shopper_prompt>` tags.
  - Oversized prompt DOS defense: prompts exceeding 2,000 characters rejected via `PromptIntakeForm`.
  - Non-USD currency injection rejected (`EUR`, `GBP`, `BTC`).
  - Zero/negative budget inputs rejected.
  - Zero AI authority invariant: Gemini extraction output strictly initializes contracts to `DRAFT` state only.
- **Payments Adversarial & End-to-End Test Suite (`payments/tests/test_adversarial_and_e2e.py`)**:
  - Price fluctuation defense (+$0.01): remote PayPal price $91.40 vs approved $91.39 aborts capture, fails closed, and transitions order to `FAILED`.
  - Price fluctuation defense (-$0.01): remote PayPal price $91.38 vs approved $91.39 fails closed.
  - Payee tampering defense: unauthorized payee ID fails closed.
  - Cart fingerprint forgery defense: custom_id mismatch between PayPal order and approved proposal aborts capture.
  - Concurrent / duplicate capture race conditions: idempotency key and state check return existing capture without double-capture.
  - Out-of-order webhook delivery defense: `CHECKOUT.ORDER.APPROVED` or `PAYMENT.CAPTURE.DENIED` cannot regress an already `COMPLETED` order.
  - Complete End-to-End User Journey: Verified complete flow from shopper prompt -> draft contract -> confirmed contract -> candidate product search -> deterministic policy evaluation -> proposal creation -> single-use approval -> PayPal sandbox checkout -> pre-capture revalidation -> server capture -> webhook verification -> order receipt.
- **P6 Evidence Reconciliation**:
  - Reconciled create-order idempotency key (`CREATE-61e305aa-f376-435b-bf55-565edd097027`) vs capture key (`CAPTURE-52c79176-822e-4c0d-a4f1-9f32e6cd1e3d`) in `TASK_GATES.md` and `P6-VERIFICATION.md`.
  - Reconciled webhook timeline: transmission at 12:31:09Z (18:01:09 IST) cryptographically verified by PayPal's `POST /v1/notifications/verify-webhook-signature`.
- **Hackathon Submission Readiness**:
  - Judge-ready `README.md` with Windows quickstart, step-by-step interactive demo walkthrough, 3-minute video outline, and demo merchant disclosure.
  - Safe `.env.example` verified with placeholders only (`CHANNEL3_BASE_URL=https://api.trychannel3.com`).
  - Total test suite: **153 tests passing in 0.620s**. Full audit documented in `docs/planning/P7-VERIFICATION.md`. Ruff clean (0 issues). Django check clean (0 issues). Zero additional spend ($0.00).

### Phase P8: Production-Quality Working Product Hardening (Complete & Signed Off)
- Resolved 10 classified defects across the 12-step shopper journey.
- Fixed critical unhandled `NoReverseMatch` 500 error on checkout initiation failure by querying approval by token.
- Implemented Idempotent Dual-Method Handling on `contract_confirm`, resolving HTTP 405 Method Not Allowed on breadcrumbs and `ValidationError` on browser refresh.
- Added dynamic status-driven routing to `order_detail` in `payments/views.py`, eliminating misleading "Payment Captured" receipt displays for non-completed orders.
- Prevented duplicate `PROPOSED` proposals by reusing unexpired pending proposals.
- Added status badges and conditional actions to `proposal_detail` and `approval_detail` for already approved, consumed, expired, or rejected states.
- Enhanced responsive CSS in `templates/base.html` for 768px, 480px, and 360px viewports.
- Added 8 new automated regression tests, expanding project test suite to 161 tests passing in 1.212s (100% pass rate). Ruff clean (0 issues), Django check clean (0 issues).

### Phase P9: Release Candidate Verification (Complete & Signed Off — PASS)
- Generated and applied missing migration `orders.0002_alter_purchaseproposal_payee_id`, achieving 100% migration consistency and applied status across all 7 apps.
- Audited all 7 payment states (`CREATED`, `BUYER_APPROVED`, `COMPLETED`, `PENDING_RECONCILIATION`, `FAILED`, `CANCELLED`, `PAYER_ACTION_REQUIRED`), verifying that non-completed payments cannot render a completed receipt.
- Added stale-price defense to proposal reuse and added automated regression test `test_proposal_create_from_evaluation_does_not_reuse_stale_price_proposal`.
- Repaired invalid URL reverse in `contracts/templates/contracts/review.html` (`product_search` -> `contract_discovery`).
- Verified complete 12-step shopper journey programmatically and captured visual screenshot evidence across 4 viewports (1200px desktop, 768px tablet, 480px mobile, 360px small mobile) using Chrome DevTools MCP.
- Executed genuine live Gemini contract extraction with `gemini-3.5-flash-lite` (verified live).
- Verified Channel3 credit ledger (1,000 monthly / 1,000 bonus intact) and safe fail-closed fixture degradation.
- Reused genuine P6 PayPal Sandbox acceptance evidence. All 162 automated tests passing in 1.157s. Ruff clean (0 issues), Django check clean (0 issues). Release verdict: PASS. Documented in `docs/planning/P9-RELEASE-CANDIDATE-REPORT.md`.

### Gate G1: Competition Readiness Assessment (Complete & Signed Off — CONDITIONALLY READY)
- Completed independent 8-gate evaluation against official PayPal AI Hackathon rules, the TrustCart Competition Engineering Rulebook v1.2, and the Competition Strategy & Execution Rulebook v1.2.
- Scored official 5-criterion rubric: **7.90 / 10.0** (Tech: 9.5, Design: 9.0, Impact: 6.5, Innovation: 8.5, Presentation: 6.0; heuristic internal self-assessment).
- Rulebook Conformance Working Score: **6.4 / 10.0** (Unweighted baseline retained pending defensible evidence-based re-audit; previous unsupported 9.3/10 claim retracted).
- Formulated Rumelt Strategy Kernel (with diagnosis as a product-risk hypothesis), Playing to Win framework, Porter 5 Forces across separated dimensions (noting model agnosticism does not insulate from supplier power), and Christensen Disruption assessment (classified as NOT ESTABLISHED).
- Audited customer validation: Found 0 recorded interviews; created 5-question Mom Test interview script and evidence capture template; classified Customer Discovery as **MISSING STRATEGIC EVIDENCE** (not a mandatory Devpost field).
- Audited benchmarking: Found no empirical head-to-head live assistant benchmarks; classified Benchmarking as **MISSING STRATEGIC EVIDENCE** (not a mandatory Devpost field).
- Audited 12 submission deliverables: verified baseline creation post-Oct 1, 2026 (Nov 9 commit 76bc7ce); identified missing root LICENSE file and uncreated remote GitHub repo; Channel3 sponsor prize ($1,500 cash) marked UNVERIFIED LIVE due to P9 DNS failure (optional track).
- Verdict: **CONDITIONALLY READY** pending mandatory public submission items and repository housekeeping. Documented in `docs/planning/G1-COMPETITION-READINESS-ASSESSMENT.md`.

### Gate G2: Submission & Presentation Preparation (Complete & Signed Off)
- Executed bounded Channel3 recovery: diagnosed `.env` domain mismatch and stripped rejected schema fields (`extra_forbidden`); executed live search returning real products (`Redragon Antonium K745 Pro` at $49.99 USD from `redragonshop.com`), evaluated `ELIGIBLE` by `PolicyEngine`, and debited 1 credit from `Channel3CreditLedger`. Channel3 verdict: **LIVE SUCCESS** (qualifies for $1,500 Channel3 sponsor prize).
- Prepared standard MIT `LICENSE` file at root with explicit copyright holder placeholder awaiting user input.
- Conducted deep automated secret scan across all candidate files; found and sanitized hardcoded webhook IDs in historical P6 verification docs; verified 100% clean.
- Authored 8-scene demo video storyboard and script in `README.md` and G2 report (~3 min timing, narration, actions, fallback contingencies).
- Prepared complete 14-section copy-paste Devpost submission draft.
- All 162 automated tests passing in 0.73s. Ruff clean (0 issues), Django check clean (0 issues). Zero additional spend ($0.00). Documented in `docs/planning/G2-SUBMISSION-AND-PRESENTATION-REPORT.md`.

### Knowledge Graph Baseline (Graphify Tooling — Complete)
- Installed official `graphifyy` CLI (v0.9.105) via `uv tool install graphifyy` with zero modification to application code and zero virtual environment pollution.
- Completed Antigravity integration (`graphify antigravity install`), installing `.agents/rules/graphify.md` and `.agents/workflows/graphify.md` while preserving all GSD Core workflows and project invariants.
- Configured repository protections: `.graphifyignore` created to exclude `.env`, `.venv`, `db.sqlite3`, `.planning/`, `.agents/`; `graphify-out/` added to `.gitignore`.
- Built code-only knowledge graph offline (`graphify extract . --code-only`, `graphify cluster-only . --no-label`):
  - **Metrics**: 894 nodes, 1,949 edges, 62 communities across 86 code files.
  - **God Nodes Identified**: `PurchaseContract` (78 edges), `ProductEvidence` (55 edges), `PurchaseApproval` (34 edges), `PurchaseProposal` (34 edges), `PolicyEvaluationReport` (28 edges), `PayPalClient` (28 edges), `PaymentService` (28 edges), `PaymentOrder` (24 edges).
  - **Zero Cost**: 100% offline AST extraction ($0.00 spend, zero LLM tokens, zero external API requests).
- Traced 4 critical architectural paths via graph queries (`graphify path`, `graphify explain`):
  1. `PurchaseApproval` fingerprint -> atomic consumption (`orders/services.py:L157`) -> `PaymentService` (`payments/services.py:L48`).
  2. `PaymentService` (`payments/services.py:L53`) -> `PayPalClient` (`payments/client.py:L49`) -> `PaymentOrder` (`payments/models.py:L22`).
  3. `paypal_webhook_listener()` (`payments/views.py:L104`) -> `PaymentService.handle_webhook()` -> `._process_verified_webhook_event()` -> `.reconcile_order()` (`payments/services.py`), backed by `WebhookEventRecord` (`payments/models.py:L118`).
  4. `PurchaseContract` -> `ProductSearchService` -> `ProductEvidence` -> `PolicyEvaluationReport` -> `PurchaseProposal` -> `ApprovalService` -> `PurchaseApproval`.
- Knowledge Graph Refresh Command: `graphify update . --force` (offline clustering: `graphify cluster-only . --no-label`).
- **Automated Lifecycle Enforcement**:
  - Registered native Antigravity lifecycle hooks in `.agents/hooks.json` invoking `.agents/scripts/graphify-auto.ps1`.
  - `PreInvocation` hook runs before model reasoning, checks SHA-256 fingerprint of indexable sources against `.graphify-runtime/last-indexed-source.sha256`, conditionally updates the graph via atomic lock protection (`.graphify-runtime/graphify.lock`), and injects a mandatory system directive requiring Graphify consultation.
  - `Stop` hook runs when `fullyIdle` is true, ensuring any source code modifications during a task are incorporated into the graph even without a follow-up model prompt.
  - Updated `.agents/rules/graphify.md` with 10 mandatory operating requirements for graph-first architecture review and ground-truthing.
  - Automated test suite verified 10/10 lifecycle tests in `scratch/test_hook_lifecycle.ps1`. Runtime state and logs stored in `.graphify-runtime/` (gitignored). Zero application code changes and $0.00 spend.

---

## 2. Key Architectural Invariants Enforced
- **Untrusted Reasoning Boundary & Deterministic Backend Authority (Invariants 1 & 2)**: Gemini proposes structured data but NEVER owns payment state or authorization; backend owns all validation, capture execution, and state transitions.
- **Fail-Closed Principle & Critical Uncertainty (Invariants 3 & 4)**: Missing or contradictory critical facts fail closed to `UNKNOWN` or `INELIGIBLE`. Discrepancies during pre-capture revalidation halt capture and mark the order `FAILED`.
- **Monetary Precision (Invariant 5)**: All monetary values use Python `Decimal` (`unit_price * quantity`, zero `float`).
- **Immutable Approval Binding (Invariant 6)**: Purchase approval binds cryptographically to exact parameters and cart fingerprint. Altering 1 cent or any parameter voids approval.
- **Single-Use, Time-Limited Approvals (Invariant 7)**: Approvals have a 15-minute TTL and are consumable exactly once via atomic state transition.
- **Decoupled Two-Stage Approvals (Invariant 8)**: TrustCart purchase approval confirms the proposal; PayPal buyer approval authorizes payment in PayPal Sandbox; server-side capture executes as the final gate.
- **Server-Side Capture & Webhook Verification (Invariants 9 & 10)**: PayPal capture occurs exclusively server-side. Incoming webhooks cryptographically verify signatures against PayPal public certificates.
- **Controlled Demo Payee Disclosure (Invariant 13)**: Prominently disclosed demo merchant boundary across all checkout, return, and receipt screens; zero claim of arbitrary third-party settlement.
- **Zero-Spend Engineering Policy (ADR-0004 & Invariant 15)**: 100% local execution and PayPal Sandbox; zero external API charges ($0.00).

---

## 3. Verification & Test Evidence
- **Django System Check**:
  ```powershell
  .\.venv\Scripts\python.exe manage.py check
  # Output: System check identified no issues (0 silenced).
  ```
- **Automated Test Suite (Full Project)**:
  ```powershell
  .\.venv\Scripts\python.exe manage.py test
  # Output: Ran 227 tests in 13.572s (OK, offline env isolated, 100% pass rate)
  ```
- **Chrome Screenshot Audit & Live Checks**:
  ```
  Chrome CDP suite: 27 routes, 100 screenshots across 320-1648px, 200% zoom reflow, forced-colors, 0 console/5xx/contrast/dupLink/overflow defects.
  ```
- **10-Step Shopper Journey Acceptance Suite (56 Checks)**:
  ```powershell
  .\.venv\Scripts\python.exe scripts/verify_shopper_journey.py
  # Output: VERDICT: ALL 56/56 CHECKS PASSED (100%)
  ```
- **Ruff Code Linter**:
  ```powershell
  .\.venv\Scripts\ruff.exe check .
  # Output: All checks passed!
  ```
- **Integrated Verification Pipeline (`scripts/run_all_verifications.py`)**: All 7/7 quality gates passed cleanly (Exit Code 0).
- **Secret & Privacy Scan**: 1,285 candidate release files scanned; 0 leaks of credentials, keys, or passwords.
- **Zero-Spend Audit**:
  Total additional expenditure: **$0.00**.

---

## 4. Current Status & Next Steps
- **Current Position**: Phases P0–P9, Gate G1/G2, Frontend Remodel, UX Defect Fixes, Independent Audit Fixes, Shopping Flow UX Corrections, Custom 404, Pre-Commit Hygiene, Complete Rebranding, Manifest Corrections, and Git History Security Audit are COMPLETE and documented in [AI-CART-REPOSITORY-CLEANUP-AND-REBRANDING-REPORT.md](file:///d:/TrustCart/docs/planning/AI-CART-REPOSITORY-CLEANUP-AND-REBRANDING-REPORT.md).
- **Release Status**: Release Candidate `v1.0.0-rc1` (`170` newly approved paths + 1 baseline `.editorconfig` = `171` total files in `RELEASE-FILE-ALLOWLIST.md`; uncommitted locally, nothing staged; 100% clean).
- **Ranked P0 Action Plan for User Execution (Before Nov 13, 1:30 AM IST)**:
  1. **Verify `LICENSE` Author Line** (`Copyright (c) 2026 Naveen` in root `LICENSE`) & confirm `.planning/` inclusion choice from `RELEASE-FILE-ALLOWLIST.md`.
  2. **Stage Allowlisted Files & Commit Release Candidate**: Use explicit `git add` commands from Section 13/15 of `AI-CART-REPOSITORY-CLEANUP-AND-REBRANDING-REPORT.md` (NEVER `git add .`) and tag `v1.0.0-rc1`.
  3. **Push to Public GitHub**: Create public repository and push `main` + tags.
  4. **Record `<3 min` Public Demo Video**: Follow G2 8-scene storyboard and upload to YouTube.
  5. **Submit Devpost Form**: Copy-paste submission text from `docs/planning/G2-SUBMISSION-AND-PRESENTATION-REPORT.md` with GitHub & YouTube URLs before **Nov 13, 1:30 AM IST**.
