# TrustCart Task Gates & Phase Roadmap

This document defines the strict, phase-gated execution plan for TrustCart. No phase may commence until its prerequisites are satisfied and the prior phase gate is formally signed off with evidence.

---

## Phase Overview

| Phase | Title | Status | Gate Status |
| :--- | :--- | :--- | :--- |
| **P0** | Development environment and engineering workspace | **IN PROGRESS** | Pending Review |
| **P1** | Architecture and application foundation | **PENDING** | Not Started |
| **P2** | Purchase Contract creation and confirmation | **PENDING** | Not Started |
| **P3** | Channel3 product search, lookup and evidence provenance | **PENDING** | Not Started |
| **P4** | Deterministic policy and trust evaluation | **PENDING** | Not Started |
| **P5** | Exact, immutable, one-use purchase approval | **PENDING** | Not Started |
| **P6** | PayPal Sandbox order, buyer approval, capture and reconciliation | **PENDING** | Not Started |
| **P7** | Security, failure injection and end-to-end testing | **PENDING** | Not Started |
| **P8** | Deployment, documentation and hackathon submission | **PENDING** | Not Started |

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

---

### Phase P2: Purchase Contract Creation & Confirmation
- **Purpose**: Implement the user intent intake pipeline where Gemini parses shopper requests into a structured, validated, user-confirmed Purchase Contract within verified Free Tier quotas.
- **Scope**: Purchase Contract domain model / dataclass, Gemini API client with strict structured output schema, validation service, contract confirmation UI, model allocation routing (Flash Lite for shopping requests; Gemini 3.8 Flash for complex reasoning), quota tracking, and fail-safe fallback.
- **Dependencies**: P1 signed off, Gemini API key configured on verified Free Tier (dashboard quotas: Gemini 3.5 Flash Lite 15 RPM/500 RPD, Gemini 3.1 Flash Lite 15 RPM/500 RPD, Gemini 3.8 Flash 5 RPM/20 RPD; actual API model identifiers verified before implementation; zero billing account attached).
- **Deliverables**: Contract data models (budget, category, required specs, excluded terms), Gemini prompt template and schema parser, contract view and confirmation template, quota exhaustion handler and labeled demo fixtures.
- **Required Tests**: Schema validation tests, Gemini mock response parser tests, malformed JSON recovery tests, user confirmation state transition tests, quota exhaustion fail-safe tests.
- **Security & Cost Checks**: Strict schema validation rejecting unparsed keys, indirect prompt injection sanitization, contract immutability; verification that Gemini API project has no billing account attached; models displaying zero quotas treated as unavailable; zero use of paid Search grounding or paid fallbacks; sensitive credentials never transmitted.
- **Explicit Completion Gate**: Shopper prompt generates structured contract; invalid prompts fail closed; quota exhaustion cleanly degrades to labeled demo fixtures; user confirms contract before search; zero API expenditure incurred.

---

### Phase P3: Channel3 Product Search, Lookup & Evidence Provenance
- **Purpose**: Integrate Channel3 API to discover real product offerings, preserving evidence provenance, pricing, and stock status within the verified 1,000 credits/month free tier allowance and 1,000 bonus credits.
- **Scope**: Channel3 API client service, credit budget manager (tracking monthly allowance and bonus credits separately; bonus consumed only after monthly credits), product evidence dataclasses, caching layer by product ID with freshness TTL, provenance capture (source merchant, retrieval timestamp, currency, variant ID).
- **Dependencies**: P2 signed off, Channel3 API credentials on verified free tier (1,000 monthly credits resetting on the 1st + 1,000 one-time bonus credits).
- **Deliverables**: `Channel3Client` service with usage tracking, product evidence models, offline mock fixtures for testing, catalog search and detail views, quota-exhausted status handler.
- **Required Tests**: Channel3 client unit tests with mock responses, credit tracking unit tests, network timeout / failure tests, price parser tests (confirming Decimal conversion), stale cache eviction tests, quota exhaustion degradation tests.
- **Security & Cost Checks**: Ingestion sanitization of product titles/descriptions; fail-closed handling of items with missing/ambiguous pricing; credit consumption counter enforced to prevent exceeding free allowance; bonus credits never represented as recurring allowance; zero paid tier upgrades or credit purchases.
- **Explicit Completion Gate**: Verified retrieval of real product data within free allowance, caching by product ID verified, accurate Decimal conversion, complete provenance recording, safe degradation on quota exhaustion, and zero financial spend.

