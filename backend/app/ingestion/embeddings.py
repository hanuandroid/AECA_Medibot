"""Batch vectorisation of chunks for indexing: dense + sparse from the same contextualised text."""

from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import models

from app.ingestion.metadata import ChunkRecord
from app.retrieval.embeddings import embed_documents_dense, embed_documents_sparse


@dataclass
class ChunkVectors:
    dense: list[float]
    sparse: models.SparseVector


def vectorise(records: list[ChunkRecord]) -> list[ChunkVectors]:
    texts = [r.embed_text for r in records]
    dense = embed_documents_dense(texts)
    sparse = embed_documents_sparse(texts)
    return [ChunkVectors(dense=d, sparse=s) for d, s in zip(dense, sparse, strict=True)]
