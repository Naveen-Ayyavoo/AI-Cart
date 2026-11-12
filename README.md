# AI Cart

> **Intelligence in Every Click**<br>
> *Autonomous Shopping Assistant — PayPal AI Hackathon Submission (US Market / USD)*<br>
> *(Formerly developed under the engineering working name **TrustCart**)*

AI Cart enables shoppers to delegate tedious shopping research to an autonomous AI assistant while maintaining strict, deterministic authority and cryptographic safety over financial commitments.

---

## The Problem & Architecture

Autonomous AI agents often suffer from a fundamental flaw: **hallucinated transactions and unbounded agency**. Allowing a Large Language Model (LLM) to directly hold credentials, authorize charges, or interact with payment gateways introduces severe security risks: prompt injection attacks, price hallucination, unauthorized vendor redirection, and double-charging.

AI Cart solves this through a **dual-boundary architecture**:
1. **Advisory AI Boundary (Google Gemini)**: Analyzes natural language shopper requests, extracts structured parameters, evaluates options, and compiles proposals. The AI has **zero authority** over state transitions, approvals, or payments.
2. **Deterministic Backend Authority (Python / Django)**: Owns contract validation, deterministic spending policy evaluation, cryptographic cart fingerprinting, single-use approval binding, and server-side PayPal Sandbox capture.

```
+-----------------------------------------------------------------------------------+
|                            UNTRUSTED REASONING BOUNDARY                           |
|  Shopper Prompt ----> [ Google Gemini AI ] ----> Structured Purchase Contract     |
|                               (Advisory Only; State = DRAFT)                      |
+-----------------------------------------------------------------------------------+
                                        | (Shopper Review & Lock)
+-----------------------------------------------------------------------------------+
|                        DETERMINISTIC BACKEND AUTHORITY                            |
|                                                                                   |
|  [ Channel3 Catalog ] ----> Product Evidence (Provenance, SKU, Stock, Decimal)    |
|                                       |                                           |
|  [ Policy Engine ]    ----> Hard Spending Policy Evaluation & Audit Log           |
|                                       |                                           |
|  [ Proposal Engine ]  ----> SHA-256 Cart Fingerprint (15 terms)                   |
|                                       |                                           |
|  [ Shopper Approval ] ----> Cryptographic Single-Use Approval Token (15-min TTL) |
|                                       |                                           |
|  [ PayPal Orders v2 ] ----> Server-Side Order Creation (intent: CAPTURE)          |
+-----------------------------------------------------------------------------------+
                                        | (Redirect)
+-----------------------------------------------------------------------------------+
|                         PAYPAL BUYER APPROVAL BOUNDARY                            |
|       Shopper logs into PayPal Sandbox & explicitly approves payment              |
+-----------------------------------------------------------------------------------+
                                        | (Return Callback)
+-----------------------------------------------------------------------------------+
|                       SERVER-SIDE PRE-CAPTURE REVALIDATION                        |
|  1. Authoritative PayPal GET /v2/checkout/orders/{id}                             |
|  2. Revalidate: Payee == Demo Payee (PU7K3F65AAQ8U)                              |
|  3. Revalidate: Currency == USD & Amount == Approved Snapshot (Exact Decimal)     |
|  4. Revalidate: custom_id == Cart Fingerprint                                     |
|  5. Execute: Server-Side POST /v2/checkout/orders/{id}/capture                    |
|  6. Webhook: Cryptographic Signature Verification & Idempotent Audit              |
+-----------------------------------------------------------------------------------+
```

---

## Non-Negotiable Invariants

AI Cart strictly enforces these architectural invariants:

1. **Untrusted Reasoning Boundary**: Gemini is strictly advisory. It generates proposals, but can never advance state, bypass policies, or trigger payments.
2. **Deterministic Backend Authority**: Python backend code strictly governs contracts, policies, state machines, approvals, and payment execution.
3. **Exact Monetary Calculations**: All price and currency arithmetic uses Python `Decimal`. Binary floating-point (`float`) is strictly prohibited for monetary values.
4. **Cryptographic Cart Fingerprint & Approval Binding**: An approval binds cryptographically to exact parameters: `product_id`, `variant_id`, `sku`, `source_merchant`, `payee_id`, `quantity`, `unit_price`, `base_amount`, `shipping_amount`, `tax_amount`, `fee_amount`, `total_amount`, `currency`, `contract_id`, and `contract_version`. Any discrepancy invalidates the approval token.
5. **Single-Use, Time-Limited Approvals**: Approvals have an explicit 15-minute TTL and can be consumed exactly once via atomic database locking.
6. **Two-Stage Approval**: AI Cart internal approval and PayPal buyer approval are separate sequential gates.
7. **Server-Side PayPal Capture**: Payment capture occurs exclusively server-side after deterministic revalidation. The browser or client cannot capture funds.
8. **Idempotency & Webhook Signature Verification**: Create-order and capture requests persist and reuse distinct idempotency keys. All incoming PayPal webhook notifications verify cryptographic signatures before processing.
9. **Controlled Demo Merchant Disclosure**: PayPal Sandbox transactions settle against a controlled, clearly disclosed demo merchant account (`PU7K3F65AAQ8U`), never pretending to execute arbitrary external retail checkout.
10. **Zero Additional Spend ($0.00)**: Operates 100% within verified free allowances (Gemini Free Tier, Channel3 free tier allowance, PayPal Sandbox, local SQLite). On quota exhaustion, the system fails closed or gracefully degrades to clearly disclosed local fixtures without misrepresenting them as live data.

---

## Quickstart & Installation (Windows PowerShell)

### Prerequisites
- **Operating System**: Windows 10/11 (64-bit)
- **Python**: Python 3.10+ (tested on Python 3.14.10)
- **PowerShell**: Windows PowerShell 5.1 or PowerShell 7+
- **Git**: Installed and available in PATH

### 1. Clone & Set Up Virtual Environment

```powershell
# Navigate to project directory
cd D:\TrustCart

# Verify Python version
python --version

# Create virtual environment (if not already present)
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1
```

### 2. Configure Environment Variables

```powershell
# Copy the environment template
Copy-Item .env.example .env
```

Open `.env` and configure your credentials. Safe template defaults are provided in `.env.example`:
```ini
DJANGO_SECRET_KEY=change-me-to-a-secure-random-secret-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

# Google Gemini API (Free tier from Google AI Studio)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL_ROUTINE=gemini-3.5-flash-lite
GEMINI_MODEL_COMPLEX=gemini-3.8-flash

# Channel3 Catalog API (Free allowance)
CHANNEL3_API_KEY=your_channel3_api_key_here
CHANNEL3_BASE_URL=https://api.trychannel3.com

# PayPal Sandbox API (US Sandbox Merchant)
PAYPAL_CLIENT_ID=your_paypal_sandbox_client_id_here
PAYPAL_CLIENT_SECRET=your_paypal_sandbox_client_secret_here
PAYPAL_ENVIRONMENT=sandbox
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
PAYPAL_WEBHOOK_ID=your_paypal_webhook_id_here
PAYPAL_DEMO_MERCHANT_ID=PU7K3F65AAQ8U
```

*(Note: If API keys are omitted or quotas are exhausted, AI Cart runs seamlessly in offline demo mode using labeled local fixtures.)*

### 3. Run Migrations

```powershell
python manage.py migrate
```

### 4. Run the Automated Test Suite

AI Cart includes **227 automated unit, integration, and adversarial tests** with 100% pass rate:

```powershell
python manage.py test
```

Run code quality and system checks:
```powershell
# Run Ruff linter
.\.venv\Scripts\ruff.exe check .

# Run Django system checks
python manage.py check
```

### 5. Launch the Development Server

```powershell
python manage.py runserver 127.0.0.1:8000
```

Open your browser to: **`http://127.0.0.1:8000/`**

---

## Step-by-Step Interactive Demo Walkthrough

Judges and evaluators can experience the full AI Cart lifecycle following this step-by-step walkthrough:

### Step 1: Prompt Intake & AI Contract Extraction
- Navigate to `http://127.0.0.1:8000/contracts/`
- Enter a natural language request, for example:
  > *"I need an ergonomic mechanical keyboard for typing under $100. Must have tactile switches."*
- Click **"Analyze & Create Draft Contract"**.
- Gemini extracts structured constraints (category, description, max budget `$100.00`, currency `USD`, quantity `1`).
- The contract is initialized in `DRAFT` state. The AI has **no authority** to confirm or execute it.

### Step 2: Contract Review & Explicit Lock
- Review the parsed contract terms.
- Click **"Confirm & Lock Contract"**.
- The contract transitions from `DRAFT` to `CONFIRMED`. It is now immutable.

### Step 3: Product Evidence Discovery
- The interface queries Channel3 for matching products.
- Product evidence preserves provenance: merchant name, SKU, variant ID, inventory availability, and price parsed strictly into Python `Decimal`.
- Inspect candidate products and select the target item.