---

### Phase P4: Deterministic Policy & Trust Evaluation
- **Purpose**: Implement the deterministic rule engine that evaluates candidate products against the Purchase Contract and hard shopping policies with zero external API costs.
- **Scope**: Policy engine evaluating budget limits, shipping constraints, merchant reputation rules, variant matching, and price consistency entirely in local Python code.
- **Dependencies**: P3 signed off.
- **Deliverables**: Policy evaluation service, policy violation types, explainable evaluation report generator.
- **Required Tests**: Budget boundary unit tests (exact match, \$0.01 over budget fails), disallowed attribute tests, conflicting evidence tests, negative tests on malformed products.
- **Security & Cost Checks**: Complete decoupling from LLM reasoning: policy logic is 100% deterministic local Python code; zero external API or cloud compute expenses.
- **Explicit Completion Gate**: Policy engine accurately passes conforming items and deterministically rejects non-conforming items with clear, auditable explanations at zero operational cost.

---

### Phase P5: Exact, Immutable, One-Use Purchase Approval
- **Purpose**: Generate a cryptographically bound, time-limited, single-use purchase proposal requiring explicit buyer confirmation using local cryptographic primitives.
- **Scope**: Proposed purchase generator, cryptographic cart fingerprinting (SHA-256 over product, variant, quantity, unit price, total, payee, currency), approval token lifecycle manager (creation, expiry TTL, atomic consumption).
- **Dependencies**: P4 signed off.
- **Deliverables**: Approval domain model, token generator and verifier, proposal presentation UI, approval action handler.
- **Required Tests**: Token tamper tests (altering 1 cent invalidates token), TTL expiration tests, double-consumption / replay prevention tests, concurrent approval tests.
- **Security & Cost Checks**: Approval cannot be consumed more than once; cart modification voids existing approval; tokens expire within 15 minutes; zero external service or token licensing fees.
- **Explicit Completion Gate**: Positive and negative approval tests pass; approval strictly bound to fingerprint; single-use atomic consumption verified under test with zero cost.

---

### Phase P6: PayPal Sandbox Order, Buyer Approval, Capture & Reconciliation
- **Purpose**: Execute PayPal Sandbox payment lifecycle: order creation, buyer redirect/approval, server-side capture, and webhook reconciliation strictly in Sandbox mode.
- **Scope**: PayPal Orders v2 API client, order creation with idempotency keys (`PayPal-Request-Id`), buyer approval redirect handler, server-side capture service, webhook signature verification, mock sandbox accounts only.
- **Dependencies**: P5 signed off, PayPal Sandbox credentials.
- **Deliverables**: `PayPalClient` service configured exclusively for Sandbox (`api-m.sandbox.paypal.com`), order and transaction models, checkout UI flow, webhook handler endpoint, demo merchant disclosure.
- **Required Tests**: Order creation mock tests, pre-capture revalidation tests, idempotency duplicate call tests, simulated webhook signature verification tests, negative payment failure tests.
- **Security & Cost Checks**: Server-side capture only; pre-capture deterministic revalidation; webhook signature verified; zero sensitive card data touched; demo payee clearly disclosed; strict verification that live credentials and live endpoints are never used; zero real financial settlement or processing fees.
- **Explicit Completion Gate**: Full Sandbox checkout flow completes; server captures payment in Sandbox; duplicate capture attempts rejected; webhook verified; zero real money moved or charged.

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

---

### Phase P8: Deployment, Documentation & Hackathon Submission
- **Purpose**: Finalize production-ready documentation, demo scripts, video recording assets, and submission package for the PayPal AI Hackathon using zero-spend hosting.
- **Scope**: Final documentation polish, demo walk-through script, README updates, zero-cost asset packaging (GitHub public repo, free YouTube video, local demonstration).
- **Dependencies**: P7 signed off.
- **Deliverables**: Final submission README, demo script, architecture diagrams, verified submission checklist, zero-spend audit log.
- **Required Tests**: Clean checkout smoke test on fresh environment using local server.
- **Security & Cost Checks**: Final audit confirming no credentials or secrets exist in repository or commit history; audit verifying that no paid cloud hosting, paid domain, or paid service was activated.
- **Explicit Completion Gate**: Workspace ready for hackathon review, demo reproducible from clean clone on localhost, all criteria met with verified total financial expenditure of exactly $0.00.

