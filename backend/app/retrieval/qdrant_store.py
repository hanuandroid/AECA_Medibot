"""Qdrant client factory and collection schema.

Schema (one Qdrant collection holds every document collection; the ``collection`` payload
field says which MediAssist collection a chunk belongs to):

* named dense vector ``dense``  - bge-small, cosine
* named sparse vector ``bm25``  - BM25 term weights, ``Modifier.IDF`` (IDF computed by Qdrant)
* payload indexes on ``access_roles`` / ``collection`` / ``source_document`` / ``chunk_type``
  so the RBAC filter is evaluated by the index inside Qdrant.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from qdrant_client import QdrantClient, models

from app.config import get_settings

logger = logging.getLogger(__name__)

DENSE_VECTOR = "dense"
SPARSE_VECTOR = "bm25"
KEYWORD_INDEXES = ("access_roles", "collection", "source_document", "chunk_type")


@lru_cache(maxsize=1)
def get_client() -> QdrantClient:
    s = get_settings()
    if s.qdrant_path:
        logger.info("Using embedded Qdrant at %s", s.qdrant_path)
        return QdrantClient(path=s.qdrant_path)
    logger.info("Using Qdrant server at %s", s.qdrant_url)
    return QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key, timeout=30)


def collection_name() -> str:
    return get_settings().qdrant_collection


def create_collection(client: QdrantClient, name: str, dense_dim: int) -> None:
    if client.collection_exists(name):
        client.delete_collection(name)
    client.create_collection(
        collection_name=name,
        vectors_config={
            DENSE_VECTOR: models.VectorParams(size=dense_dim, distance=models.Distance.COSINE)
        },
        sparse_vectors_config={
            SPARSE_VECTOR: models.SparseVectorParams(modifier=models.Modifier.IDF)
        },
    )
    for field in KEYWORD_INDEXES:
        client.create_payload_index(
            collection_name=name,
            field_name=field,
            field_schema=models.PayloadSchemaType.KEYWORD,
        )


def index_status(client: QdrantClient | None = None) -> dict[str, object]:
    """Reachability + point count, used by /health and test skips."""
    try:
        client = client or get_client()
        name = collection_name()
        if not client.collection_exists(name):
            return {"reachable": True, "collection": name, "exists": False, "points": 0}
        count = client.count(name, exact=True).count
        return {"reachable": True, "collection": name, "exists": True, "points": count}
    except Exception as exc:  # noqa: BLE001 - health endpoint must never raise
        return {"reachable": False, "error": str(exc)}