### Step 4: Deterministic Policy Evaluation
- The backend evaluates the candidate item against spending rules:
  - Total price <= max budget ($100.00).
  - Currency strictly matches USD.
  - Merchant is verified.
- An immutable `PolicyEvaluationReport` is generated with `PASSED` verdict and timestamped audit logs.

### Step 5: Proposal Assembly & Approval Binding
- A `PurchaseProposal` is generated with detailed cost breakdown (base, tax, shipping, total).
- The system computes an immutable SHA-256 **Cart Fingerprint** over 15 parameters.
- Click **"Approve Purchase Proposal"**.
- The user grants explicit single-use approval, generating a time-limited `PurchaseApproval` token (15-minute TTL).

### Step 6: PayPal Sandbox Checkout Initiation
- Click **"Proceed to PayPal Sandbox Checkout"**.
- AI Cart initiates an Orders v2 order via `POST https://api-m.sandbox.paypal.com/v2/checkout/orders`:
  - `intent: "CAPTURE"`
  - `payee.merchant_id: "PU7K3F65AAQ8U"` (controlled demo merchant)
  - `custom_id: <SHA-256 Cart Fingerprint>`
- The `PurchaseApproval` is atomically consumed (`CONSUMED` state). It cannot be reused.
- The browser redirects to PayPal's secure Sandbox approval page (`sandbox.paypal.com/checkoutnow`).

### Step 7: PayPal Buyer Approval & Server-Side Capture
- Log into PayPal Sandbox using your personal sandbox buyer account.
- Complete the buyer review and click **"Complete Purchase"**.
- PayPal redirects to AI Cart's return handler: `/payments/checkout/return/`.
- **Pre-Capture Revalidation**: Before capturing, AI Cart queries PayPal `GET /v2/checkout/orders/{id}` and strictly checks:
  - Payee matches demo merchant `PU7K3F65AAQ8U`.
  - Amount matches the approved proposal down to the cent.
  - Currency is USD.
  - Cart fingerprint matches.
- Only upon passing all checks does AI Cart execute server-side capture: `POST /v2/checkout/orders/{id}/capture`.
- Order transitions to `COMPLETED`. An authentic receipt is rendered showing transaction ID, capture ID, and cryptographic fingerprint.

### Step 8: Webhook Replay & Verification
- PayPal sends asynchronous `PAYMENT.CAPTURE.COMPLETED` webhook notifications.
- AI Cart verifies webhook authenticity using PayPal's public cert chain (`POST /v1/notifications/verify-webhook-signature`).
- Duplicate deliveries are recognized idempotently without double-capture.

---

## Adversarial & Security Defenses

AI Cart includes automated tests verifying defense against real-world adversarial attacks:

| Attack Scenario | Test Reference | Defense Mechanism |
|---|---|---|
| **Prompt Injection Attack** | `test_adversarial_security.py::test_prompt_injection_extra_keys_rejected` | Strict Pydantic schema validation (`extra="forbid"`). LLM cannot inject extra keys or permissions. |
| **Secret Exfiltration Attempt** | `test_adversarial_security.py::test_prompt_injection_secret_exfiltration_prevented` | Shopper prompt cannot extract server secrets; extra fields in LLM responses fail closed. |
| **Prompt Tag Escape** | `test_adversarial_security.py::test_prompt_encapsulation_in_shopper_prompt_tags` | User prompts are sanitized and strictly encapsulated in `<shopper_prompt>` tags. |
| **Policy Bypass Attempt** | `test_adversarial_security.py::test_direct_prompt_injection_in_raw_prompt_cannot_bypass_policy_engine` | Adversarial commands in contract prompt text have zero authority over deterministic PolicyEngine. |
| **Indirect Product Injection** | `test_adversarial_and_e2e.py::test_indirect_prompt_injection_in_product_evidence_has_zero_execution_authority` | Untrusted seller descriptions/evidence have zero execution authority; cannot alter payee or bypass budget. |
| **Oversized Prompt Attack** | `test_adversarial_security.py::test_oversized_prompt_rejected` | Prompt input limited to 2,000 characters; prevents context-stuffing denial of service. |
| **Currency Tampering** | `test_adversarial_security.py::test_non_usd_currency_rejected` | Non-USD currencies (`EUR`, `GBP`, `BTC`) rejected immediately with validation errors. |
| **Price Tampering (+$0.01 / -$0.01)** | `test_adversarial_and_e2e.py::test_price_fluctuation_increase_aborts_capture` | Pre-capture check revalidates remote PayPal amount against approved snapshot. Even a $0.01 discrepancy aborts capture. |
| **Currency Mismatch** | `test_adversarial_and_e2e.py::test_pre_capture_currency_mismatch_fails_closed` | Pre-capture revalidation strictly rejects non-USD remote currency and marks order FAILED. |
| **Payee Hijacking Attack** | `test_adversarial_and_e2e.py::test_payee_tampering_aborts_capture` | Captures fail closed if remote payee does not match controlled demo merchant ID. |
| **Cart Fingerprint Forgery** | `test_adversarial_and_e2e.py::test_cart_fingerprint_tampering_aborts_capture` | Altering custom_id or cart terms invalidates approval and aborts payment. |
| **Approval Token Replay** | `test_adversarial_and_e2e.py::test_approval_token_replay_rejected` | Consumed approval token cannot initiate a second checkout. |
| **Concurrent Capture Race Condition** | `test_adversarial_and_e2e.py::test_concurrent_capture_idempotency` | Idempotency keys and atomic DB locking prevent duplicate captures. |
| **Out-of-Order Webhook Delivery** | `test_adversarial_and_e2e.py::test_out_of_order_webhook_delivery_does_not_regress_completed_order` | `CHECKOUT.ORDER.APPROVED` arriving after `COMPLETED` cannot regress order status. |

