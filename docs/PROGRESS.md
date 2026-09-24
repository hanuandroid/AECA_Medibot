# Progress Log

| Phase | Status | Completed | Remaining | Tests | Known issues | Next step |
|---|---|---|---|---|---|---|
| 0 Audit | ✅ Done | `docs/IMPLEMENTATION_AUDIT.md` | – | – | – | Framework |
| 1 Claude framework | ✅ Done | `CLAUDE.md`, 7 rules, 6 skills, 8 agents | – | – | – | Data inspection |
| 3 Data inspection | ✅ Done | Docs mapped to collections; `docs/DATABASE_SCHEMA.md` | – | `test_sql_rag.py::test_schema_*` | Data is 2024-only → `SQL_AS_OF_DATE` | Ingestion |
| 4 Ingestion | ✅ Done | Docling + heading re-levelling + HybridChunker + metadata; 12 docs → 329 chunks | – | `test_chunker.py`, `test_ingestion_metadata.py` | Heading levels inferred from font size (heuristic) | Qdrant |
| 5 Qdrant hybrid | ✅ Done | Named dense + sparse (IDF) vectors, payload indexes, single RRF query | – | `test_hybrid_retrieval.py` | RRF ties can reorder equal-score candidates between runs | RBAC |
| 6 RBAC | ✅ Done | Filter on every prefetch + outer query; tripwire; JWT role | – | `test_rbac.py`, `test_rbac_adversarial.py` (8 attacks × 3 search modes) | – | Rerank |
| 7 Reranking | ✅ Done | Cross-encoder top-10 → top-3; 3 models compared | – | `test_reranker.py` | – | RAG answer |
| 8 RAG answering | ✅ Done | Grounded prompt with citations + safety rules | – | `test_reranker.py::test_only_reranked_top_k_reach_the_llm`, `test_api.py` (llm) | – | Router |
| 9 Router | ✅ Done | LLM JSON router + heuristic fallback | – | `test_router.py` | – | SQL RAG |
| 10 SQL RAG | ✅ Done | `sql_rag_chain` 3 steps, validation, read-only exec, 1 repair retry | – | `test_sql_extract.py`, `test_sql_rag.py` | – | API |
| 11 FastAPI | ✅ Done | 4 endpoints, denial UX, rerank details in response | – | `test_api.py` | – | Frontend |
| 13 Next.js | ✅ Done | Login, chat, access sidebar, badges, citations, denial notice, rerank table | – | lint + typecheck + build | – | Tests |
| 14–16 Tests / eval | ✅ Done | 210 backend tests; `docs/RAG_EVALUATION.md` | – | 210 passed | – | README |
| 17 README | ✅ Done | Setup, architecture, RBAC, adversarial table + screenshots, hybrid/rerank/SQL sections with live outputs, substitutions | – | – | – | – |
| 18 Compliance | ✅ Done | `docs/ASSIGNMENT_COMPLIANCE.md` | Public GitHub repo + submission (owner) | – | – | – |
| 19 Final verification | ✅ Done | 217 passed (incl. 19 live LLM); ruff/format/mypy clean; frontend lint/typecheck/build; ingestion; live backend + UI via Playwright | – | 217/217 | – | Push to GitHub |

LLM key blocker resolved 2026-09-24 (valid OpenAI key; `gpt-4o-mini`). Two live SQL tests initially
failed only on answer wording ("Orthopaedics" vs "orthopaedics", "No claims" for 0) — the SQL
results were correct; the text match was made case-insensitive and accepts no/none/zero for 0.

**Cross-verification against the assignment (2026-09-24):** 20 end-to-end scenarios traced to
specific assignment lines (security example, IV cannula, both SQL examples, patient category
counts, admin access to all 5 collections, SQL denial for doctor/technician, …) all passed with the
real LLM. The run exposed an intermittent bug — the LLM read "last month" as the as-of month — which
the zero-valued reference question could not detect. Fixed by computing date windows in Python
(`relative_date_windows`) and adding discriminating regression tests (9 vs 4, 7 vs 9).
