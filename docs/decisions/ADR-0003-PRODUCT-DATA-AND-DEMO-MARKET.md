# ADR-0003: Product Data Integration and Demo Market Scope

## Status
Accepted

## Context
TrustCart needs real-world product catalog data to demonstrate authentic comparison and purchase proposal generation. However, settling payments with arbitrary third-party retailers in a Sandbox hackathon environment is impossible without direct merchant merchant-of-record agreements. Furthermore, multi-currency conversions introduce floating-point drift and exchange rate risks.

## Decision
1. **Product Data Provider**:
   - Integrate Channel3 API for real product search, specifications, pricing, and availability.
   - All product payloads are ingested as untrusted external evidence with provenance metadata: source URL, merchant name, retrieval timestamp, currency, and variant identifier.
2. **Demo Market Boundary**:
   - Scope the hackathon MVP strictly to the United States market with transactions in US Dollars (`USD`).
   - Cross-border currency conversion is excluded from MVP scope to prevent exchange rate volatility and precision edge cases.
3. **Controlled Demo Merchant / Payee**:
   - The PayPal Sandbox checkout flow explicitly settles with a controlled demo merchant/payee account owned by the test team.
   - The user interface must transparently disclose: *"Demo Sandbox Transaction: Payment settles with TrustCart Demo Merchant for evaluation purposes."*
   - Never claim or mislead the user that funds are settling directly with third-party retailers discovered via Channel3.
4. **Fail-Closed on Product Discrepancies**:
   - If Channel3 returns ambiguous stock, missing prices, or non-USD currencies, the policy engine fails closed and excludes the item from purchase proposals.

## Consequences
- **Positive**: Compliant, ethical, transparent demonstration that showcases end-to-end payment capture without violating retail merchant terms or deceiving shoppers.
- **Negative**: The user must understand that physical shipment will not occur from the discovered retailer.

## Assumptions & Unresolved Questions
- **Assumption**: Channel3 provides API access and test query allowances for US market products during the hackathon timeline.
- **Assumption**: Channel3 schema delivers structured numerical or clean string prices easily convertible to `Decimal`.
- **Unresolved Question**: In the event of Channel3 rate limiting or network downtime, will mock fixtures be sufficient for local development and offline testing? *(Answer: Yes, recorded fixtures will be established in Phase P3).*

