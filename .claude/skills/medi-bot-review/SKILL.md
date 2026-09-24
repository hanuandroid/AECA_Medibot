---
name: medi-bot-review
description: Review the MediBot implementation against every requirement in Medibot_Assignment_Instruction.md and report gaps with evidence. Use before submission or after major changes.
---

# MediBot Assignment Review

1. Re-read `Medibot_Assignment_Instruction.md` fully.
2. For each requirement below, find the implementing file **and** a test or run log that proves
   it. No evidence → `PARTIAL` or `FAIL`.
3. Update `docs/ASSIGNMENT_COMPLIANCE.md` (Requirement | Implementation | File | Test | Status).

## Checklist (weight)

**RBAC at retrieval layer (25%)**
- [ ] `build_access_filter` used by every Qdrant query (grep `query_points`, `search`, `scroll`)
- [ ] filter on each prefetch + outer query
- [ ] role from JWT only; `ChatRequest` forbids extra fields
- [ ] ≥3 adversarial prompts tested at retrieval level and documented in README

**Structural ingestion (20%)**
- [ ] Docling for PDF + MD; HybridChunker (hierarchical + token-aware)
- [ ] heading context in embedded text
- [ ] all 5 metadata fields on every point; tables preserved

**Hybrid + rerank (20%)**
- [ ] dense + sparse stored at index time, one query with RRF
- [ ] top-10 → cross-encoder → top-3; only top-3 in prompt
- [ ] `docs/RAG_EVALUATION.md` shows dense-only vs hybrid vs reranked with real outputs

**SQL RAG (15%)**
- [ ] `sql_rag_chain(question: str) -> str` plain function with 3 explicit steps
- [ ] extraction handles fences/prefixes; read-only validation
- [ ] ≥4 analytical questions verified against real DB
- [ ] role gate billing_executive/admin

**FastAPI (10%)** — /login /chat /collections/{role} /health; sources in every response.

**Next.js (5%)** — login, role badge, collections, retrieval label, citations, RBAC refusal message.

**Code quality / README (5%)** — setup, API keys, demo creds, diagram, adversarial examples,
tool substitutions.

## Also check
- No fabricated metrics/citations; no hard-coded answers; secrets not committed.
- `pytest`, `ruff`, `mypy`, `npm run lint`, `npm run typecheck`, `npm run build` all pass.
