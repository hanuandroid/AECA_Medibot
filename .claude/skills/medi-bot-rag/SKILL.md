---
name: medi-bot-rag
description: How MediBot implements hybrid retrieval (dense + BM25 in one Qdrant query with RRF fusion), cross-encoder reranking and source-preserving answer generation. Use when changing backend/app/retrieval or backend/app/rag.
---

# MediBot Hybrid RAG

## Pipeline

```text
question
  ├─ dense embedding   (fastembed TextEmbedding, BAAI/bge-small-en-v1.5, 384-d, cosine)
  └─ sparse BM25 vector (fastembed SparseTextEmbedding, Qdrant/bm25; collection uses Modifier.IDF)
        ↓
Qdrant query_points  (ONE call)
  prefetch = [Prefetch(dense, filter=rbac, limit=N), Prefetch(bm25, filter=rbac, limit=N)]
  query    = FusionQuery(fusion=Fusion.RRF)
  query_filter = rbac, limit = RETRIEVAL_CANDIDATES (10)
        ↓
top-10 candidates (fusion rank kept)
        ↓
Cross-encoder (fastembed TextCrossEncoder, Xenova/ms-marco-MiniLM-L-6-v2)
scores (query, chunk_text) jointly → sort → top-3 (RERANK_TOP_K)
        ↓
LLM prompt contains ONLY the top-3, numbered [1]..[3]
        ↓
answer + sources (built from those 3 chunks' payloads)
```

## Rules
1. Dense and sparse vectors are both written at index time (named vectors `dense`, `bm25`).
2. Never run two searches and merge in Python for the production path. (The evaluation script
   runs dense-only as a *baseline* — clearly labelled.)
3. Every Qdrant call gets `build_access_filter(role)` (see `medi-bot-rbac`).
4. Documents are embedded with the same `contextualize()` text used for BM25 — heading path + body.
   Query embedding uses the model's query prefix handling from fastembed (`query_embed`).
5. Keep `initial_rank`, `fusion_score`, `rerank_score`, `final_rank` on each `RetrievedChunk` and
   log them at DEBUG/INFO so the rerank effect can be demonstrated.
6. Sources are never synthesised — they are the payloads of the chunks sent to the LLM,
   de-duplicated by (source_document, section_title).

## Key files
- `backend/app/retrieval/embeddings.py` — model singletons (dense, sparse, reranker)
- `backend/app/retrieval/hybrid.py` — `hybrid_search`, `dense_search` (baseline)
- `backend/app/retrieval/reranker.py` — `rerank`
- `backend/app/rag/pipeline.py` — `answer_with_documents`
- `backend/scripts/evaluate_retrieval.py` — dense vs hybrid vs hybrid+rerank report

## Verify
`pytest tests/test_hybrid_retrieval.py tests/test_reranker.py tests/test_rbac_adversarial.py`
