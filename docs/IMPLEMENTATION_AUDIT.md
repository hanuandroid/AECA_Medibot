# Implementation Audit (Phase 0)

Audit performed before implementation, on 2026-09-23. Working directory:
`E:\codebasics\code\Medibot_Assignment` (not a git repository).

## 1. Repository structure at audit time

```text
Medibot_Assignment/
├── Medibot_Assignment_Instruction.md     # assignment (source of truth)
├── MediBot_Assignment_Instructions.pdf   # same assignment as PDF
├── prompt_doc/1 prompt.md                # implementation brief
└── mediassist_data/
    ├── billing/     billing_codes.pdf, claim_submission_guide.md
    ├── clinical/    diagnostic_reference.pdf, drug_formulary.pdf, treatment_protocols.pdf
    ├── equipment/   equipment_manual.pdf
    ├── general/     code_of_conduct.pdf, general_faqs.pdf, leave_policy.pdf, staff_handbook.pdf
    ├── nursing/     icu_nursing_procedures.pdf, infection_control.pdf
    └── db/          mediassist.db
```

## 2. Existing functionality

None. No backend, frontend, tests, Docker configuration, environment files or vector-database
configuration existed — only the assignment, the brief and the dataset.

| Item | Found |
|---|---|
| Backend / frontend / tests | none |
| Python environment | system Python 3.14.2 and 3.13 (via `py`), `uv` 0.12 available |
| Package managers | uv, npm 11, pnpm 10 |
| Node | v24 |
| Docker | Docker Desktop installed but not running (started during the audit) |
| GPU | none (CPU-only → ONNX/fastembed models chosen) |
| LLM API keys in environment | none |
| Env files | none |

## 3. Dataset findings

- 12 documents (11 PDF + 1 Markdown), already organised in one folder per collection, so the
  folder name is used as the `collection` value.
- The PDFs are digitally generated (no OCR needed), contain many tables (drug formulary, fault
  codes, ICD codes, reference ranges) and a clear visual heading hierarchy.
- **Docling reports every PDF heading at level 1** — the hierarchy (e.g. "Fault codes" under
  four different devices) is lost unless reconstructed (see §5).
- `mediassist.db`: tables `claims` (85 rows) and `maintenance_tickets` (78 rows); all dates in
  2024 — see `docs/DATABASE_SCHEMA.md`.

## 4. Missing assignment requirements (all, at audit time)

Docling ingestion + hierarchical chunking; metadata schema; Qdrant with dense + sparse vectors;
hybrid fusion; RBAC filter at query level; cross-encoder reranking; SQL RAG (`sql_rag_chain`);
query router; FastAPI (`/login`, `/chat`, `/collections/{role}`, `/health`); JWT auth; Next.js UI;
tests incl. adversarial RBAC; README; evaluation evidence.

## 5. Technology decisions

| Concern | Decision | Why |
|---|---|---|
| Parsing | **Docling** `DocumentConverter` (PDF layout + TableFormer, Markdown backend) | Required; recognises headings, tables, code |
| Heading hierarchy | Re-level PDF headings by rendered heading height (bbox) | Docling flattens PDF heading levels; sizes are consistent per level in this corpus |
| Chunking | **Docling HybridChunker** (hierarchical, then token-aware with the bge tokenizer, 384 tokens), Markdown table serialiser | Required structure-first chunking; tables stay tables |
| Vector DB | **Qdrant** server (Docker) — embedded local mode supported via `QDRANT_PATH` | Required; native hybrid query + payload filters |
| Dense | fastembed `BAAI/bge-small-en-v1.5` (384-d) | Strong small model, CPU/ONNX |
| Sparse | fastembed `Qdrant/bm25` + Qdrant `Modifier.IDF` | Real BM25 inside Qdrant |
| Fusion | Qdrant `query_points` with two `Prefetch` + `FusionQuery(RRF)` | Single query, as the assignment requires |
| Reranker | fastembed cross-encoder `jinaai/jina-reranker-v1-turbo-en` | Best of three evaluated (see `docs/RAG_EVALUATION.md`, README) |
| LLM | Provider-agnostic client: OpenAI-compatible (OpenAI/Groq/Gemini/OpenRouter) or Anthropic, via env | Cloud LLM required; provider not hard-coded |
| SQL safety | extract → sqlglot validation (single SELECT, allow-listed tables) → read-only SQLite URI + `query_only` | Never execute raw LLM output |
| API | FastAPI + Pydantic v2, JWT (HS256) | Required |
| Frontend | Next.js 16 (App Router) + TypeScript, plain CSS modules | Required; minimal dependencies |
| Orchestration frameworks | none (no LangChain/LlamaIndex) | Fewer abstractions, easier to prove RBAC placement |

## 6. Risks (and mitigations)

| Risk | Mitigation |
|---|---|
| RBAC bypass through prompt injection | Filter is built from the JWT role and attached to every Qdrant call (each prefetch + outer query); tripwire raises if an unauthorised chunk ever appears; tests at retrieval level |
| Client-supplied role | `ChatRequest` forbids extra fields; role only from verified JWT |
| Lost heading context in chunks | Heading re-levelling + `contextualize()` embed text; tests on hierarchy |
| LLM-generated destructive SQL | Validation + read-only connection (two independent guards), tests with destructive SQL |
| Relative dates vs 2024-only data | Configurable `SQL_AS_OF_DATE`, default = latest DB date, stated in prompt |
| No LLM key available during build | LLM-dependent tests marked `llm` and skipped (never faked); extractive fallback in UI clearly labelled |
| Windows HF cache symlink errors | fastembed retries/falls back; model cache pinned to `backend/.cache` |

## 7. Implementation plan

Audit → Claude framework (`CLAUDE.md`, `.claude/`) → data inspection → ingestion → Qdrant →
RBAC → hybrid retrieval → reranking → SQL RAG → router → FastAPI → Next.js → tests → README →
compliance audit. Progress is logged in `docs/PROGRESS.md`.

## 8. Test strategy

- Unit: RBAC matrix/filter, JWT, SQL extraction/validation, router parsing/heuristics, chunk typing,
  heading hierarchy.
- Integration (real Qdrant + real models): metadata completeness, hybrid single-query structure,
  exact-term recall, reranking, adversarial prompts at retrieval level, exhaustive scroll per role,
  spy asserting the filter on every Qdrant call.
- API: TestClient on the real app; scripted LLM stub only where deterministic routing is needed
  (clearly named `StubLLM`).
- Live LLM (`-m llm`): router, SQL RAG on ≥4 analytical questions against reference SQL,
  end-to-end adversarial prompts.
