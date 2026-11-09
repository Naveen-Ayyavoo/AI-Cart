# TrustCart Current Workspace & Environment Status

**Last Updated**: 2026-11-09  
**Current Phase**: Phase P0 (Development Environment & Engineering Workspace) - **IN PROGRESS**

---

## 1. Verified Environment Facts

The following items have been directly verified via local execution commands:
- **Operating System**: Windows 64-bit
- **Workspace Directory**: `D:\TrustCart`
- **IDE**: Antigravity IDE 2.6.0
- **Python Version**: Python 3.14.10 (64-bit)
- **Virtual Environment**: Located at `D:\TrustCart\.venv`
- **Pip Version**: pip 26.3 (located inside `.venv\Lib\site-packages\pip`)
- **Version Control**: Git 2.56.0.windows.4 (Repository initialized locally; no remote configured)
- **Workspace Configuration**: `.vscode/settings.json` configured to use `.venv\Scripts\python.exe`
- **Exclusion Hygiene**: `.gitignore` strictly excludes `.venv`, `.env`, SQLite files, and caches

---

## 2. Unverified Items (Pending User Confirmation)

The following items remain **UNVERIFIED** until confirmed by the user:
- [ ] **Antigravity Google Sign-in**: Status of Google account authentication within the Antigravity IDE.
- [ ] **Microsoft Python Extension**: Verified in IDE extensions list (`ms-python.python`).
- [ ] **Microsoft Pylance Extension**: Verified in IDE extensions list (`ms-python.vscode-pylance`).
- [ ] **Ruff Extension**: Verified in IDE extensions list (`charliermarsh.ruff`).
- [ ] **Git Remote / Remote Repository Creation**: Upstream GitHub/GitLab repository creation.
- [ ] **Runtime API Connectivity**: Active API key reachability testing for Gemini (P2), Channel3 (P3), and PayPal Sandbox (P6) upon phase initiation.

---

## 3. Approved Free-Tier Technology Stack & Quota Registry

Per [`ADR-0004`](file:///d:/TrustCart/docs/decisions/ADR-0004-ZERO-SPEND-POLICY.md), TrustCart operates under a mandatory **Zero-Spend Engineering Policy**. All services have been verified on free tiers based on account-dashboard evidence provided by the project owner:

| Service / Resource | Approved Tier | Documented Quota / Allowance | Billing Status | Verification Date | Restrictions / Degradation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Antigravity IDE** | Individual Free / Jio Google AI Pro Benefit | Included developer benefit | **VERIFIED FREE** | 2026-11-09 | Local IDE execution; zero additional tooling cost. |
| **Google Gemini API** | Free Tier only (via AI Studio) | • Gemini 3.5 Flash Lite: 15 RPM, 250K TPM, 500 RPD<br>• Gemini 3.1 Flash Lite: 15 RPM, 250K TPM, 500 RPD<br>• Gemini 3.8 Flash: 5 RPM, 250K TPM, 20 RPD<br>*(Zero quota models treated as unavailable)* | **VERIFIED FREE TIER** | 2026-11-09 | Confirmed Free Tier (no billing account attached). Recommended allocation: Flash Lite for normal shopping; Gemini 3.8 Flash for complex reasoning. Verify actual API model identifiers before Phase P2 implementation. Never enable billing or paid fallbacks. On quota exhaustion, fall back to labeled demo fixtures. |
| **Channel3 API** | Free Tier | 1,000 credits/month (resets 1st of month; 0/1,000 used) + 1,000 one-time bonus credits | **VERIFIED FREE** | 2026-11-09 | Confirmed Free Tier. Bonus credits consumed only after monthly allowance; tracked separately and never represented as recurring. Cache product details by ID; enforce credit counter. On quota exhaustion, halt calls and signal status. |
| **Context7 API** | Free Plan (1 seat) | 1,000 requests / month (0/1,000 used; $0.00 cost) | **VERIFIED FREE** | 2026-11-09 | Confirmed Free Plan. Public documentation access only. Stop calls if monthly ceiling reached. |
| **PayPal Orders API** | Sandbox Environment | Unlimited mock sandbox transactions | **VERIFIED FREE** | 2026-11-09 | Sandbox endpoints only (`api-m.sandbox.paypal.com`). Simulated buyer and merchant accounts only. Zero live payment credentials or endpoints. |
| **Python / Django / SQLite** | Open Source (PSFL / BSD-3 / Public Domain) | Unlimited local usage | **VERIFIED FREE** | 2026-11-09 | Local runtime execution in `.venv`. Zero cloud hosting or DB fees. |
| **GitHub / Git** | GitHub Free | Free public repo & actions | **VERIFIED FREE** | 2026-11-09 | Public repo for hackathon submission. |
| **Demonstration Hosting**| Localhost & YouTube Free | Unlimited local / public video | **VERIFIED FREE** | 2026-11-09 | Local presentation; free unlisted/public video hosting. |

> [!IMPORTANT]
> **Cost Safety Protocol**: These dashboard confirmations establish current account status, not permanent guarantees. Quotas must be verified again before implementing each integration (P2 for Gemini, P3 for Channel3, P6 for PayPal). Service calls must immediately halt when free allowances are exhausted. Never upgrade tiers, enable auto-recharge, or attach billing accounts.

---

## 4. Component Status Tracker

| Component | Target Phase | Implementation Status | Test Status |
| :--- | :--- | :--- | :--- |
| **Workspace Governance & Rules** | P0 | Complete | Verified |
| **Project Documentation & ADRs** | P0 | Complete | Verified |
| **Django Application Skeleton** | P1 | Not Started | Not Started |
| **Purchase Contract Engine** | P2 | Not Started | Not Started |
| **Gemini Structured Integration**| P2 | Not Started | Not Started |
| **Channel3 Catalog Integration** | P3 | Not Started | Not Started |
| **Deterministic Policy Engine**  | P4 | Not Started | Not Started |
| **Approval Binding Manager**     | P5 | Not Started | Not Started |
| **PayPal Orders v2 Integration** | P6 | Not Started | Not Started |
| **PayPal Webhook Listener**      | P6 | Not Started | Not Started |
| **Adversarial & Security Suite** | P7 | Not Started | Not Started |

