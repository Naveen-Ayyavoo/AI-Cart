# ADR-0004: Zero-Spend Engineering and Free-Tier Quota Policy

## Status
Accepted

## Context
TrustCart is being built for the PayPal AI Hackathon. A foundational, permanent project constraint is that the total additional expenditure for developing, testing, demonstrating, and submitting TrustCart must remain strictly **ZERO**.

Autonomous agentic development and modern cloud architectures often incur unexpected expenses through pay-as-you-go APIs, silent tier upgrades, automatic billing renewals, cloud database provisioning, or external SaaS integrations. To guarantee zero financial liability, TrustCart requires a deterministic, binding zero-spend engineering policy governing all tooling, runtime services, API integrations, and demonstration media.

---

## Decision

### 1. Zero Additional Expenditure Mandate
Under no circumstances may any activity associated with TrustCart incur financial charges. The project must operate entirely within verified free tiers, local open-source runtimes, mock environments, or pre-existing developer benefits.

### 2. Approved Service Registry & Free-Tier Quotas

| Service / Tool | Approved Tier | Documented Allowance | Verification Date | Billing Status |
| :--- | :--- | :--- | :--- | :--- |
| **Antigravity IDE** | Individual Free Plan / Jio Google AI Pro Benefit | Included developer benefit | 2026-11-09 | **VERIFIED FREE** (Zero cost) |
| **Google Gemini API** | Free Tier only (via Google AI Studio) | • Gemini 3.5 Flash Lite: 15 RPM, 250K TPM, 500 RPD<br>• Gemini 3.1 Flash Lite: 15 RPM, 250K TPM, 500 RPD<br>• Gemini 3.8 Flash: 5 RPM, 250K TPM, 20 RPD<br>*(Models with zero quota treated as unavailable)* | 2026-11-09 | **VERIFIED FREE TIER** (Confirmed via AI Studio dashboard; no billing attached) |
| **Channel3 API** | Free tier | 1,000 credits / month (resets 1st of month; 0/1,000 used) + 1,000 one-time bonus credits (consumed after monthly allowance; tracked separately) | 2026-11-09 | **VERIFIED FREE** (Confirmed via Channel3 dashboard) |
| **Context7 API** | Free plan (1 seat) | 1,000 requests / month (0/1,000 used) | 2026-11-09 | **VERIFIED FREE** (Confirmed via Context7 dashboard; cost $0.00) |
| **PayPal API** | Sandbox environment only | Unlimited sandbox test transactions (simulated buyer & merchant accounts only) | 2026-11-09 | **VERIFIED FREE** (Sandbox has zero monetary settlement) |
| **Python / Django / SQLite** | Open Source (PSFL, BSD-3, Public Domain) | Unlimited local usage | 2026-11-09 | **VERIFIED FREE** (Local environment) |
| **Git / GitHub** | GitHub Free plan | Free public repository & actions | 2026-11-09 | **VERIFIED FREE** (Zero cost) |
| **Demonstration Hosting** | Localhost & YouTube Free | Unlimited local demo / public video | 2026-11-09 | **VERIFIED FREE** (Zero cost) |

### 3. Absolute Prohibitions
1. **No Paid Billing Accounts**: Never enable billing, attach credit cards, or link paid Google Cloud Billing accounts to the Gemini API project.
2. **No Tier Upgrades**: Never upgrade any service or API project from a free tier to a paid, pay-as-you-go, or developer tier.
3. **No Paid Fallbacks**: Never configure paid LLM fallbacks, paid search engines (e.g. paid Google Search grounding), or premium endpoints.
4. **No Paid Cloud Infrastructure**: Never provision paid cloud servers, VPS, cloud databases, managed containers, or custom domains.
5. **No Auto-Recharge or Trials**: Never enable auto-recharge, overdraft protection requiring billing, or free trials that automatically convert into paid subscriptions.
6. **No Unapproved Infrastructure**: Never make an architectural or infrastructure change that could incur charges without prior explicit written approval from the user.

