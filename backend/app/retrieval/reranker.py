"""Cross-encoder reranking: score (question, chunk) pairs jointly and keep the best ``top_k``."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from app.config import get_settings
from app.retrieval.embeddings import cross_encoder_scores
from app.retrieval.models import RetrievedChunk

logger = logging.getLogger(__name__)

ScoreFn = Callable[[str, Sequence[str]], list[float]]


def rerank_text(chunk: RetrievedChunk) -> str:
    """Text the cross-encoder reads: heading path + body (same context the LLM sees)."""
    return f"{' > '.join(chunk.heading_path)}\n{chunk.text}" if chunk.heading_path else chunk.text


def rerank(
    question: str,
    candidates: list[RetrievedChunk],
    *,
    top_k: int | None = None,
    score_fn: ScoreFn = cross_encoder_scores,
) -> list[RetrievedChunk]:
    """Score every candidate, set ``rerank_score``/``final_rank`` on all, return the top_k.

    All candidates are annotated (so the caller can log / display the full before-vs-after
    ranking), but only the returned ``top_k`` may be sent to the LLM.
    """
    top_k = top_k or get_settings().rerank_top_k
    if not candidates:
        return []
    scores = score_fn(question, [rerank_text(c) for c in candidates])
    for chunk, score in zip(candidates, scores, strict=True):
        chunk.rerank_score = score
    ordered = sorted(candidates, key=lambda c: c.rerank_score or 0.0, reverse=True)
    for i, chunk in enumerate(ordered):
        chunk.final_rank = i + 1
    logger.info(
        "rerank q=%r\n%s",
        question[:80],
        "\n".join(
            f"  initial #{c.initial_rank:>2} -> final #{c.final_rank:>2}  "
            f"ce={c.rerank_score:+.3f}  rrf={c.retrieval_score:.4f}  "
            f"{c.source_document} :: {c.section_title}"
            for c in sorted(candidates, key=lambda c: c.initial_rank)
        ),
    )
    return ordered[:top_k]
