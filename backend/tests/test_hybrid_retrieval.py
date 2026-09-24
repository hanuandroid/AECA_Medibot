"""Hybrid retrieval: a single fused Qdrant query that finds exact terms and semantics."""

from __future__ import annotations

from typing import Any

import pytest
from qdrant_client import models

from app.rbac import Role
from app.retrieval.hybrid import build_hybrid_query, hybrid_search
from app.retrieval.qdrant_store import DENSE_VECTOR, SPARSE_VECTOR

pytestmark = pytest.mark.index


def test_hybrid_query_is_one_fused_query_over_dense_and_sparse() -> None:
    q = build_hybrid_query("vancomycin dose", Role.DOCTOR, limit=10, prefetch_limit=30)
    prefetch = q["prefetch"]
    assert isinstance(prefetch, list) and len(prefetch) == 2
    assert {p.using for p in prefetch} == {DENSE_VECTOR, SPARSE_VECTOR}
    dense = next(p for p in prefetch if p.using == DENSE_VECTOR)
    sparse = next(p for p in prefetch if p.using == SPARSE_VECTOR)
    assert isinstance(dense.query, list) and len(dense.query) == 384
    assert isinstance(sparse.query, models.SparseVector) and sparse.query.indices
    assert isinstance(q["query"], models.FusionQuery)
    assert q["query"].fusion == models.Fusion.RRF
    assert q["limit"] == 10


def test_hybrid_search_makes_exactly_one_qdrant_call() -> None:
    from app.retrieval.qdrant_store import get_client

    calls: list[dict[str, Any]] = []
    real = get_client()

    class Spy:
        def query_points(self, **kw: Any) -> Any:
            calls.append(kw)
            return real.query_points(**kw)

    chunks = hybrid_search("vancomycin dose", Role.DOCTOR, client=Spy())  # type: ignore[arg-type]
    assert len(calls) == 1 and chunks


def test_candidate_set_is_top_10_with_ranks() -> None:
    chunks = hybrid_search("How is a central venous catheter dressing changed?", Role.NURSE)
    assert len(chunks) == 10
    assert [c.initial_rank for c in chunks] == list(range(1, 11))
    scores = [c.retrieval_score for c in chunks]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.parametrize(
    ("role", "question", "document", "must_contain"),
    [
        # exact terms: drug name, ICD code, equipment model, fault code, table value
        (Role.DOCTOR, "vancomycin dose", "drug_formulary.pdf", "Vancomycin"),
        (Role.BILLING_EXECUTIVE, "ICD-10 code A90", "billing_codes.pdf", "A90"),
        (Role.TECHNICIAN, "RadiPro MX-150 fault codes", "equipment_manual.pdf", "RadiPro"),
        (
            Role.TECHNICIAN,
            "What does F-03 mean on the infusion pump?",
            "equipment_manual.pdf",
            "F-03",
        ),
        (
            Role.NURSE,
            "IV cannula size for a paediatric patient under 5kg",
            "icu_nursing_procedures.pdf",
            "24G",
        ),
        # semantic phrasing without the document's wording
        (
            Role.NURSE,
            "how do I stop bedsores in bed-bound ICU patients",
            "icu_nursing_procedures.pdf",
            "Pressure",
        ),
        (
            Role.DOCTOR,
            "first-line tablets for high blood sugar",
            "treatment_protocols.pdf",
            "Metformin",
        ),
    ],
)
def test_hybrid_finds_relevant_chunk_in_top_candidates(
    role: Role, question: str, document: str, must_contain: str
) -> None:
    chunks = hybrid_search(question, role)
    hits = [
        c
        for c in chunks
        if c.source_document == document
        and (must_contain in c.text or must_contain in " > ".join(c.heading_path))
    ]
    assert hits, [(c.source_document, c.section_title) for c in chunks]
    assert min(c.initial_rank for c in hits) <= 5