### 4. Quota Exhaustion & Degradation Protocol
When an external free-tier quota is reached:
1. **Immediate Cessation**: The service client must immediately cease making outbound network calls to that provider.
2. **Clear Status Signaling**: Return a deterministic, user-visible `QUOTA_EXHAUSTED` status explaining that the free allowance limit has been reached.
3. **Zero Paid Fallback**: Never attempt an automatic upgrade or paid fallback.
4. **Fixture Fallback**: Transition to clearly labeled local test fixtures or cached offline data for local demonstration.
5. **Transparency Invariant**: Cached or fixture responses must be explicitly marked as `[DEMO FIXTURE]` or `[CACHED EVIDENCE]`. Never misrepresent synthetic or cached data as live API responses.

### 5. Service-Specific Governance

#### A. Google Gemini API (Free Tier)
- **Verified Status**: Free Tier confirmed via Google AI Studio dashboard (no active billing account).
- **Verified Free Model Quotas**:
  - `Gemini 3.5 Flash Lite`: 15 RPM, 250,000 TPM, 500 RPD
  - `Gemini 3.1 Flash Lite`: 15 RPM, 250,000 TPM, 500 RPD
  - `Gemini 3.8 Flash`: 5 RPM, 250,000 TPM, 20 RPD
  - *Models displaying zero quotas must be treated as unavailable.*
- **Recommended Model Allocation**:
  - Use **Flash Lite** for standard shopping requests and routine extraction tasks.
  - Use **Gemini 3.8 Flash** selectively for complex multi-product trade-off evaluations.
  - *Note: These are dashboard-displayed model names. Actual API model identifiers must be verified prior to implementation in Phase P2.*
- **Prohibitions**: Chargeable features, such as paid Google Search grounding, paid fine-tuning, paid tier upgrades, or paid fallback models, are strictly forbidden.
- **Data Protection**: Never transmit sensitive personal data, payment credentials, or secrets to the free-tier API.

#### B. Channel3 API (Product Discovery)
- **Verified Status**: Free Tier confirmed via Channel3 account dashboard (0/1,000 used).
- **Monthly Allowance**: 1,000 credits/month, resetting automatically on the first day of each month.
- **One-Time Bonus Credits**: 1,000 bonus credits remaining.
- **Balance Governance**:
  - Monthly free credits and bonus credits must be tracked separately.
  - Bonus credits are consumed *only after* monthly free credits are exhausted.
  - Bonus credits must never be represented as recurring allowance.
- **Consumption Controls**:
  - Enforce an internal configurable credit budget counter.
  - Cache retrieved product details by unique product ID to eliminate duplicate external queries.
  - Avoid unnecessary repeated searches; queries must be strictly initiated by user-confirmed Purchase Contracts.

#### C. Context7 API (Documentation Retrieval)
- **Verified Status**: Free Plan confirmed via Context7 account dashboard (1 seat, $0.00 cost, 0/1,000 requests used).
- **Allowance**: 1,000 requests / month.
- **Governance**: Access public documentation endpoints only. Monitor monthly usage and halt calls if the free allowance limit is reached.

#### D. PayPal API (Sandbox Only)
- **Verified Status**: PayPal Developer Sandbox environment.
- **Governance**: Use exclusively PayPal Developer Sandbox endpoints (`api-m.sandbox.paypal.com`) with simulated buyer and merchant accounts only.
- **Prohibitions**: Live client credentials, live app IDs, and live production endpoints (`api-m.paypal.com`) are strictly prohibited in the codebase. Zero live monetary transactions or merchant fees.

### 6. Dependency Cost-Impact Review
Every newly proposed third-party Python package, tool, or library must undergo an explicit cost-impact review:
- Must carry a permissive free/open-source license (MIT, BSD, Apache 2.0, MPL, LGPL).
- Must have zero paid runtime dependencies, paid subscription gates, or proprietary license keys.

---

## Consequences
- **Positive**: Complete elimination of financial risk; total predictability in development expenditure; guarantees zero-cost reproducibility for judges and open-source contributors.
- **Negative**: Development and testing must operate within strict rate limits and monthly quotas; requires maintenance of offline fixtures when quotas are depleted.

