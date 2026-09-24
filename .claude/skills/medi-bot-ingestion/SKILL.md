---
name: medi-bot-ingestion
description: How MediBot ingests PDF/Markdown with Docling, chunks hierarchically with HybridChunker, attaches the required metadata and indexes dense+sparse vectors in Qdrant. Use when changing backend/app/ingestion or re-indexing.
---

# MediBot Ingestion

```text
mediassist_data/<collection>/*.pdf|*.md
   ↓ loader.py     discover files; collection = parent folder name
   ↓ parser.py     Docling DocumentConverter (PDF: layout + TableFormer; MD: markdown backend)
   ↓ chunker.py    HybridChunker(tokenizer=bge-small tokenizer, max_tokens, merge_peers=True)
   │               - hierarchical: splits on document structure first
   │               - token-aware: splits oversized / merges undersized peers
   │               - tables serialised as Markdown (MarkdownTableSerializer)
   ↓ metadata.py   source_document, collection, access_roles, section_title, chunk_type,
   │               heading_path, page_numbers, chunk_index, text, embed_text
   ↓ embeddings    dense (bge-small) + sparse (Qdrant/bm25) on embed_text
   ↓ indexer.py    recreate collection, payload indexes, upsert points (uuid5 ids)
```

## Chunk metadata (all mandatory)

| field | source |
|---|---|
| `source_document` | file name, e.g. `drug_formulary.pdf` |
| `collection` | folder name ∈ general, clinical, nursing, billing, equipment |
| `access_roles` | `rbac.roles_for_collection(collection)` |
| `section_title` | deepest heading in `chunk.meta.headings` (fallback: document title) |
| `chunk_type` | `table` if any doc item is a TABLE, `code` if CODE, `heading` if only headers/titles, else `text` |

## Rules
- `embed_text = chunker.contextualize(chunk)` → heading path + body. Store it and embed it.
- Never drop tables; never split a table row across chunks when avoidable (HybridChunker keeps
  table items whole and repeats headers when a table must be split).
- Deterministic point ids (`uuid5(source_document + chunk_index)`) so re-ingestion is idempotent.
- Run once standalone (`python -m app.ingestion`) — first run downloads Docling models.
- Write a chunk summary (`backend/data/chunks_preview.jsonl`) for inspection/evaluation.

## Verify
`pytest tests/test_ingestion_metadata.py` (checks every point in Qdrant has the full schema,
valid collection/role mapping, headings present, tables present in clinical docs).
