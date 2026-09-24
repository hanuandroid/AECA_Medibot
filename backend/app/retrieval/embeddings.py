"""Embedding / reranking model singletons (fastembed, ONNX runtime, CPU-friendly).

* dense  : BAAI/bge-small-en-v1.5 (384-d, cosine) - semantic similarity
* sparse : Qdrant/bm25 - BM25 term frequencies; Qdrant applies IDF server-side
           (sparse vector config ``modifier=IDF``) which yields BM25 scoring
* rerank : cross-encoder ms-marco-MiniLM-L-6-v2 - scores (query, passage) jointly
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Sequence
from functools import lru_cache
from typing import TYPE_CHECKING

from qdrant_client import models

from app.config import get_settings

if TYPE_CHECKING:
    from fastembed import SparseTextEmbedding, TextEmbedding
    from fastembed.rerank.cross_encoder import TextCrossEncoder

logger = logging.getLogger(__name__)

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

_lock = threading.Lock()


def _cache_dir() -> str:
    path = get_settings().models_cache_dir
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


@lru_cache(maxsize=1)
def dense_model() -> TextEmbedding:
    from fastembed import TextEmbedding

    name = get_settings().dense_model
    logger.info("Loading dense embedding model %s", name)
    return TextEmbedding(name, cache_dir=_cache_dir())


@lru_cache(maxsize=1)
def sparse_model() -> SparseTextEmbedding:
    from fastembed import SparseTextEmbedding

    name = get_settings().sparse_model
    logger.info("Loading sparse (BM25) model %s", name)
    return SparseTextEmbedding(name, cache_dir=_cache_dir())


@lru_cache(maxsize=1)
def reranker_model() -> TextCrossEncoder:
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    name = get_settings().reranker_model
    logger.info("Loading cross-encoder reranker %s", name)
    return TextCrossEncoder(name, cache_dir=_cache_dir())


def dense_dim() -> int:
    return len(embed_query_dense("dimension probe"))


def embed_documents_dense(texts: Sequence[str]) -> list[list[float]]:
    with _lock:
        return [v.tolist() for v in dense_model().passage_embed(list(texts))]


def embed_documents_sparse(texts: Sequence[str]) -> list[models.SparseVector]:
    with _lock:
        return [
            models.SparseVector(indices=e.indices.tolist(), values=e.values.tolist())
            for e in sparse_model().passage_embed(list(texts))
        ]


def embed_query_dense(text: str) -> list[float]:
    with _lock:
        return next(iter(dense_model().query_embed(text))).tolist()


def embed_query_sparse(text: str) -> models.SparseVector:
    with _lock:
        e = next(iter(sparse_model().query_embed(text)))
    return models.SparseVector(indices=e.indices.tolist(), values=e.values.tolist())


def cross_encoder_scores(query: str, passages: Sequence[str]) -> list[float]:
    if not passages:
        return []
    with _lock:
        return [float(s) for s in reranker_model().rerank(query, list(passages))]


def warmup() -> None:
    """Load all models once (first run downloads them)."""
    embed_query_dense("warmup")
    embed_query_sparse("warmup")
    cross_encoder_scores("warmup", ["warmup"])
