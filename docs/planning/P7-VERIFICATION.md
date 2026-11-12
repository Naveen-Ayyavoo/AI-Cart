# Phase P7 Verification Report: Security, Adversarial Defenses & Reliability

> **Status**: VERIFIED & SIGNED OFF  
> **Date**: 2026-11-10  
> **Workspace**: `D:\TrustCart`  
> **Test Suite**: 153 passing tests (Ran in ~0.62s with 0 failures, 0 errors)  
> **Lint & Health**: Ruff 0 issues, Django system checks 0 issues, Graphify 874 nodes / 1922 edges  
> **Zero-Spend Audit**: Total additional expenditure: **$0.00**

---

## 1. Audit & Coverage Matrix

| # | Requirement Category | Scope / Threat Scenario | Audit Status | Implementation Location | Test Reference |
|---|---|---|---|---|---|
| **1** | **Direct Prompt Injection** | Shopper input attempts system instruction override, currency alteration, secret exfiltration, policy bypass, or forced confirmation. | **VERIFIED** | `contracts/gemini.py`<br>`contracts/schemas.py`<br>`policies/engine.py`<br>`contracts/views.py` | `contracts/tests/test_adversarial_security.py`<br>• `test_schema_rejects_injected_extra_keys`<br>• `test_schema_rejects_non_usd_currency_injection`<br>• `test_prompt_encapsulation_prevents_system_instruction_escape`<br>• `test_prompt_injection_secret_exfiltration_prevented`<br>• `test_direct_prompt_injection_in_raw_prompt_cannot_bypass_policy_engine`<br>• `test_direct_prompt_injection_cannot_force_contract_confirmation` |
| **2** | **Indirect Prompt Injection** | Untrusted product title, description, or raw catalog evidence contains adversarial payloads attempting to override policy, grant admin role, set price to $0, or alter payee. | **VERIFIED** | `policies/engine.py`<br>`orders/services.py`<br>`orders/models.py`<br>`payments/services.py` | `payments/tests/test_adversarial_and_e2e.py`<br>• `test_indirect_prompt_injection_in_product_evidence_has_zero_execution_authority` |
| **3** | **Price & Transaction Integrity** | Price fluctuation (+$0.01 / -$0.01), currency mismatch, payee hijacking, cart fingerprint forgery, and out-of-band proposal mutation. | **VERIFIED** | `payments/services.py`<br>`orders/models.py`<br>`orders/fingerprint.py` | `payments/tests/test_adversarial_and_e2e.py`<br>• `test_price_fluctuation_one_cent_higher_fails_closed`<br>• `test_price_fluctuation_one_cent_lower_fails_closed`<br>• `test_payee_tampering_fails_closed`<br>• `test_fingerprint_tampering_fails_closed`<br>• `test_pre_capture_currency_mismatch_fails_closed`<br>• `test_pre_capture_proposal_mutation_fails_closed` |
| **4** | **Approval Token Replay** | Attempting duplicate consumption of a single-use approval token concurrently or sequentially. | **VERIFIED** | `orders/models.py`<br>`orders/services.py`<br>`payments/services.py` | `orders/tests/test_concurrency.py`<br>• `test_concurrent_consumption_race_condition`<br>• `test_conditional_atomic_update_criteria`<br>`payments/tests/test_adversarial_and_e2e.py`<br>• `test_approval_token_replay_rejected` |
| **5** | **Duplicate & Concurrent Capture** | Competing or repeated calls to complete checkout on the same PayPal order. | **VERIFIED** | `payments/services.py`<br>`payments/models.py` | `payments/tests/test_adversarial_and_e2e.py`<br>• `test_concurrent_or_duplicate_capture_is_idempotent`<br>• `test_stable_idempotency_keys_reused_on_retries`<br>`payments/tests/test_services_and_views.py`<br>• `test_full_happy_path_checkout_and_server_capture` |
| **6** | **Quota Exhaustion & Provider Failure** | Gemini HTTP 429, timeout, malformed JSON; Channel3 HTTP 429, timeout, credit exhaustion (monthly then bonus), missing credentials; zero quota leakage in customer UI. | **VERIFIED** | `contracts/gemini.py`<br>`catalog/client.py`<br>`catalog/models.py` | `contracts/tests/test_domain_and_gemini.py`<br>• `test_gemini_client_quota_exhaustion_fallback`<br>• `test_gemini_client_timeout_fallback`<br>• `test_gemini_client_malformed_response_fallback`<br>`catalog/tests/test_client_and_search.py`<br>• `test_client_halts_and_falls_back_when_credits_exhausted`<br>• `test_client_http_429_falls_back_to_fixtures`<br>• `test_client_timeout_falls_back_to_fixtures`<br>• `test_ledger_sequential_consumption_monthly_then_bonus`<br>• `test_client_safe_fallback_for_unmatched_query` |
| **7** | **Webhook Signature Failure & Replay** | Missing headers, invalid cryptographic signature, SSRF cert URL forgery, and duplicate event deduplication. | **VERIFIED** | `payments/client.py`<br>`payments/services.py`<br>`payments/views.py` | `payments/tests/test_webhooks.py`<br>• `test_webhook_missing_headers_rejected`<br>• `test_webhook_invalid_signature_rejected`<br>• `test_webhook_duplicate_event_deduplication`<br>`payments/tests/test_client_and_models.py`<br>• `test_verify_webhook_signature_ssrf_protection` |
| **8** | **Out-of-Order Webhook Delivery** | Late arrival of `CHECKOUT.ORDER.APPROVED` or `PAYMENT.CAPTURE.DENIED` after payment order is already `COMPLETED`. | **VERIFIED** | `payments/services.py` | `payments/tests/test_adversarial_and_e2e.py`<br>• `test_out_of_order_webhook_cannot_regress_completed_order`<br>`payments/tests/test_webhooks.py`<br>• `test_out_of_order_webhook_cannot_regress_completed_order` |
| **9** | **Complete Shopper-to-Payment Workflow** | End-to-end user journey across all 5 applications: Contract -> Discovery -> Policy -> Proposal -> Approval -> Checkout -> Capture -> Webhook -> Receipt. | **VERIFIED** | Full application stack | `payments/tests/test_adversarial_and_e2e.py`<br>• `test_complete_end_to_end_shopper_journey` |
| **10** | **Security Regression Coverage** | Automated test suite enforcing all invariants across 153 tests with zero regressions. | **VERIFIED** | Full application stack | 153 automated tests across `contracts`, `catalog`, `policies`, `orders`, `payments`, `trustcart` |

