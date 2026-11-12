---
trigger: always_on
description: Mandatory consultation and maintenance of the Graphify knowledge graph at graphify-out/.
---

# Graphify Knowledge Graph Rules

TrustCart maintains an AST-extracted code knowledge graph at `graphify-out/graph.json` with automatic lifecycle synchronization.

## Mandatory Operating Requirements:
1. **Consult Graphify Skill & Graph First**: Consult the Graphify skill and inspect the knowledge graph before repository-related investigation, architectural design, implementation, or refactoring.
2. **Path & Caller Identification**: Use the graph (`graphify path`, `graphify explain`, `graphify query`) to identify relevant files, callers, dependencies, and execution paths before modifying interconnected components.
3. **Query Targeted Relationships**: Target specific relationships across domain boundaries (e.g., `contracts` -> `catalog` -> `policies` -> `orders` -> `payments`) rather than relying on unstructured text searches or guessing.
4. **Guide, Not Replace, Source Inspection**: Use graph query results to guide and focus source-code inspection; the graph identifies where to look, but actual source code remains authoritative.
5. **Distinguish Relationship Types**: Clearly distinguish deterministic AST relationships (`[EXTRACTED]`) from probabilistic or semantic associations (`[INFERRED]`).
6. **Verify Conclusions Against Code & Tests**: Verify all important architectural conclusions, interface assumptions, and data contracts against actual source code and automated tests.
7. **Ensure Automatic Refresh Succeeds**: After code modifications, verify that the automated Graphify lifecycle hook or `graphify update . --force` completes successfully.
8. **Honest Graph Freshness**: Never claim the graph is current if a background or manual update failed; inspect diagnostic logs in `.graphify-runtime/diagnostics.log` if an issue occurs.
9. **Zero Redundant Rebuilds**: Do not waste time rebuilding an unchanged graph; rely on fingerprint verification (`.graphify-runtime/last-indexed-source.sha256`) to skip redundant extractions.
10. **Manual Slash Workflow Fallback**: Retain the manual `/graphify` workflow (`.agents/workflows/graphify.md`) and standard CLI commands (`graphify path`, `graphify explain`, `graphify query`) as manual fallbacks whenever needed.
