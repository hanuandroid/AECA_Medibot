"""Retrieval result model shared by hybrid search, reranking and the RAG pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetrievedChunk:
    point_id: str
    source_document: str
    collection: str
    access_roles: list[str]
    section_title: str
    chunk_type: str
    text: str
    heading_path: list[str] = field(default_factory=list)
    page_numbers: list[int] = field(default_factory=list)
    retrieval_score: float = 0.0  # fusion (RRF) score, or dense/sparse score for baselines
    initial_rank: int = 0  # 1-based rank from Qdrant
    rerank_score: float | None = None
    final_rank: int | None = None  # 1-based rank after cross-encoder

    @classmethod
    def from_point(cls, point: Any, rank: int) -> RetrievedChunk:
        p = point.payload or {}
        return cls(
            point_id=str(point.id),
            source_document=p["source_document"],
            collection=p["collection"],
            access_roles=list(p["access_roles"]),
            section_title=p["section_title"],
            chunk_type=p["chunk_type"],
            text=p["text"],
            heading_path=list(p.get("heading_path") or []),
            page_numbers=list(p.get("page_numbers") or []),
            retrieval_score=float(point.score),
            initial_rank=rank,
        )

    @property
    def context_header(self) -> str:
        path = " > ".join(self.heading_path) if self.heading_path else self.section_title
        return f"{self.source_document} | {path}"
