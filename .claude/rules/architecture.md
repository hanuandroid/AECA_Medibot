# Architecture Rules

## Module layout (backend/app)

| Module | Responsibility | May depend on |
|---|---|---|
| `config.py` | Settings from environment (`pydantic-settings`) | — |
| `rbac.py` | Role → collections matrix, Qdrant filter builder | `config` |
| `auth/` | Demo users, password check, JWT issue/verify | `config`, `rbac` |
| `ingestion/` | Offline: Docling parse → chunk → metadata → embed → index | `config`, `rbac`, `retrieval.embeddings` |
| `retrieval/` | Embedding models, Qdrant hybrid search, cross-encoder reranker | `config`, `rbac` |
| `llm/` | Provider-agnostic chat completion client + prompts | `config` |
| `rag/` | Hybrid RAG answer pipeline (retrieve → rerank → generate) | `retrieval`, `llm`, `rbac` |
| `sql_rag/` | `sql_rag_chain` (generate → extract → validate → execute → answer) | `llm`, `config` |
| `router.py` | Classify question: SQL vs document RAG, target collections | `llm`, `rbac` |
| `api/` | FastAPI app, schemas, dependencies, endpoints | everything above |

## Dependency direction

`api` → `router`/`rag`/`sql_rag` → `retrieval`/`llm` → `rbac`/`config`.
Lower layers never import from `api`. `ingestion` is never imported by the API at request time.

## Principles

- Ingestion, retrieval, reranking, LLM generation and the API are separate modules with
  plain-function / small-class interfaces so each can be unit-tested in isolation.
- Heavy resources (embedding models, cross-encoder, Qdrant client, LLM client) are created once
  and injected (FastAPI dependencies / module-level lazy singletons) so tests can substitute them.
- All configuration comes from environment variables (see `backend/.env.example`). No paths,
  URLs, model names or secrets are hard-coded in business logic.
- No framework-of-frameworks: no LangChain / LlamaIndex orchestration layers. Direct SDK calls.
- Keep coupling low: the API layer passes the authenticated role explicitly into retrieval;
  retrieval never reads request state.
