# Assignment Compliance

Mapped against `Medibot_Assignment_Instruction.md`. Evidence = a test in `backend/tests` (last full
run: **217 passed, 0 skipped**, including 19 live-LLM tests with `gpt-4o-mini`) or a recorded run
artifact. Status: PASS / PARTIAL / FAIL.

## RBAC at the vector store retrieval layer — 25%

| Requirement | Implementation | File | Test / evidence | Status |
|---|---|---|---|---|
| 5 roles with the specified access matrix | `Role`, `ROLE_COLLECTIONS` | `backend/app/rbac.py` | `test_rbac.py::test_access_matrix_matches_assignment` | PASS |
| `access_roles` metadata filter applied at query level on every retrieval | `build_access_filter` on both prefetches + outer query; also dense/BM25 baselines | `app/rbac.py`, `app/retrieval/hybrid.py` | `test_rbac_adversarial.py::test_every_qdrant_query_carries_the_role_filter`, `test_rbac.py::test_access_filter_structure` | PASS |
| Restricted chunks never returned, not filtered after the fact | Filter inside Qdrant; post-retrieval tripwire only raises | `app/retrieval/hybrid.py` | `test_exhaustive_scroll_with_role_filter_never_leaks` (whole index per role) | PASS |
| Adversarial prompts cannot surface restricted documents | — | — | `test_attack_returns_no_restricted_chunks` (8 attacks × hybrid/dense/BM25, limit 50) + admin control; `test_chat_blocks_restricted_chunks_even_if_router_is_fooled`; `test_live_adversarial_prompts` (real LLM) | PASS |
| ≥3 adversarial prompts documented in README with screenshots | README § Adversarial prompt tests | `README.md`, `docs/screenshots/01–03*.png` | screenshots captured from the running stack | PASS |
| Role from authenticated session, never from client | JWT role claim; `ChatRequest` forbids extra fields | `app/auth/tokens.py`, `app/api/schemas.py`, `app/api/deps.py` | `test_api.py::test_chat_rejects_client_supplied_role`, `test_auth.py` (forged, `alg=none`, expired, unknown role) | PASS |

## Structural ingestion & hierarchical chunking — 20%

| Requirement | Implementation | File | Test / evidence | Status |
|---|---|---|---|---|
| Parse PDF + Markdown with structural awareness (headings, tables, code) | Docling `DocumentConverter` (layout + TableFormer, MD backend) | `app/ingestion/parser.py` | `data/ingestion_run.log`; `test_all_chunk_types_present_and_tables_preserved` | PASS |
| Hierarchical split first, token-aware second | Docling `HybridChunker` (bge tokenizer, 384 tokens, merge_peers, repeat table header) + PDF heading re-levelling | `app/ingestion/chunker.py`, `parser.py` | `test_chunker.py::test_assign_heading_levels_restores_hierarchy` | PASS |
| Chunk embedded text carries parent section heading | `contextualize()` → heading path + body | `app/ingestion/chunker.py` | `test_embedded_text_carries_parent_heading_context`, `test_chunks_carry_parent_heading_context_and_metadata` | PASS |
| Tables not flattened | Markdown table serializer | `app/ingestion/chunker.py` | `test_all_chunk_types_present_and_tables_preserved` (Vancomycin row intact) | PASS |
| Metadata: source_document, collection, access_roles, section_title, chunk_type | `ChunkRecord` (validated; roles derived from matrix) | `app/ingestion/metadata.py` | `test_every_chunk_has_the_required_metadata`, `test_every_source_document_is_indexed_in_its_folder_collection` | PASS |
| Standalone ingestion script | `python -m app.ingestion` | `app/ingestion/__main__.py` | run log: 12 docs → 329 chunks | PASS |

## Hybrid RAG + reranking — 20%

| Requirement | Implementation | File | Test / evidence | Status |
|---|---|---|---|---|
| Dense + sparse (BM25) stored at index time | Named vectors `dense` + `bm25` (IDF modifier) | `app/retrieval/qdrant_store.py`, `app/ingestion/indexer.py` | `test_points_have_dense_and_sparse_vectors` | PASS |
| Queried together in a single query, not merged in app code | One `query_points` with 2 prefetches + `FusionQuery(RRF)` | `app/retrieval/hybrid.py` | `test_hybrid_query_is_one_fused_query_over_dense_and_sparse`, `test_hybrid_search_makes_exactly_one_qdrant_call` | PASS |
| Fused single ranked list | RRF → top-10 | `app/retrieval/hybrid.py` | `test_candidate_set_is_top_10_with_ranks` | PASS |
| Cross-encoder scores query+chunk jointly | fastembed `TextCrossEncoder` (`jina-reranker-v1-turbo-en`) | `app/retrieval/reranker.py` | `test_cross_encoder_scores_query_passage_pairs_jointly` | PASS |
| Broad candidate set (10) → narrow (3); only top chunks in LLM prompt | `rerank(top_k=3)`; prompt built from `used_chunks` | `app/rag/pipeline.py` | `test_only_reranked_top_k_reach_the_llm`, `test_chat_hybrid_answer_has_real_sources` | PASS |
| Retrieval quality demonstrably better than dense-only | Evaluation script | `scripts/evaluate_retrieval.py` | `docs/RAG_EVALUATION.md`: MRR dense 0.849 → hybrid 0.889 → hybrid+rerank 0.933; Hit@3 13/15 → 15/15 | PASS |
| Cloud-hosted LLM for generation | Provider-agnostic client (OpenAI-compatible / Anthropic) | `app/llm/client.py` | `test_live_hybrid_answer` | PASS |

