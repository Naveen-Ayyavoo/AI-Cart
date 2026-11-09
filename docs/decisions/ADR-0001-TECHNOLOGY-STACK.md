# ADR-0001: Technology Stack Selection

## Status
Accepted

## Context
TrustCart is being built for the PayPal AI Hackathon on a Windows 64-bit host with Python 3.14.10, Antigravity IDE 2.6.0, Git 2.56.0, and pip 26.3. The project requires a reliable, rapid-development backend, deterministic state management, strict mathematical precision for currency, and safe integration with Gemini and PayPal.

## Decision
1. **Language & Runtime**: Python 3.14.10 running in an isolated virtual environment (`.venv`). Development is strictly native Windows PowerShell (no WSL).
2. **Backend Framework**: Django 6.1 (to be installed and verified in Phase 1).
   - *Rationale*: Django provides mature ORM transaction management (`transaction.atomic`), built-in CSRF protection, secure session management, and robust template rendering without requiring heavyweight Node.js toolchains.
3. **Database**: SQLite for initial local development and prototyping.
   - *Rationale*: Zero-configuration, file-based, supported out of the box by Django, and sufficient for hackathon proof-of-concept workflows.
4. **Frontend Architecture**: Server-rendered Django Templates with Semantic HTML5, CSS, and Vanilla JavaScript (ES6+).
   - *Rationale*: Eliminates frontend build steps and npm dependency vulnerabilities. Keeps server-side rendering authoritative over financial data presentation.
5. **AI / LLM Integration**: Google Gemini API (via Google AI Studio).
   - *Rationale*: Advanced reasoning, structured JSON output capabilities, and low latency for contract extraction and product trade-off summarization.
6. **Code Quality & Linting**: Ruff for formatting and linting. Microsoft Python and Pylance for static typing.

## Consequences
- **Positive**: Clean, reproducible architecture with minimal external build dependencies; robust database transaction support; fast development cycle.
- **Negative**: Django 6.1 is a very modern release and must be tested for compatibility with third-party libraries under Python 3.14.

## Assumptions & Unresolved Questions
- **Assumption**: Django 6.1 will install cleanly in Python 3.14 without binary wheel compilation issues on Windows 64-bit. *(Must be formally verified when dependencies are installed in Phase 1).*
- **Assumption**: SQLite write concurrency is adequate for single-user hackathon demonstration flows.
- **Unresolved Question**: Should deployment require PostgreSQL if deployed to a hosted cloud environment in Phase P8? *(Resolved by ADR-0004: All deployment and demonstration will be local and zero-spend; paid cloud hosting and managed cloud databases are prohibited).*

