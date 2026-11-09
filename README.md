# TrustCart

> **A Trustworthy Autonomous Shopping Assistant**  
> *PayPal AI Hackathon Project*

TrustCart enables shoppers to delegate tedious shopping research to an autonomous assistant while maintaining strict, deterministic control over financial commitments.

---

## What TrustCart Does

TrustCart can:
- Parse and clarify shopper requirements and budgetary limits into structured **Purchase Contracts**.
- Search and compare real product catalog data via **Channel3**.
- Explain evidence, trade-offs, and matching rationale.
- Evaluate candidate items against deterministic purchase and spending policies.
- Prepare an immutable, exact proposed purchase for explicit user approval.

TrustCart **will never**:
- Hallucinate or invent product facts, prices, inventory, or merchant terms.
- Treat untrusted product descriptions or LLM generation as authoritative execution commands.
- Modify user-approved purchase details without voiding the approval.
- Treat a Purchase Contract as payment authorization.
- Permit an LLM to authorize or capture a payment.
- Bypass explicit user approval.

---

## Current Project Status

- **Status**: Phase 0 (Workspace & Governance Initialization) **In Progress**.
- **Implementation Status**: Application implementation **has not begun**. All application features, Django scaffoldings, database schemas, and external API calls remain pending until Phase 0 is formally reviewed and signed off.

---

## Planned Technology Stack

- **Platform**: Windows 64-bit (PowerShell development environment; no WSL)
- **Runtime**: Python 3.14.10 (virtual environment at `.venv`)
- **Backend Framework**: Django 6.1 (to be installed & verified in Phase 1)
- **Database**: SQLite (initial local development)
- **Frontend**: Django Templates, Semantic HTML5, CSS, and Vanilla JavaScript (ES6+)
- **AI / LLM**: Google Gemini API via Google AI Studio (advisory reasoning)
- **Product Data**: Channel3 Catalog API (USD, US Market)
- **Payment Execution**: PayPal Orders API (Sandbox environment, server-side capture, demo payee)

---

## Initial Windows Setup Instructions

### Prerequisites
- Windows 10/11 (64-bit)
- Git 2.56.0 or higher
- Python 3.14.10 installed
- PowerShell 7 or Windows PowerShell 5.1

### Workspace Verification
1. Open PowerShell and navigate to the repository:
   ```powershell
   cd D:\TrustCart
   ```

2. Confirm the existing virtual environment:
   ```powershell
   .\.venv\Scripts\python.exe --version
   .\.venv\Scripts\pip.exe --version
   ```

3. Activate the virtual environment in PowerShell:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
   *(If script execution is disabled, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`)*

4. Environment Variables:
   - Copy `.env.example` to `.env` (do not commit `.env`):
     ```powershell
     Copy-Item .env.example .env
     ```
   - Populate `.env` with development credentials when Phase 1 commences.

---

## Agent Tooling & GSD Core

The engineering workspace incorporates **GSD Core** (`@opengsd/gsd-core`) to provide structured software design and delivery workflows.

- **Installed Version**: `v1.20.1` (MIT Licensed; see [`THIRD-PARTY-LICENSES.md`](THIRD-PARTY-LICENSES.md))
- **Scope & Runtime**: Local repository scope (`.agents/`), runtime: `antigravity`, mode: `full`.
- **Reproducible Installation**:
  To reproduce or restore the GSD Core toolset in a fresh workspace:
  ```powershell
  npx -y @opengsd/gsd-core@1.20.1 --antigravity --local
  ```
- **Local Governance & Safety**:
  - GSD-managed skills, agents, workflows, and hooks are version-controlled in `.agents/`.
  - Machine-local state (`.agents/mcp_config.json`, `.agents/gsd-install-state.json`, `.agents/gsd-migration-journal/`) is strictly excluded in `.gitignore`.
  - TrustCart-specific architectural rules and security review skills take absolute precedence over general GSD agents.

---

## Project Structure & Documentation

- [`AGENTS.md`](AGENTS.md): Agent rules of engagement and architectural invariants.
- [`TASK_GATES.md`](TASK_GATES.md): Complete phase roadmap, deliverables, and completion criteria.
- [`docs/architecture/`](docs/architecture/): System design, trust boundaries, and data flows.
- [`docs/decisions/`](docs/decisions/): Architecture Decision Records (ADRs).
- [`docs/security/`](docs/security/): Threat model and security mitigations.
- [`docs/quality/`](docs/quality/): Comprehensive test strategy.
- [`docs/planning/`](docs/planning/): Status tracking and handoff logs.

