# CLAUDE.md — MediBot

## Project

MediBot — Advanced RAG Healthcare Knowledge Assistant for MediAssist Health Network.
Hybrid (dense + BM25) retrieval over Qdrant with RBAC enforced inside every Qdrant query,
cross-encoder reranking, SQL RAG over `mediassist.db`, a FastAPI backend and a Next.js frontend.

## Source of Truth

`Medibot_Assignment_Instruction.md` (also shipped as `MediBot_Assignment_Instructions.pdf`).
Where this file and the assignment disagree, the assignment wins.

## Architecture

```text
Next.js (frontend/)
   |
   v
FastAPI (backend/app/api)
   |
   +---- Authentication / RBAC        (app/auth, app/rbac.py)
   |
   +---- Query Router                 (app/router.py)
             |
             +---- SQL RAG            (app/sql_rag)          billing_executive, admin only
             |
             +---- Hybrid RAG         (app/rag, app/retrieval)
                       |
                       +---- Qdrant RBAC filter   (app/rbac.py -> build_access_filter)
                       +---- Dense retrieval      (fastembed BAAI/bge-small-en-v1.5)
                       +---- Sparse retrieval     (fastembed Qdrant/bm25 + IDF modifier)
                       +---- Fusion               (Qdrant-native RRF via query_points prefetch)
                       +---- Cross Encoder        (top-10 -> top-3)
                       +---- LLM                  (app/llm, provider via env)
```

Ingestion (`backend/app/ingestion`, run with `python -m app.ingestion`) is an offline pipeline:
Docling -> HybridChunker (hierarchical + token-aware) -> metadata -> dense + sparse vectors -> Qdrant.

## Mandatory Security Rule

RBAC MUST be enforced at the vector database retrieval layer.

Never retrieve unrestricted documents and filter them afterwards.

Every Qdrant retrieval operation must contain the appropriate access filter
(`access_roles` contains the authenticated role), on every prefetch and on the top-level query.

The LLM must never receive unauthorized chunks.

The role always comes from the verified JWT — never from the request body.

## Coding Rules

- Prefer simple modular architecture.
- Avoid unnecessary abstractions.
- Use type hints.
- Keep business logic testable.
- Keep secrets in environment variables.
- Never commit API keys.
- Never hard-code production credentials.
- Validate external inputs.
- Never execute arbitrary LLM-generated SQL.
- SQL must be restricted to safe read-only operations.
- Do not bypass RBAC.
- Do not remove tests merely to make them pass.
- Do not hard-code responses for assignment examples.
- Do not fake retrieval results.
- Do not create fake source citations.

Detailed rules live in `.claude/rules/` (architecture, security, rag, testing, python, frontend, sql).
Task playbooks live in `.claude/skills/`; specialised agents in `.claude/agents/`.

## Testing Rules

Every major component must have tests (`backend/tests`). Minimum coverage:

- authentication
- role permissions
- collection access
- Qdrant RBAC filter generation
- adversarial RBAC attempts
- document metadata
- SQL RAG
- SQL extraction
- query routing
- hybrid retrieval
- reranking
- API endpoints

Tests marked `llm` need a real LLM API key; tests marked `index` need the ingested Qdrant index.
They are skipped (never faked) when those are unavailable.

## Commands

```bash
# backend (from backend/)
uv venv --python 3.13 .venv
uv pip install -e ".[ingest,dev]"
python -m app.ingestion                 # build the Qdrant index
uvicorn app.api.main:app --reload       # http://localhost:8000
pytest                                  # tests
ruff check . && mypy app                # lint + types
python -m scripts.evaluate_retrieval    # dense-only vs hybrid vs hybrid+rerank

# frontend (from frontend/)
npm install && npm run dev              # http://localhost:3000
npm run lint && npm run typecheck
```

## Verification Rule

Before declaring the project complete:

```text
run tests
run lint
run type checks where available
run backend
run frontend
test ingestion
test retrieval
test SQL RAG
test RBAC
test adversarial prompts
test frontend login
```

Progress is tracked in `docs/PROGRESS.md`; requirement mapping in `docs/ASSIGNMENT_COMPLIANCE.md`.