---

## Controlled PayPal Sandbox Merchant Disclosure

Per hackathon guidelines and competition invariants:
- **Sandbox Environment Only**: All transactions are executed strictly against `https://api-m.sandbox.paypal.com`.
- **Demo Payee Identity**: Payments settle exclusively into the controlled US Business Sandbox test account:
  - **Account Name**: AI Cart US Demo Store (formerly TrustCart)
  - **Merchant ID**: `PU7K3F65AAQ8U`
  - **Email**: `sb-k43uvc49363066@business.example.com`
- **Integrity Guarantee**: AI Cart never pretends to execute settlement against arbitrary external retailers. Payment capture is strictly scoped to the disclosed demo merchant.

---

## 3-Minute Video Demo Script & Outline (8-Scene Walkthrough)

This structured outline guides the 3-minute hackathon demonstration video, demonstrating live Channel3 evidence discovery, deterministic policy enforcement, unsafe-case rejection, single-use cryptographic approval, and PayPal Sandbox capture:

```text
[0:00 - 0:25] Scene 1: The Problem — Unbounded Agency Destroys Trust
- Screen: Title card & architectural comparison diagram: Probabilistic LLM holding payment credentials vs AI Cart Dual Boundary.
- Visual: "Autonomous shopping is broken. Giving an LLM direct payment authority leads to hallucinated prices, prompt injections, and rogue checkouts."
- Narration: "Autonomous AI shopping agents are powerful, but giving an LLM direct access to your credit card or payment execution is dangerous. Probabilistic models hallucinate prices, succumb to prompt injections, and cannot be trusted with financial authority. Welcome to AI Cart: Intelligence in Every Click, the trustworthy autonomous shopping assistant powered by PayPal."

[0:25 - 0:45] Scene 2: Shopping Request Intake
- Screen: AI Cart homepage (`http://127.0.0.1:8000/`).
- Visual: User enters prompt: "Find me an ergonomic mechanical keyboard under $100. Must have hot-swappable switches and USB-C. Exclude Blue switches and refurbished items."
- Narration: "The shopper delegates intent by defining the item, exact budget ceiling, and non-negotiable constraints. Shopper input is strictly length-capped and isolated."

[0:45 - 1:10] Scene 3: Advisory AI Intake -> Locked Purchase Contract
- Screen: Contract Review screen (`/contracts/<id>/review/`).
- Visual: Google Gemini extracts structured requirements (Category: Electronics, Max Budget: $100.00 USD, Required Specs, Excluded Terms). Status is DRAFT.
- Narration: "Google Gemini acts strictly as an advisory reasoning engine with zero execution authority. It parses intent into a structured Purchase Contract. The shopper reviews the extracted parameters and explicitly clicks 'Lock & Confirm Contract'."

