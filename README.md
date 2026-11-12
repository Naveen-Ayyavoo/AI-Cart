# AI Cart — Intelligence in Every Click

**An AI-assisted shopping experience where AI interprets what you want, deterministic software enforces your rules, and you remain in control of every purchase.**

[![PayPal AI Hackathon](https://img.shields.io/badge/PayPal-AI%20Hackathon-blue)](https://paypalaihackathon.devpost.com/)
[![Python](https://img.shields.io/badge/Python-3.14-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.1-green)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**AI Cart combines Google Gemini, Channel3 product discovery, a deterministic Python policy engine, and PayPal Checkout to demonstrate a more controlled approach to AI-assisted commerce.**

**Market:** United States · **Currency:** USD · **Payments:** PayPal Sandbox

---

## 1. The Problem

AI can understand shopping preferences, compare products, and make recommendations. But allowing a probabilistic model to control financial transactions introduces a fundamental trust problem.

An AI shopping agent might misunderstand a requirement, accept manipulated product information, overlook a price change, or initiate a purchase the shopper never intended.

A shopping assistant should not need unrestricted payment authority to be useful.

**The central question behind AI Cart:**

How can shoppers delegate shopping research to AI without delegating unrestricted control over their money?

## 2. The Solution

AI Cart separates AI reasoning from financial execution.

Gemini interprets the shopper's natural-language request and helps construct a structured Purchase Contract. Channel3 provides product catalog evidence. A deterministic Python backend evaluates products against the shopper's requirements and spending limits.

The shopper reviews the resulting purchase proposal and explicitly approves it. PayPal then provides a separate buyer-approval step. Only after the required checks does the backend execute a server-side capture in PayPal Sandbox.

**The governing principle is simple: AI proposes. Deterministic software validates. The shopper authorizes. PayPal executes.**

## 3. How It Works

### The shopper journey

1. **Describe what you need.** The shopper enters a natural-language request, including product preferences, budget and exclusions.

2. **Generate a Purchase Contract.** Google Gemini interprets the request into structured requirements. The resulting contract starts as a draft.

3. **Review and confirm.** The shopper reviews and confirms the contract. Confirmation locks the shopping requirements; it does not authorize payment.

4. **Discover products.** AI Cart queries Channel3 and retrieves product information, including available pricing, merchant, variant and stock evidence.

5. **Evaluate products.** The deterministic policy engine checks candidate products against budget, currency, availability, category compatibility, required specifications and excluded terms.

6. **Review the purchase proposal.** The shopper selects an eligible product and reviews the proposal, including its itemized cost information and disclosed demo payee.

7. **Give explicit purchase approval.** AI Cart binds approval to the exact purchase parameters and generates a time-limited, single-use approval.

8. **Approve through PayPal.** The shopper proceeds to PayPal's hosted Sandbox checkout and separately approves the payment.

9. **Revalidate and capture.** On return, the backend independently retrieves the PayPal order and validates the payee, amount, currency and cart fingerprint before server-side capture.

10. **Reconcile the transaction.** Verified PayPal webhook events update the payment record. The shopper can inspect the resulting transaction and receipt.

## 4. What Makes AI Cart Different

| Component | Responsibility | Authority |
|---|---|---|
| Google Gemini | Interprets shopper intent and generates structured proposals | Advisory only |
| Channel3 | Supplies external product catalog evidence | Discovery only |
| Python Policy Engine | Enforces deterministic purchase rules | Policy authority |
| Approval Manager | Binds shopper approval to exact purchase parameters | Approval validation |
| PayPal Orders v2 | Handles hosted buyer approval and Sandbox payment execution | Payment execution |
| Shopper | Reviews requirements and authorizes the proposed purchase | Human authorization |

### Separation of reasoning and execution

Gemini does not receive payment execution tools, payment credentials or authority to advance transaction states.

Its output is treated as untrusted input. Structured validation and deterministic backend rules independently determine whether a purchase can proceed.

A model-generated recommendation cannot override a mandatory policy failure.

### Deterministic spending controls

The backend evaluates products using explicit rules rather than relying on an LLM's opinion.

Examples include:

- Rejecting products above the confirmed budget.
- Rejecting incompatible product categories and variants.
- Rejecting products that violate excluded terms.
- Treating missing or conflicting critical evidence as unknown or ineligible.
- Preventing preferences from overriding mandatory requirements.

Eligible, uncertain and ineligible products are presented as distinct outcomes.

### Exact financial calculations

All monetary calculations use Python `Decimal`, not binary floating-point arithmetic.

The system maintains a disclosed cost breakdown covering applicable item, shipping, tax and fee amounts. Unconfirmed critical charges prevent final purchase approval.

## 5. Purchase Approval and PayPal Protection

AI Cart treats purchase approval and payment execution as separate trust boundaries.

### Cryptographic purchase binding

Before approval, the backend computes a SHA-256 cart fingerprint over the purchase parameters, including:

- Product and variant identifiers.
- SKU and source merchant.
- Payee identity.
- Quantity and unit price.
- Base amount, shipping, tax and fees.
- Total amount and currency.
- Purchase Contract identity and version.

The approval is bound to this purchase snapshot. Material changes invalidate the approval.

### Single-use approval

Purchase approvals have a 15-minute validity period and are consumed atomically. Expired, altered or previously consumed approvals are rejected.

### Server-side PayPal capture

Before capture, AI Cart retrieves the authoritative PayPal order and revalidates:

- Configured demo payee identity.
- USD currency.
- Exact approved amount.
- Cart fingerprint.

A discrepancy causes the transaction to fail closed rather than proceed with a different purchase.

### Payment integrity

The implementation includes:

- Separate idempotency keys for payment operations.
- Atomic payment-state transitions.
- PayPal webhook signature verification.
- Duplicate webhook handling.
- Protection against approval replay and concurrent capture attempts.
- Server-side payment execution rather than client-side capture.

AI Cart does not collect or store shoppers' raw card details. Buyer authorization takes place through PayPal's hosted checkout experience.

## 6. PayPal and Product Seller Disclosure

**The distinction between product discovery and payment settlement is intentional and important.**

Channel3 supplies product discovery information and identifies the original product source merchant.

However, this hackathon implementation uses a controlled PayPal Sandbox demo merchant for payment execution.

Consequently:

- The PayPal Sandbox transaction settles to the configured AI Cart demo payee.
- The original Channel3 source merchant does not receive the Sandbox payment.
- AI Cart does not claim to complete a live purchase with an arbitrary external retailer.
- The implementation does not provide multi-party payouts, seller onboarding or external retailer order fulfilment.
- All payment execution is confined to PayPal Sandbox. No real money is transferred.

This architecture demonstrates the payment authorization, validation and execution controls without misrepresenting a simulated transaction as a completed retail purchase.

## 7. Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python, Django |
| AI reasoning | Google Gemini API |
| Product discovery | Channel3 API |
| Policy evaluation | Deterministic Python services |
| Financial arithmetic | Python `Decimal` |
| Approval integrity | SHA-256 fingerprinting and single-use approval controls |
| Payment integration | PayPal Orders v2 |
| Payment verification | PayPal webhook signature verification |
| Database | SQLite |
| Frontend | Django templates, HTML, CSS and vanilla JavaScript |
| Code quality | Ruff |
| Testing | Django automated test suite and dedicated verification scripts |

The application is designed to run locally. Its development and testing approach uses free-tier services, PayPal Sandbox and local infrastructure rather than requiring paid cloud infrastructure.

When a provider's free allowance is unavailable or exhausted, the application can use clearly disclosed local demo fixtures. Fixture data must not be mistaken for live product evidence.

## 8. Verification and Engineering Evidence

The repository's latest documented verification record is dated **13 November 2026**.

| Verification | Recorded result |
|---|---:|
| Django automated tests | **227 / 227 passed** |
| Integrated verification pipeline | **7 / 7 gates passed** |
| Shopper journey acceptance checks | **56 / 56 passed** |
| Ruff linting | **0 reported issues** |
| Browser audit | **27 routes across 7 viewport widths** |
| Browser screenshots | **100** |
| Reported console, server-error, contrast and overflow defects in the audited run | **0** |

The browser audit also covered responsive reflow, 200% zoom and forced-colors checks.

The automated test strategy includes positive and negative testing across contract validation, monetary precision, product evidence, spending policies, purchase approval, payment state transitions, webhook verification and adversarial scenarios.

### Security scenarios covered by automated tests

| Scenario | Expected behavior |
|---|---|
| Direct prompt injection | Model output cannot override backend policy |
| Indirect injection through product descriptions | External descriptions have no execution authority |
| Product price changes | Capture is blocked when the approved amount no longer matches |
| Payee or currency tampering | Pre-capture validation rejects mismatches |
| Cart fingerprint alteration | The original approval becomes invalid |
| Approval replay | A consumed approval cannot be reused |
| Concurrent capture requests | Idempotency and atomic transitions prevent duplicate capture |
| Forged webhook | Invalid webhook signatures are rejected |
| Out-of-order webhook events | Payment state cannot regress incorrectly |

These are documented implementation and automated-test results, not a claim of immunity to every possible vulnerability or a substitute for an independent security certification.

## 9. Run AI Cart Locally

### Prerequisites

- Windows 10/11 or another supported Python environment.
- Python installed; **Python 3.14.10 was used for the documented verification run**.
- Git.
- An internet connection for installation and live provider integrations.

### 1. Clone the repository

```powershell
git clone https://github.com/Naveen-Ayyavoo/AI-Cart.git
cd AI-Cart
```

### 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

```powershell
Copy-Item .env.example .env
```

Configure the required credentials in `.env` for the integrations you intend to use:

```ini
DJANGO_SECRET_KEY=your_local_secret_key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL_ROUTINE=your_available_gemini_model
GEMINI_MODEL_COMPLEX=your_available_gemini_model

CHANNEL3_API_KEY=your_channel3_api_key
CHANNEL3_BASE_URL=https://api.trychannel3.com

PAYPAL_CLIENT_ID=your_paypal_sandbox_client_id
PAYPAL_CLIENT_SECRET=your_paypal_sandbox_client_secret
PAYPAL_ENVIRONMENT=sandbox
PAYPAL_WEBHOOK_ID=your_paypal_webhook_id
PAYPAL_DEMO_MERCHANT_ID=your_sandbox_merchant_id
```

Use Sandbox credentials only. The repository's `.env.example` contains the full set of supported configuration variables and safe placeholders.

**Never commit `.env` or publish provider credentials.**

### 5. Apply database migrations

```powershell
python manage.py migrate
```

### 6. Run the automated tests

```powershell
python manage.py test
```

### 7. Run the application

```powershell
python manage.py runserver 127.0.0.1:8000
```

Open:

```text
http://127.0.0.1:8000/
```

For live Gemini, Channel3 and PayPal Sandbox functionality, configure the corresponding credentials and provider-side accounts. Where a provider is unavailable, clearly labeled demo fixtures may be used instead.

## 10. Project Scope and Limitations

AI Cart is a hackathon prototype demonstrating controlled AI-assisted shopping and a separately governed payment lifecycle.

Its current scope is deliberately bounded:

- US market and USD transactions.
- PayPal Sandbox only; no production payment processing.
- Product discovery through Channel3.
- A controlled demo payee rather than arbitrary external merchant settlement.
- No seller payouts, multi-party settlement or retailer fulfilment.
- No claim that catalog prices or stock remain valid indefinitely.
- No representation of demo fixtures as live product data.

These boundaries are part of the product's trust model, not capabilities that should be inferred from the demonstration.

## 11. Engineering Documentation

The repository contains supporting documentation for the implementation and verification:

| Document | Purpose |
|---|---|
| [System Architecture Overview](docs/architecture/SYSTEM_OVERVIEW.md) | Components, responsibilities and trust boundaries |
| [Threat Model](docs/security/THREAT_MODEL.md) | Threat analysis and defensive controls |
| [Test Strategy](docs/quality/TEST_STRATEGY.md) | Unit, integration, security and end-to-end testing |
| [Zero-Spend Policy](docs/decisions/ADR-0004-ZERO-SPEND-POLICY.md) | Free-tier and cost-control requirements |
| [Task Gates and Roadmap](TASK_GATES.md) | Implementation phases and acceptance criteria |
| [Current Status](docs/planning/CURRENT_STATUS.md) | Latest documented verification and project status |
| [Engineering Handoff](docs/planning/HANDOFF.md) | Detailed implementation and verification history |
| [Agent Operating Guide](AGENTS.md) | Architectural invariants and engineering rules |

## 12. License

AI Cart is released under the [MIT License](LICENSE).

---

**AI Cart — Intelligence in Every Click**

**AI proposes. Deterministic software governs. The shopper stays in control.**# AI Cart — Intelligence in Every Click

**An AI-assisted shopping experience where AI interprets what you want, deterministic software enforces your rules, and you remain in control of every purchase.**

[![PayPal AI Hackathon](https://img.shields.io/badge/PayPal-AI%20Hackathon-blue)](https://paypalaihackathon.devpost.com/)
[![Python](https://img.shields.io/badge/Python-3.14-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.1-green)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**AI Cart combines Google Gemini, Channel3 product discovery, a deterministic Python policy engine, and PayPal Checkout to demonstrate a more controlled approach to AI-assisted commerce.**

**Market:** United States · **Currency:** USD · **Payments:** PayPal Sandbox

---

## 1. The Problem

AI can understand shopping preferences, compare products, and make recommendations. But allowing a probabilistic model to control financial transactions introduces a fundamental trust problem.

An AI shopping agent might misunderstand a requirement, accept manipulated product information, overlook a price change, or initiate a purchase the shopper never intended.

A shopping assistant should not need unrestricted payment authority to be useful.

**The central question behind AI Cart:**

How can shoppers delegate shopping research to AI without delegating unrestricted control over their money?

## 2. The Solution

AI Cart separates AI reasoning from financial execution.

Gemini interprets the shopper's natural-language request and helps construct a structured Purchase Contract. Channel3 provides product catalog evidence. A deterministic Python backend evaluates products against the shopper's requirements and spending limits.

The shopper reviews the resulting purchase proposal and explicitly approves it. PayPal then provides a separate buyer-approval step. Only after the required checks does the backend execute a server-side capture in PayPal Sandbox.

**The governing principle is simple: AI proposes. Deterministic software validates. The shopper authorizes. PayPal executes.**

## 3. How It Works

### The shopper journey

1. **Describe what you need.** The shopper enters a natural-language request, including product preferences, budget and exclusions.

2. **Generate a Purchase Contract.** Google Gemini interprets the request into structured requirements. The resulting contract starts as a draft.

3. **Review and confirm.** The shopper reviews and confirms the contract. Confirmation locks the shopping requirements; it does not authorize payment.

4. **Discover products.** AI Cart queries Channel3 and retrieves product information, including available pricing, merchant, variant and stock evidence.

5. **Evaluate products.** The deterministic policy engine checks candidate products against budget, currency, availability, category compatibility, required specifications and excluded terms.

6. **Review the purchase proposal.** The shopper selects an eligible product and reviews the proposal, including its itemized cost information and disclosed demo payee.

7. **Give explicit purchase approval.** AI Cart binds approval to the exact purchase parameters and generates a time-limited, single-use approval.

8. **Approve through PayPal.** The shopper proceeds to PayPal's hosted Sandbox checkout and separately approves the payment.

9. **Revalidate and capture.** On return, the backend independently retrieves the PayPal order and validates the payee, amount, currency and cart fingerprint before server-side capture.

10. **Reconcile the transaction.** Verified PayPal webhook events update the payment record. The shopper can inspect the resulting transaction and receipt.

## 4. What Makes AI Cart Different

| Component | Responsibility | Authority |
|---|---|---|
| Google Gemini | Interprets shopper intent and generates structured proposals | Advisory only |
| Channel3 | Supplies external product catalog evidence | Discovery only |
| Python Policy Engine | Enforces deterministic purchase rules | Policy authority |
| Approval Manager | Binds shopper approval to exact purchase parameters | Approval validation |
| PayPal Orders v2 | Handles hosted buyer approval and Sandbox payment execution | Payment execution |
| Shopper | Reviews requirements and authorizes the proposed purchase | Human authorization |

### Separation of reasoning and execution

Gemini does not receive payment execution tools, payment credentials or authority to advance transaction states.

Its output is treated as untrusted input. Structured validation and deterministic backend rules independently determine whether a purchase can proceed.

A model-generated recommendation cannot override a mandatory policy failure.

### Deterministic spending controls

The backend evaluates products using explicit rules rather than relying on an LLM's opinion.

Examples include:

- Rejecting products above the confirmed budget.
- Rejecting incompatible product categories and variants.
- Rejecting products that violate excluded terms.
- Treating missing or conflicting critical evidence as unknown or ineligible.
- Preventing preferences from overriding mandatory requirements.

Eligible, uncertain and ineligible products are presented as distinct outcomes.

### Exact financial calculations

All monetary calculations use Python `Decimal`, not binary floating-point arithmetic.

The system maintains a disclosed cost breakdown covering applicable item, shipping, tax and fee amounts. Unconfirmed critical charges prevent final purchase approval.

## 5. Purchase Approval and PayPal Protection

AI Cart treats purchase approval and payment execution as separate trust boundaries.

### Cryptographic purchase binding

Before approval, the backend computes a SHA-256 cart fingerprint over the purchase parameters, including:

- Product and variant identifiers.
- SKU and source merchant.
- Payee identity.
- Quantity and unit price.
- Base amount, shipping, tax and fees.
- Total amount and currency.
- Purchase Contract identity and version.

The approval is bound to this purchase snapshot. Material changes invalidate the approval.

### Single-use approval

Purchase approvals have a 15-minute validity period and are consumed atomically. Expired, altered or previously consumed approvals are rejected.

### Server-side PayPal capture

Before capture, AI Cart retrieves the authoritative PayPal order and revalidates:

- Configured demo payee identity.
- USD currency.
- Exact approved amount.
- Cart fingerprint.

A discrepancy causes the transaction to fail closed rather than proceed with a different purchase.

### Payment integrity

The implementation includes:

- Separate idempotency keys for payment operations.
- Atomic payment-state transitions.
- PayPal webhook signature verification.
- Duplicate webhook handling.
- Protection against approval replay and concurrent capture attempts.
- Server-side payment execution rather than client-side capture.

AI Cart does not collect or store shoppers' raw card details. Buyer authorization takes place through PayPal's hosted checkout experience.

## 6. PayPal and Product Seller Disclosure

**The distinction between product discovery and payment settlement is intentional and important.**

Channel3 supplies product discovery information and identifies the original product source merchant.

However, this hackathon implementation uses a controlled PayPal Sandbox demo merchant for payment execution.

Consequently:

- The PayPal Sandbox transaction settles to the configured AI Cart demo payee.
- The original Channel3 source merchant does not receive the Sandbox payment.
- AI Cart does not claim to complete a live purchase with an arbitrary external retailer.
- The implementation does not provide multi-party payouts, seller onboarding or external retailer order fulfilment.
- All payment execution is confined to PayPal Sandbox. No real money is transferred.

This architecture demonstrates the payment authorization, validation and execution controls without misrepresenting a simulated transaction as a completed retail purchase.

## 7. Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python, Django |
| AI reasoning | Google Gemini API |
| Product discovery | Channel3 API |
| Policy evaluation | Deterministic Python services |
| Financial arithmetic | Python `Decimal` |
| Approval integrity | SHA-256 fingerprinting and single-use approval controls |
| Payment integration | PayPal Orders v2 |
| Payment verification | PayPal webhook signature verification |
| Database | SQLite |
| Frontend | Django templates, HTML, CSS and vanilla JavaScript |
| Code quality | Ruff |
| Testing | Django automated test suite and dedicated verification scripts |

The application is designed to run locally. Its development and testing approach uses free-tier services, PayPal Sandbox and local infrastructure rather than requiring paid cloud infrastructure.

When a provider's free allowance is unavailable or exhausted, the application can use clearly disclosed local demo fixtures. Fixture data must not be mistaken for live product evidence.

## 8. Verification and Engineering Evidence

The repository's latest documented verification record is dated **13 November 2026**.

| Verification | Recorded result |
|---|---:|
| Django automated tests | **227 / 227 passed** |
| Integrated verification pipeline | **7 / 7 gates passed** |
| Shopper journey acceptance checks | **56 / 56 passed** |
| Ruff linting | **0 reported issues** |
| Browser audit | **27 routes across 7 viewport widths** |
| Browser screenshots | **100** |
| Reported console, server-error, contrast and overflow defects in the audited run | **0** |

The browser audit also covered responsive reflow, 200% zoom and forced-colors checks.

The automated test strategy includes positive and negative testing across contract validation, monetary precision, product evidence, spending policies, purchase approval, payment state transitions, webhook verification and adversarial scenarios.

### Security scenarios covered by automated tests

| Scenario | Expected behavior |
|---|---|
| Direct prompt injection | Model output cannot override backend policy |
| Indirect injection through product descriptions | External descriptions have no execution authority |
| Product price changes | Capture is blocked when the approved amount no longer matches |
| Payee or currency tampering | Pre-capture validation rejects mismatches |
| Cart fingerprint alteration | The original approval becomes invalid |
| Approval replay | A consumed approval cannot be reused |
| Concurrent capture requests | Idempotency and atomic transitions prevent duplicate capture |
| Forged webhook | Invalid webhook signatures are rejected |
| Out-of-order webhook events | Payment state cannot regress incorrectly |

These are documented implementation and automated-test results, not a claim of immunity to every possible vulnerability or a substitute for an independent security certification.

## 9. Run AI Cart Locally

### Prerequisites

- Windows 10/11 or another supported Python environment.
- Python installed; **Python 3.14.10 was used for the documented verification run**.
- Git.
- An internet connection for installation and live provider integrations.

### 1. Clone the repository

```powershell
git clone https://github.com/Naveen-Ayyavoo/AI-Cart.git
cd AI-Cart
```

### 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

```powershell
Copy-Item .env.example .env
```

Configure the required credentials in `.env` for the integrations you intend to use:

```ini
DJANGO_SECRET_KEY=your_local_secret_key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL_ROUTINE=your_available_gemini_model
GEMINI_MODEL_COMPLEX=your_available_gemini_model

CHANNEL3_API_KEY=your_channel3_api_key
CHANNEL3_BASE_URL=https://api.trychannel3.com

PAYPAL_CLIENT_ID=your_paypal_sandbox_client_id
PAYPAL_CLIENT_SECRET=your_paypal_sandbox_client_secret
PAYPAL_ENVIRONMENT=sandbox
PAYPAL_WEBHOOK_ID=your_paypal_webhook_id
PAYPAL_DEMO_MERCHANT_ID=your_sandbox_merchant_id
```

Use Sandbox credentials only. The repository's `.env.example` contains the full set of supported configuration variables and safe placeholders.

**Never commit `.env` or publish provider credentials.**

### 5. Apply database migrations

```powershell
python manage.py migrate
```

### 6. Run the automated tests

```powershell
python manage.py test
```

### 7. Run the application

```powershell
python manage.py runserver 127.0.0.1:8000
```

Open:

```text
http://127.0.0.1:8000/
```

For live Gemini, Channel3 and PayPal Sandbox functionality, configure the corresponding credentials and provider-side accounts. Where a provider is unavailable, clearly labeled demo fixtures may be used instead.

## 10. Project Scope and Limitations

AI Cart is a hackathon prototype demonstrating controlled AI-assisted shopping and a separately governed payment lifecycle.

Its current scope is deliberately bounded:

- US market and USD transactions.
- PayPal Sandbox only; no production payment processing.
- Product discovery through Channel3.
- A controlled demo payee rather than arbitrary external merchant settlement.
- No seller payouts, multi-party settlement or retailer fulfilment.
- No claim that catalog prices or stock remain valid indefinitely.
- No representation of demo fixtures as live product data.

These boundaries are part of the product's trust model, not capabilities that should be inferred from the demonstration.

## 11. Engineering Documentation

The repository contains supporting documentation for the implementation and verification:

| Document | Purpose |
|---|---|
| [System Architecture Overview](docs/architecture/SYSTEM_OVERVIEW.md) | Components, responsibilities and trust boundaries |
| [Threat Model](docs/security/THREAT_MODEL.md) | Threat analysis and defensive controls |
| [Test Strategy](docs/quality/TEST_STRATEGY.md) | Unit, integration, security and end-to-end testing |
| [Zero-Spend Policy](docs/decisions/ADR-0004-ZERO-SPEND-POLICY.md) | Free-tier and cost-control requirements |
| [Task Gates and Roadmap](TASK_GATES.md) | Implementation phases and acceptance criteria |
| [Current Status](docs/planning/CURRENT_STATUS.md) | Latest documented verification and project status |
| [Engineering Handoff](docs/planning/HANDOFF.md) | Detailed implementation and verification history |
| [Agent Operating Guide](AGENTS.md) | Architectural invariants and engineering rules |

## 12. License

AI Cart is released under the [MIT License](LICENSE).

---

**AI Cart — Intelligence in Every Click**

**AI proposes. Deterministic software governs. The shopper stays in control.**