## SQL RAG — 15%

| Requirement | Implementation | File | Test / evidence | Status |
|---|---|---|---|---|
| Schema inspected; real columns/values | live schema description | `app/sql_rag/schema.py`, `docs/DATABASE_SCHEMA.md` | `test_schema_description_comes_from_the_live_database` | PASS |
| `sql_rag_chain(question: str) -> str` plain function | — | `app/sql_rag/chain.py` | `test_sql_rag_chain_is_a_plain_function_with_the_required_signature` | PASS |
| Step 1 LLM → SQL | `generate_sql` | `app/sql_rag/chain.py` | live tests | PASS |
| Step 2 clean output → SQL only | `extract_sql` + `validate_sql` (read-only) | `app/sql_rag/extract.py`, `validate.py` | `test_sql_extract.py` (11 formats, 15 unsafe statements) | PASS |
| Step 3 execute, pass result to LLM → answer | `execute_readonly` (mode=ro, query_only) + `answer_from_result` | `app/sql_rag/executor.py`, `chain.py` | `test_three_steps_with_fenced_llm_output`, `test_executor_is_read_only_even_if_validation_bypassed` | PASS |
| Works for ≥4 analytical questions | — | — | `test_sql_rag_live_llm` × 8 (real LLM, compared with reference SQL) + `test_sql_rag_chain_returns_string_live`; outputs in README | PASS |
| Only billing_executive and admin | `can_use_sql` gate | `app/rbac.py`, `app/api/chat_service.py` | `test_chat_sql_denied_for_non_analytical_roles`, `test_chat_sql_rag_for_permitted_roles` | PASS |

## FastAPI backend — 10%

| Requirement | Implementation | File | Test / evidence | Status |
|---|---|---|---|---|
| `POST /login` → role-tagged token | JWT (`sub`, `role`, `exp`) | `app/api/main.py` | `test_login_returns_role_tagged_token`, `test_login_failures` | PASS |
| `POST /chat` routes SQL vs hybrid, RBAC server-side | router + orchestration | `app/router.py`, `app/api/chat_service.py` | `test_api.py` chat tests, `test_router.py` (incl. live) | PASS |
| Response: answer, sources, retrieval_type, role | `ChatResponse` | `app/api/schemas.py` | `test_chat_hybrid_answer_has_real_sources`, `test_live_sql_answer` | PASS |
| `GET /collections/{role}` | own role / admin any | `app/api/main.py` | `test_collections_*` | PASS |
| `GET /health` | Qdrant + LLM + DB status | `app/api/main.py` | `test_health`; live `curl` | PASS |

## Next.js frontend — 5%

| Requirement | Implementation | File | Test / evidence | Status |
|---|---|---|---|---|
| Login with 5 demo accounts | login page | `frontend/app/page.tsx` | Playwright run: login via form for all tested roles; `docs/screenshots/00_login.png` | PASS |
| Answer + source citations (document, section) | `MessageView` | `frontend/components/MessageView.tsx` | `docs/screenshots/04_nurse_hybrid_answer.png` | PASS |
| Role + accessible collections badge/sidebar | `AccessPanel` (from `/collections/{role}`) | `frontend/components/AccessPanel.tsx` | all screenshots | PASS |
| Retrieval type label per response | `RetrievalBadge` | `MessageView.tsx` | screenshots 04/05 | PASS |
| Clear RBAC refusal message | denial box | `MessageView.tsx` | screenshots 01–03, 06 | PASS |
| Builds cleanly | — | — | `npm run lint`, `npm run typecheck`, `npm run build` | PASS |

## Code quality & README — 5%

| Requirement | Evidence | Status |
|---|---|---|
| Modular code, typed, linted | `ruff check` clean, `ruff format --check` clean, `mypy app` clean | PASS |
| README: setup, API keys, run backend/frontend, demo creds | `README.md` §Setup, §Demo users | PASS |
| Architecture diagram login → RBAC → Hybrid/SQL → response | `README.md` §Architecture (Mermaid) | PASS |
| ≥3 adversarial examples with screenshots | `README.md` §Adversarial prompt tests | PASS |
| Tool substitutions documented | `README.md` §Tool substitutions | PASS |

## Submission items outside the code

| Item | Status |
|---|---|
| Public GitHub repository | **Not done** — the folder is not yet a git repository; needs the owner's GitHub account |
| Submit link on the assignment dashboard | **Not done** (owner action) |