[1:10 - 1:30] Scene 4: Evidence Discovery & Deterministic Policy Check
- Screen: Candidate Products & Policy Evaluation Dashboard (`/policies/evaluate/<id>/`).
- Visual: Live Channel3 product evidence retrieved with full SKU provenance and Decimal pricing. PolicyEngine audit table displays green checkmarks for conforming items.
- Narration: "AI Cart retrieves product evidence via Channel3 with complete SKU and provenance tracking. Then, our deterministic Python backend evaluates hard spending policies with exact Decimal math—zero float arithmetic."

[1:30 - 1:55] Scene 5: The Unsafe Case — Deterministic Policy Blocks Violation
- Screen: Policy Evaluation Dashboard showing the Amber/Red "Ineligible" and "Uncertain" cards.
- Visual: Highlight an item with price $105.00 (+$5.00 over budget) or containing excluded "Blue switches" marked REJECTED with explicit rule failure explanation.
- Narration: "Here is the critical difference: when an item exceeds the budget by even one cent, or contains an excluded term, AI Cart's deterministic engine fails closed instantly. The AI cannot override this policy. Dangerous purchases are stopped before approval."

[1:55 - 2:20] Scene 6: Cryptographic Approval Binding (SHA-256 Fingerprint)
- Screen: Purchase Proposal screen (`/orders/proposals/<id>/`).
- Visual: Itemized payable breakdown ($49.99 base + shipping + taxes). Prominent 15-parameter SHA-256 cart fingerprint badge.
- Narration: "AI Cart binds the proposal to a canonical 15-parameter SHA-256 cart fingerprint. The shopper inspects the disclosed demo payee and grants a single-use approval token with a strict 15-minute time-to-live."

[2:20 - 2:45] Scene 7: PayPal Buyer Approval & Server-Side Capture
- Screen: PayPal Sandbox portal login (`sandbox.paypal.com`) -> Click "Complete Purchase" -> Redirect to `/payments/checkout/return/` -> Order Receipt (`receipt.html`).
- Visual: Buyer logs in, reviews approved total. Return view performs pre-capture revalidation (payee, currency, amount, cart fingerprint) before server-side capture. Status transitions to COMPLETED. Authentic receipt rendered.
- Narration: "AI Cart initiates PayPal Orders v2. The buyer approves on PayPal's secure hosted page. Upon return, AI Cart verifies every penny and payee ID server-side before executing capture. Complete receipt generated."

[2:45 - 3:00] Scene 8: Closing — Why Deterministic Control Matters
- Screen: PowerShell terminal showing 227 automated tests passing in 0.75s, followed by final architecture slide.
- Visual: "227 Automated Tests Passing | Strictly $0.00 Spent | PayPal Developer Platform + Google Gemini".
- Narration: "227 automated tests verify immunity against prompt injections, race conditions, and forged webhooks. AI Cart proves that autonomous commerce can be genuinely trustworthy when AI proposes, but deterministic software governs. Thank you."
```

---

## Knowledge Graph Tooling (Graphify)

AI Cart maintains an AST-extracted code knowledge graph generated via the official Graphify CLI (`graphifyy`) and automated via native Google Antigravity lifecycle hooks:
- **Zero-Cost & Local**: 100% offline AST parsing without LLM tokens.
- **Automated Lifecycle Hooks (`.agents/hooks.json`)**:
  - `PreInvocation`: Rebuilds the graph if source files changed and ensures graph consultation before modifications.
  - `Stop`: Synchronizes the knowledge graph when work finishes.
- **Manual Verification**:
  ```powershell
  graphify update . --force
  ```

---

## Repository Documentation Index

- [`AGENTS.md`](AGENTS.md): Core architectural invariants and operating rules.
- [`TASK_GATES.md`](TASK_GATES.md): Phase roadmap, acceptance criteria, and verification sign-offs.
- [`docs/architecture/SYSTEM_ARCHITECTURE.md`](docs/architecture/SYSTEM_ARCHITECTURE.md): System architecture and trust boundaries.
- [`docs/decisions/ADR-0004-ZERO-SPEND-POLICY.md`](docs/decisions/ADR-0004-ZERO-SPEND-POLICY.md): Zero-spend engineering policy and verified free tiers.
- [`docs/security/THREAT_MODEL.md`](docs/security/THREAT_MODEL.md): Threat model and security controls.
- [`docs/quality/TEST_STRATEGY.md`](docs/quality/TEST_STRATEGY.md): Comprehensive test strategy and negative testing.
- [`docs/planning/CURRENT_STATUS.md`](docs/planning/CURRENT_STATUS.md): Current implementation status.
- [`docs/planning/HANDOFF.md`](docs/planning/HANDOFF.md): Engineering handoff and verification log.