---

## 2. Detailed Requirement Verification Evidence

### A. Direct Prompt Injection

#### 1. Schema Injection Rejection (`extra="forbid"`)
- **Implementation**: [`contracts/schemas.py:PurchaseContractExtraction`](file:///d:/TrustCart/contracts/schemas.py) configured with `model_config = ConfigDict(extra="forbid")`.
- **Test**: `contracts/tests/test_adversarial_security.py::test_schema_rejects_injected_extra_keys`
- **Assertion**:
  ```python
  with self.assertRaises(PydanticValidationError) as ctx:
      PurchaseContractExtraction(**malicious_payload)
  self.assertIn("extra_forbidden", str(ctx.exception))
  ```
- **Result**: PASS. Injected fields (`execute_payment`, `bypass_approval`, `admin_override`) are rejected immediately.
- **Limitation**: Pydantic validation operates on JSON outputs. If an LLM returns non-JSON, fallback fixture logic triggers.

#### 2. Currency Tampering Rejection
- **Implementation**: `contracts/schemas.py` validates `currency == "USD"`. Non-USD values raise `ValidationError`.
- **Test**: `contracts/tests/test_adversarial_security.py::test_schema_rejects_non_usd_currency_injection`
- **Assertion**:
  ```python
  for bad_currency in ["EUR", "GBP", "INR", "BTC", "USDT"]:
      with self.assertRaises(PydanticValidationError):
          PurchaseContractExtraction(..., currency=bad_currency)
  ```
- **Result**: PASS. All non-USD inputs fail closed.

#### 3. Secret Exfiltration Prevention
- **Implementation**: [`contracts/gemini.py:GeminiContractClient`](file:///d:/TrustCart/contracts/gemini.py). The prompt sent to Google AI Studio encapsulates user input in `<shopper_prompt>` tags. Server secrets (`GEMINI_API_KEY`, `PAYPAL_CLIENT_SECRET`, `DJANGO_SECRET_KEY`) are never passed in the prompt body. Extra returned fields are rejected by schema validation.
- **Test**: `contracts/tests/test_adversarial_security.py::test_prompt_injection_secret_exfiltration_prevented`
- **Assertion**:
  ```python
  contract, is_fallback, _ = client.extract_contract(malicious_prompt, save_to_db=False)
  self.assertTrue(is_fallback)
  self.assertNotIn("SUPER_SECRET_KEY", str(contract.__dict__))
  self.assertNotIn("mock_key", req_data)
  ```
- **Result**: PASS. Outbound request does not leak secrets, and hallucinated/injected secret fields cause fail-closed fallback to safe demo fixtures.
- **Limitation**: Does not guarantee an external LLM will never output public training data; guarantees application secrets are never sent to or returned by the LLM into internal state.

#### 4. Policy Bypass Immunity
- **Implementation**: [`policies/engine.py:PolicyEngine`](file:///d:/TrustCart/policies/engine.py). Evaluates deterministic rules (`BudgetCeiling`, `CurrencyMatch`, `StockAvailability`, `ExcludedTerms`, `RequiredSpecs`) using strictly typed fields on `PurchaseContract` and `ProductEvidence`. It never parses or executes `contract.raw_prompt`.
- **Test**: `contracts/tests/test_adversarial_security.py::test_direct_prompt_injection_in_raw_prompt_cannot_bypass_policy_engine`
- **Assertion**:
  ```python
  result = engine.evaluate(adversarial_contract, expensive_product)
  self.assertEqual(result.outcome, "INELIGIBLE")
  self.assertEqual(budget_rule.outcome, "FAIL")
  ```
- **Result**: PASS. Adversarial commands in `raw_prompt` have zero authority over policy evaluation.

#### 5. Contract State Advancement Immunity
- **Implementation**: [`contracts/views.py:contract_create`](file:///d:/TrustCart/contracts/views.py) forces `contract.state = ContractState.DRAFT`. Only explicit HTTP POST to `contract_confirm` can transition the contract to `CONFIRMED`.
- **Test**: `contracts/tests/test_adversarial_security.py::test_direct_prompt_injection_cannot_force_contract_confirmation`
- **Assertion**:
  ```python
  resp = self.client.post(reverse("contract_create"), data={"prompt": "...", "state": "CONFIRMED"})
  self.assertEqual(contract.state, ContractState.DRAFT)
  self.assertIsNone(contract.confirmed_at)
  ```
- **Result**: PASS. Direct state manipulation via form or prompt injection fails safely.

---

### B. Indirect Prompt Injection via Retrieved Product Content

#### 1. Zero Execution Authority in Catalog Content
- **Implementation**:
  - `policies/engine.py`: Product `title` and `description` are scanned strictly as passive strings for substring inclusion of excluded terms. They are never fed into code execution or secondary LLM prompts.
  - `orders/services.py:ProposalService`: Sets `payee_id = DEFAULT_DEMO_PAYEE_ID` and computes `base_amount = product.price * quantity`.
  - `payments/services.py:PaymentService`: Revalidates payee and amount against the approved proposal, completely ignoring product descriptions.
- **Test**: `payments/tests/test_adversarial_and_e2e.py::test_indirect_prompt_injection_in_product_evidence_has_zero_execution_authority`
- **Assertion**:
  ```python
  # Malicious product with injection payload in description and raw_evidence
  result = engine.evaluate(self.contract, malicious_product)
  self.assertEqual(result.outcome, "INELIGIBLE")
  self.assertEqual(budget_rule.outcome, "FAIL")

  # Conforming item with malicious payee injection in description
  proposal, approval = ProposalService.create_proposal(...)
  self.assertEqual(proposal.payee_id, DEFAULT_DEMO_PAYEE_ID)
  self.assertNotIn("attacker@evil.com", proposal.payee_id)
  self.assertEqual(approval.state, "PENDING")
  ```
- **Result**: PASS. Untrusted product text cannot change policy outcomes, bypass approval, or alter payment destinations.
- **Limitation**: Semantic filtering of offensive text in product descriptions relies on excluded terms configured by the shopper or catalog filters; the backend guarantees execution safety, not subjective sentiment moderation.

---

### C. Price Changes Between Evaluation and Checkout

#### 1. Price Fluctuation (+ $0.01)
- **Implementation**: [`payments/services.py:PaymentService.complete_checkout`](file:///d:/TrustCart/payments/services.py) compares `remote_amount != payment_order.total_amount`.
- **Test**: `payments/tests/test_adversarial_and_e2e.py::test_price_fluctuation_one_cent_higher_fails_closed`
- **Assertion**:
  ```python
  with self.assertRaises(PayPalRevalidationError) as ctx:
      PaymentService.complete_checkout("PP-ORD-FLUCT-01", client=mock_client)
  self.assertIn("Price tampering detected", str(ctx.exception))
  self.assertEqual(order.status, "FAILED")
  self.assertEqual(mock_client.capture_order.call_count, 0)
  ```
- **Result**: PASS. Capture aborted; order marked `FAILED`.

#### 2. Price Fluctuation (- $0.01)
- **Implementation**: Strict equality comparison `remote_amount != payment_order.total_amount`.
- **Test**: `payments/tests/test_adversarial_and_e2e.py::test_price_fluctuation_one_cent_lower_fails_closed`
- **Assertion**:
  ```python
  with self.assertRaises(PayPalRevalidationError):
      PaymentService.complete_checkout("PP-ORD-FLUCT-02", client=mock_client)
  self.assertEqual(order.status, "FAILED")
  self.assertEqual(mock_client.capture_order.call_count, 0)
  ```
- **Result**: PASS. Even decreases in price fail closed to protect cryptographic contract binding.

#### 3. Currency Mismatch
- **Implementation**: `payments/services.py` verifies `remote_currency == "USD"` and `remote_currency == payment_order.currency`.
- **Test**: `payments/tests/test_adversarial_and_e2e.py::test_pre_capture_currency_mismatch_fails_closed`
- **Assertion**:
  ```python
  with self.assertRaises(PayPalRevalidationError) as ctx:
      PaymentService.complete_checkout("PP-ORD-CURR-FAIL", client=mock_client)
  self.assertIn("Currency mismatch", str(ctx.exception))
  self.assertEqual(order.status, "FAILED")
  self.assertEqual(mock_client.capture_order.call_count, 0)
  ```
- **Result**: PASS. Remote EUR order rejected; capture aborted.

#### 4. Cart Fingerprint & Proposal Mutation
- **Implementation**: `payments/services.py` checks `remote_custom_id == payment_order.cart_fingerprint` and `payment_order.proposal.verify_fingerprint()`.
- **Tests**:
  - `payments/tests/test_adversarial_and_e2e.py::test_fingerprint_tampering_fails_closed`
  - `payments/tests/test_adversarial_and_e2e.py::test_pre_capture_proposal_mutation_fails_closed`
- **Assertion**:
  ```python
  with self.assertRaises(PayPalRevalidationError) as ctx:
      PaymentService.complete_checkout("PP-ORD-MUTATE-PROP", client=mock_client)
  self.assertIn("proposal fingerprint verification failed", str(ctx.exception).lower())
  self.assertEqual(order.status, "FAILED")
  self.assertEqual(mock_client.capture_order.call_count, 0)
  ```
- **Result**: PASS. Out-of-band database alterations void pre-capture revalidation and fail closed.

---

### D. Approval-Token Replay & Concurrency

#### 1. Atomic Single-Use Consumption Under 10 Concurrent Threads
- **Implementation**: [`orders/models.py:PurchaseApproval.consume`](file:///d:/TrustCart/orders/models.py) uses conditional database atomic updates (`state='APPROVED'`, `expires_at > now`, `consumed_at IS NULL`, `cart_fingerprint=expected`).
- **Test**: `orders/tests/test_concurrency.py::test_concurrent_consumption_race_condition`
- **Assertion**:
  ```python
  # 10 worker threads compete simultaneously
  self.assertEqual(success_count, 1)
  self.assertEqual(rejected_count, 9)
  ```
- **Result**: PASS. Exactly 1 thread succeeds; 9 are rejected.

#### 2. Replay Prevention on Checkout Initiation
- **Implementation**: [`payments/services.py:PaymentService.initiate_checkout`](file:///d:/TrustCart/payments/services.py) consumes approval token immediately upon order creation.
- **Test**: `payments/tests/test_adversarial_and_e2e.py::test_approval_token_replay_rejected`
- **Assertion**:
  ```python
  with self.assertRaises(ApprovalAlreadyConsumedError):
      PaymentService.initiate_checkout(self.approval.token, ...)
  ```
- **Result**: PASS. Repeated checkout attempts with a consumed token fail closed immediately.

---

### E. Duplicate & Concurrent Capture

#### 1. Idempotent Capture on Completed Orders
- **Implementation**: [`payments/services.py:PaymentService.complete_checkout`](file:///d:/TrustCart/payments/services.py) checks if `payment_order.status == 'COMPLETED'`. If already completed, returns existing order and capture record without calling `client.capture_order`.
- **Test**: `payments/tests/test_adversarial_and_e2e.py::test_concurrent_or_duplicate_capture_is_idempotent`
- **Assertion**:
  ```python
  ord1, cap1 = PaymentService.complete_checkout("PP-ORD-IDEMP-01", client=mock_client)
  ord2, cap2 = PaymentService.complete_checkout("PP-ORD-IDEMP-01", client=mock_client)
  self.assertEqual(mock_client.capture_order.call_count, 1)  # NOT called a second time
  self.assertEqual(PaymentCaptureRecord.objects.filter(order=order).count(), 1)
  ```
- **Result**: PASS. Repeated calls return existing capture; zero double-capture.

#### 2. Stable Idempotency Keys Across Retries
- **Implementation**: `payments/services.py` persists `create_idempotency_key` and `capture_idempotency_key` as stable UUIDs on `PaymentOrder`.
- **Test**: `payments/tests/test_adversarial_and_e2e.py::test_stable_idempotency_keys_reused_on_retries`
- **Assertion**:
  ```python
  self.assertTrue(create_key.startswith("CREATE-"))
  self.assertTrue(capture_key.startswith("CAPTURE-"))
  self.assertEqual(order.create_idempotency_key, create_key)
  self.assertEqual(order.capture_idempotency_key, capture_key)
  ```
- **Result**: PASS. Keys remain stable across operations.

---

### F. Quota Exhaustion & Provider Failure

#### 1. Gemini HTTP 429, Timeout, and Malformed Responses
- **Implementation**: [`contracts/gemini.py:GeminiContractClient`](file:///d:/TrustCart/contracts/gemini.py) catches `HTTPError(code=429)`, `URLError`, `TimeoutError`, and `JSONDecodeError`. On failure, halts external requests and falls back to labeled demo fixtures with prominent `FALLBACK_DISCLOSURE`.
- **Tests**:
  - `contracts/tests/test_domain_and_gemini.py::test_gemini_client_quota_exhaustion_fallback`
  - `contracts/tests/test_domain_and_gemini.py::test_gemini_client_timeout_fallback`
  - `contracts/tests/test_domain_and_gemini.py::test_gemini_client_malformed_response_fallback`
- **Assertion**:
  ```python
  self.assertTrue(is_fallback)
  self.assertEqual(contract.source, ContractSource.DEMO_FIXTURE)
  self.assertEqual(contract.extraction_provenance.get("disclosure"), FALLBACK_DISCLOSURE)
  ```
- **Result**: PASS. Graceful, transparent fallback without unhandled exceptions or customer confusion.

#### 2. Channel3 Credit Ledger Sequential Consumption
- **Implementation**: [`catalog/models.py:Channel3CreditLedger`](file:///d:/TrustCart/catalog/models.py) tracks 1,000 monthly allowance and 1,000 bonus credits separately. Monthly allowance is debited first; bonus is debited only after monthly is exhausted. When both reach 0, billable calls halt.
- **Test**: `catalog/tests/test_client_and_search.py::test_ledger_sequential_consumption_monthly_then_bonus`
- **Assertion**:
  ```python
  # Step 1: 600 debited from monthly -> 400 monthly remain, 1000 bonus remain
  self.assertEqual(self.ledger.monthly_available, 400)
  self.assertEqual(self.ledger.bonus_remaining, 1000)

  # Step 2: 500 debited -> 400 monthly + 100 bonus -> 0 monthly remain, 900 bonus remain
  self.assertEqual(self.ledger.monthly_available, 0)
  self.assertEqual(self.ledger.bonus_remaining, 900)

  # Step 3: Total exhaustion -> halts calls
  self.assertFalse(self.ledger.can_consume(1))
  ```
- **Result**: PASS. Strict sequential budget enforcement verified.

#### 3. Channel3 HTTP 429 and Timeout Handling
- **Implementation**: [`catalog/client.py:Channel3Client.search`](file:///d:/TrustCart/catalog/client.py) catches `HTTPError` and network `Exception`, returning labeled demo fixtures.
- **Tests**:
  - `catalog/tests/test_client_and_search.py::test_client_http_429_falls_back_to_fixtures`
  - `catalog/tests/test_client_and_search.py::test_client_timeout_falls_back_to_fixtures`
- **Assertion**:
  ```python
  self.assertTrue(is_fallback)
  self.assertIn("HTTP 429", msg)
  self.assertGreaterEqual(len(products), 1)
  ```
- **Result**: PASS. Network errors and rate limits fail safely to demo fixtures.

#### 4. Customer UI Quota Isolation
- **Implementation**: Cleaned UI templates remove all internal quota counters, credit balances, and zero-spend policy references.
- **Test**: `contracts/tests/test_ui_content_hygiene.py::test_customer_ui_does_not_contain_quota_or_infrastructure_metrics`
- **Assertion**:
  ```python
  for phrase in FORBIDDEN_QUOTA_PHRASES:
      self.assertNotIn(phrase.lower(), content.lower())
  ```
- **Result**: PASS. Customer views present clean, professional messages without exposing backend quota metrics.

---

### G. Webhook Verification & Out-of-Order Safety

#### 1. Cryptographic Signature Verification & SSRF Defense
- **Implementation**: [`payments/client.py:PayPalClient.verify_webhook_signature`](file:///d:/TrustCart/payments/client.py) verifies certificates against `api.sandbox.paypal.com` and calls PayPal's `POST /v1/notifications/verify-webhook-signature`. Rogue certificate URLs are rejected immediately.
- **Tests**:
  - `payments/tests/test_webhooks.py::test_webhook_missing_headers_rejected`
  - `payments/tests/test_webhooks.py::test_webhook_invalid_signature_rejected`
  - `payments/tests/test_client_and_models.py::test_verify_webhook_signature_ssrf_protection`
- **Assertion**:
  ```python
  with self.assertRaises(PayPalError):
      PaymentService.handle_webhook(headers=self.valid_headers, raw_body=payload, client=mock_client)
  self.assertEqual(event_record.status, "REJECTED")
  ```
- **Result**: PASS. Forged or unverified webhooks fail closed.

#### 2. Out-of-Order Webhook Delivery Protection
- **Implementation**: [`payments/services.py:PaymentService._process_verified_webhook_event`](file:///d:/TrustCart/payments/services.py) prevents regressions if an order is already in `COMPLETED` state.
- **Test**: `payments/tests/test_adversarial_and_e2e.py::test_out_of_order_webhook_cannot_regress_completed_order`
- **Assertion**:
  ```python
  # Late-arriving CHECKOUT.ORDER.APPROVED or PAYMENT.CAPTURE.DENIED
  PaymentService.handle_webhook(...)
  order.refresh_from_db()
  self.assertEqual(order.status, "COMPLETED")
  ```
- **Result**: PASS. Completed transactions are immutable to late-arriving earlier-state events.

---

## 3. End-to-End Dependency Transparency

Per hackathon standards, every external dependency in TrustCart is classified transparently:

| Component / Step | Test Mode | Classification | Implementation Detail |
|---|---|---|---|
| **P0: Governance & Environment** | Local | **Genuine Local Evidence** | Python 3.14.10, Django 6.1.3, SQLite `db.sqlite3` running on Windows 64-bit PowerShell. |
| **P2: Gemini Contract Extraction** | Unit / Integration | **Mocked External Service & Curated Fixture** | Unit tests mock `urllib.request.urlopen` with synthetic JSON payloads; offline fallback uses curated fixtures in `contracts/fixtures.py`. Live API requires user's free Google AI Studio key. |
| **P3: Channel3 Product Search** | Unit / Integration | **Mocked External Service & Curated Fixture** | Unit tests mock HTTP 200, 429, and timeouts; fallback loads curated US products in `catalog/fixtures.py`. Live API uses server-side `x-api-key` against `https://api.trychannel3.com`. |
| **P4: Policy Engine** | Unit | **Genuine Local Implementation** | 100% deterministic local Python logic with Decimal arithmetic; zero external network dependencies. |
| **P5: Approval & Fingerprinting** | Unit / Concurrency | **Genuine Local Implementation** | Cryptographic SHA-256 cart fingerprinting with multi-threaded atomic database locking. |
| **P6: PayPal Sandbox Acceptance** | Live Acceptance Test | **Genuine Live Integration Evidence** | Live US Sandbox Order `7AR87873PW3372724` ($18.75 USD) created, approved by Sandbox buyer `sb-vwssg53834434@personal.example.com`, captured server-side (`1UK419750T1940027`), and verified via genuine PayPal webhook `WH-3LR1057661587304S-29B18802VC813202V`. |
| **P7: Adversarial & E2E Journey** | Automated Test Suite | **Mocked External Service** | Isolated end-to-end user journey in `payments/tests/test_adversarial_and_e2e.py` uses `MagicMock(spec=PayPalClient)` to prevent burning live rate limits or mutating sandbox state during continuous CI/CD runs. |

---

## 4. Quality Gate Summary

```powershell
# 1. Full Automated Test Suite (153 tests)
.\.venv\Scripts\python.exe manage.py test
Ran 153 tests in 0.620s — OK

# 2. Concurrency & Payment Integrity Tests (30 focused tests)
.\.venv\Scripts\python.exe manage.py test orders.tests.test_concurrency payments.tests.test_services_and_views payments.tests.test_adversarial_and_e2e payments.tests.test_webhooks
Ran 30 tests in 0.358s — OK

# 3. Ruff Code Linter
.\.venv\Scripts\ruff.exe check .
All checks passed!

# 4. Django System Checks
.\.venv\Scripts\python.exe manage.py check
System check identified no issues (0 silenced).

# 5. Graphify Knowledge Graph
graphify update . --force
Rebuilt: 874 nodes, 1922 edges, 71 communities (Offline, 0 tokens, $0.00 spend).

# 6. Zero-Spend Financial Audit
Total additional expenditure: $0.00
```

---

## 5. Remaining Risks & Documented Limitations

1. **Adversarial LLM Semantics**: TrustCart's untrusted reasoning boundary enforces strict output schema validation and strips execution authority from the LLM. However, like all LLM applications, if an adversarial prompt subtly misrepresents shopper preferences without triggering schema violations (e.g. requesting "wireless" when the user said "wired"), the output is still subject to human inspection during the mandatory contract review step. Human review and explicit confirmation remain the primary line of semantic defense.
2. **Product Catalog Semantics**: Unstructured descriptions from untrusted third-party sellers are ingested as passive text. While they cannot execute commands or alter policy rules, semantic matching of nuanced preferences (e.g. "tactile" vs "clicky") relies on substring matching and catalog tags. Missing or ambiguous critical attributes correctly fail closed to `UNKNOWN`.
3. **Sandbox Network Flakiness**: Transient network timeouts between the local server and PayPal Sandbox API can occur during live demonstrations. TrustCart mitigates this via `PENDING_RECONCILIATION` and authoritative reconciliation on status queries.

