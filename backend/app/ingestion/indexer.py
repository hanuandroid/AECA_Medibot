"""Write chunks (payload + dense + sparse vectors) to Qdrant."""

from __future__ import annotations

import logging

from qdrant_client import QdrantClient, models

from app.ingestion.embeddings import vectorise
from app.ingestion.metadata import ChunkRecord
from app.retrieval.embeddings import dense_dim
from app.retrieval.qdrant_store import DENSE_VECTOR, SPARSE_VECTOR, create_collection

logger = logging.getLogger(__name__)

BATCH_SIZE = 64


def index_records(
    client: QdrantClient, collection: str, records: list[ChunkRecord], *, recreate: bool = True
) -> int:
    if recreate or not client.collection_exists(collection):
        create_collection(client, collection, dense_dim())
    written = 0
    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start : start + BATCH_SIZE]
        vectors = vectorise(batch)
        points = [
            models.PointStruct(
                id=rec.point_id,
                vector={DENSE_VECTOR: vec.dense, SPARSE_VECTOR: vec.sparse},
                payload=rec.payload(),
            )
            for rec, vec in zip(batch, vectors, strict=True)
        ]
        client.upsert(collection_name=collection, points=points, wait=True)
        written += len(points)
        logger.info("Indexed %d/%d chunks", written, len(records))
    return written
