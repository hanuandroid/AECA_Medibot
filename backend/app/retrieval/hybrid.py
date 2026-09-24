"""Hybrid retrieval: dense + BM25 in ONE Qdrant query, fused with Reciprocal Rank Fusion.

The RBAC filter (``build_access_filter(role)``) is attached to both prefetch branches and to
the top-level query, so Qdrant only ever scores and returns chunks the role may read.
There is intentionally no code path here that queries Qdrant without the filter.
"""

from __future__ import annotations

import logging

from qdrant_client import QdrantClient, models

from app.config import get_settings
from app.rbac import ROLE_COLLECTIONS, Role, build_access_filter
from app.retrieval.embeddings import embed_query_dense, embed_query_sparse
from app.retrieval.models import RetrievedChunk
from app.retrieval.qdrant_store import DENSE_VECTOR, SPARSE_VECTOR, collection_name, get_client

logger = logging.getLogger(__name__)


class RBACViolationError(RuntimeError):
    """Raised if Qdrant ever returns a chunk outside the role's collections (tripwire)."""


def _assert_authorised(chunks: list[RetrievedChunk], role: Role) -> None:
    """Defence-in-depth tripwire. It never filters - it fails loudly instead.

    If this ever raises, the Qdrant filter is broken and the request must not proceed.
    """
    allowed = {c.value for c in ROLE_COLLECTIONS[role]}
    for c in chunks:
        if c.collection not in allowed or role.value not in c.access_roles:
            raise RBACViolationError(
                f"Unauthorised chunk returned for role {role.value}: "
                f"{c.source_document} ({c.collection})"
            )


def build_hybrid_query(
    question: str, role: Role, limit: int, prefetch_limit: int
) -> dict[str, object]:
    """Arguments for ``QdrantClient.query_points`` - exposed so tests can inspect them."""
    access_filter = build_access_filter(role)
    return {
        "prefetch": [
            models.Prefetch(
                query=embed_query_dense(question),
                using=DENSE_VECTOR,
                filter=access_filter,
                limit=prefetch_limit,
            ),
            models.Prefetch(
                query=embed_query_sparse(question),
                using=SPARSE_VECTOR,
                filter=access_filter,
                limit=prefetch_limit,
            ),
        ],
        "query": models.FusionQuery(fusion=models.Fusion.RRF),
        "query_filter": access_filter,
        "limit": limit,
        "with_payload": True,
    }


def hybrid_search(
    question: str,
    role: Role,
    *,
    limit: int | None = None,
    client: QdrantClient | None = None,
) -> list[RetrievedChunk]:
    """Top-``limit`` RBAC-filtered candidates from fused dense + BM25 retrieval."""
    s = get_settings()
    limit = limit or s.retrieval_candidates
    client = client or get_client()
    kwargs = build_hybrid_query(question, role, limit, max(s.prefetch_limit, limit))
    response = client.query_points(collection_name=collection_name(), **kwargs)  # type: ignore[arg-type]
    chunks = [RetrievedChunk.from_point(p, i + 1) for i, p in enumerate(response.points)]
    _assert_authorised(chunks, role)
    logger.info(
        "hybrid_search role=%s q=%r -> %s",
        role.value,
        question[:80],
        [
            (c.initial_rank, c.source_document, c.section_title, round(c.retrieval_score, 4))
            for c in chunks
        ],
    )
    return chunks


def dense_search(
    question: str, role: Role, *, limit: int = 10, client: QdrantClient | None = None
) -> list[RetrievedChunk]:
    """Dense-only baseline (evaluation). Still RBAC-filtered inside Qdrant."""
    client = client or get_client()
    response = client.query_points(
        collection_name=collection_name(),
        query=embed_query_dense(question),
        using=DENSE_VECTOR,
        query_filter=build_access_filter(role),
        limit=limit,
        with_payload=True,
    )
    chunks = [RetrievedChunk.from_point(p, i + 1) for i, p in enumerate(response.points)]
    _assert_authorised(chunks, role)
    return chunks


def sparse_search(
    question: str, role: Role, *, limit: int = 10, client: QdrantClient | None = None
) -> list[RetrievedChunk]:
    """BM25-only baseline (evaluation). Still RBAC-filtered inside Qdrant."""
    client = client or get_client()
    response = client.query_points(
        collection_name=collection_name(),
        query=embed_query_sparse(question),
        using=SPARSE_VECTOR,
        query_filter=build_access_filter(role),
        limit=limit,
        with_payload=True,
    )
    chunks = [RetrievedChunk.from_point(p, i + 1) for i, p in enumerate(response.points)]
    _assert_authorised(chunks, role)
    return chunks
