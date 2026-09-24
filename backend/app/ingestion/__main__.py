"""Standalone ingestion: ``python -m app.ingestion [--reparse] [--data-dir PATH]``.

PDF/Markdown -> Docling -> hierarchical chunks (+heading context, metadata)
-> dense + BM25 vectors -> Qdrant.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import time
from collections import Counter
from pathlib import Path

from app.config import BACKEND_DIR, get_settings
from app.ingestion.chunker import chunk_document
from app.ingestion.indexer import index_records
from app.ingestion.loader import discover_documents
from app.ingestion.metadata import ChunkRecord
from app.ingestion.parser import parse_document
from app.retrieval.qdrant_store import collection_name, get_client

logger = logging.getLogger("app.ingestion")

CACHE_DIR = BACKEND_DIR / "data" / "docling_cache"
PREVIEW_PATH = BACKEND_DIR / "data" / "chunks_preview.jsonl"


def run(data_dir: Path, reparse: bool = False) -> list[ChunkRecord]:
    if reparse and CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
    docs = discover_documents(data_dir)
    logger.info("Found %d documents under %s", len(docs), data_dir)

    records: list[ChunkRecord] = []
    for src in docs:
        started = time.perf_counter()
        doc = parse_document(src.path, cache_dir=CACHE_DIR)
        chunks = chunk_document(doc, source_document=src.filename, collection=src.collection)
        records.extend(chunks)
        logger.info(
            "%-28s %-10s %3d chunks (%.1fs)",
            src.filename,
            src.collection.value,
            len(chunks),
            time.perf_counter() - started,
        )

    client = get_client()
    written = index_records(client, collection_name(), records, recreate=True)

    PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PREVIEW_PATH.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r.payload() | {"point_id": r.point_id}, ensure_ascii=False) + "\n")

    by_collection = Counter(r.collection.value for r in records)
    by_type = Counter(r.chunk_type for r in records)
    logger.info("Indexed %d chunks into '%s'", written, collection_name())
    logger.info("Chunks per collection: %s", dict(by_collection))
    logger.info("Chunks per type: %s", dict(by_type))
    logger.info("Chunk preview written to %s", PREVIEW_PATH)
    return records


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    for noisy in ("docling", "httpx", "RapidOCR", "transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description="Build the MediBot Qdrant index")
    parser.add_argument("--data-dir", type=Path, default=get_settings().data_dir)
    parser.add_argument("--reparse", action="store_true", help="ignore the Docling parse cache")
    args = parser.parse_args()
    run(args.data_dir, reparse=args.reparse)


if __name__ == "__main__":
    main()
