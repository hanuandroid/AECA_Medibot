"""Cross-encoder reranking: joint scoring, reordering, top-k cut, only top-k reach the LLM."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.rag.pipeline import answer_with_documents
from app.rbac import Role
from app.retrieval.embeddings import cross_encoder_scores
from app.retrieval.hybrid import hybrid_search
from app.retrieval.models import RetrievedChunk
from app.retrieval.reranker import rerank

from .conftest import StubLLM


def _chunk(i: int, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        point_id=str(i),
        source_document=f"d{i}.pdf",
        collection="general",
        access_roles=["admin"],
        section_title=f"s{i}",
        chunk_type="text",
        text=text,
        retrieval_score=1.0 / i,
        initial_rank=i,
    )


def test_rerank_orders_by_score_and_cuts_to_top_k() -> None:
    cands = [_chunk(i, f"text {i}") for i in range(1, 11)]
    fake_scores = [0.1, 0.5, 0.2, 0.9, 0.0, 0.3, 0.8, 0.4, 0.6, 0.7]

    def score_fn(q: str, passages: Sequence[str]) -> list[float]:
        assert len(passages) == 10  # the reranker sees the whole candidate set jointly with q
        return fake_scores

    top = rerank("q", cands, top_k=3, score_fn=score_fn)
    assert [c.initial_rank for c in top] == [4, 7, 10]
    assert [c.final_rank for c in top] == [1, 2, 3]
    assert all(c.rerank_score is not None for c in cands)  # all annotated for logging


def test_rerank_empty() -> None:
    assert rerank("q", [], top_k=3) == []


def test_cross_encoder_scores_query_passage_pairs_jointly() -> None:
    q = "What is the occlusion alarm threshold for venous lines?"
    passages = [
        "Annual leave: staff are entitled to 24 days of earned leave per year.",
        "Occlusion pressure alarm settings: venous lines - reduce the threshold to 200 mmHg.",
    ]
    scores = cross_encoder_scores(q, passages)
    assert scores[1] > scores[0]
    # Joint scoring: the same passage scores differently for a different query.
    other = cross_encoder_scores("How many days of annual leave?", passages)
    assert other[0] > other[1]


@pytest.mark.index
def test_reranker_changes_order_on_real_candidates() -> None:
    q = "What is the standard dose of vancomycin?"
    candidates = hybrid_search(q, Role.DOCTOR)
    top = rerank(q, candidates, top_k=3)
    assert len(top) == 3
    assert any(c.initial_rank != c.final_rank for c in candidates)
    assert any("Vancomycin" in c.text and "Q12H" in c.text for c in top)


@pytest.mark.index
def test_only_reranked_top_k_reach_the_llm() -> None:
    llm = StubLLM("Vancomycin is dosed at 15-20 mg/kg Q12H [1].")
    result = answer_with_documents("What is the standard dose of vancomycin?", Role.DOCTOR, llm=llm)
    assert len(result.candidates) == 10
    assert len(result.used_chunks) == 3
    _, prompt = llm.calls[0]
    assert prompt.count("Source: ") == 3
    for c in result.candidates:
        in_prompt = f"[{c.final_rank}] Source: {c.context_header}" in prompt
        assert in_prompt == (c in result.used_chunks)
