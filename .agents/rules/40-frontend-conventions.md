---
trigger: glob
globs: "**/*.html, **/*.css, **/*.js"
description: "Frontend conventions for TrustCart templates, stylesheets and JavaScript."
---

# 40 - Frontend Conventions

1. **Tech Stack**: Vanilla JavaScript (ES6+), standard modern CSS, semantic HTML5, and server-rendered Django templates. No heavy frontend frameworks (React, Vue, etc.).
2. **Security & Data Sanitization**:
   - Always rely on Django's auto-escaping in templates. Never use `|safe` on unverified external product descriptions or LLM outputs.
   - Sanitize dynamic DOM insertions against XSS. Avoid `element.innerHTML` with untrusted data; use `textContent` or controlled template clones.
3. **Approval Presentation**:
   - The user approval UI must explicitly render the binding details: exact product title, selected variant, quantity, unit price, total price, currency (USD), demo merchant disclosure, and approval expiration countdown.
   - Require positive user interaction (e.g. distinct confirmation button) before triggering the approval token generation.
4. **Resilient Network Handling**:
   - Disable submission buttons on click to prevent double-submissions.
   - Display clear, non-technical error messages when validation fails or backend policies fail closed.
   - Never embed API keys, secrets, or raw internal IDs in client-side scripts.

