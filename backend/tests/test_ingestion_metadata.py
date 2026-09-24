"""The ingested Qdrant index: complete metadata schema, RBAC stamping, structure preserved."""

from __future__ import annotations

from collections import Counter
from typing import Any

import pytest

from app.config import get_settings
from app.ingestion.loader import discover_documents
from app.ingestion.metadata import REQUIRED_FIELDS
from app.rbac import ALL_COLLECTIONS, Collection, roles_for_collection
from app.retrieval.qdrant_store import DENSE_VECTOR, SPARSE_VECTOR, collection_name, get_client

pytestmark = pytest.mark.index


@pytest.fixture(scope="module")
def payloads() -> list[dict[str, Any]]:
    client = get_client()
    out: list[dict[str, Any]] = []
    offset = None
    while True:
        batch, offset = client.scroll(
            collection_name(), limit=256, offset=offset, with_payload=True
        )
        out.extend(p.payload or {} for p in batch)
        if offset is None:
            return out


def test_every_chunk_has_the_required_metadata(payloads: list[dict[str, Any]]) -> None:
    assert len(payloads) > 100
    for p in payloads:
        for field in REQUIRED_FIELDS:
            assert p.get(field), f"missing {field} in {p.get('source_document')}"
        assert p["collection"] in {c.value for c in ALL_COLLECTIONS}
        assert p["chunk_type"] in {"text", "table", "heading", "code"}
        assert sorted(p["access_roles"]) == sorted(
            roles_for_collection(Collection(p["collection"]))
        )


def test_every_source_document_is_indexed_in_its_folder_collection(
    payloads: list[dict[str, Any]],
) -> None:
    expected = {d.filename: d.collection.value for d in discover_documents(get_settings().data_dir)}
    indexed = {p["source_document"]: p["collection"] for p in payloads}
    assert indexed == expected
    assert len(expected) == 12


def test_all_chunk_types_present_and_tables_preserved(payloads: list[dict[str, Any]]) -> None:
    types = Counter(p["chunk_type"] for p in payloads)
    assert types["text"] and types["table"] and types["heading"] and types["code"]
    tables = [p for p in payloads if p["chunk_type"] == "table"]
    # Tables are serialised as Markdown tables, not flattened prose.
    assert all("|" in p["text"] and "---" in p["text"] for p in tables)
    formulary = [p for p in tables if p["source_document"] == "drug_formulary.pdf"]
    assert any("Vancomycin" in p["text"] and "15-20 mg/kg Q12H" in p["text"] for p in formulary)


def test_embedded_text_carries_parent_heading_context(payloads: list[dict[str, Any]]) -> None:
    for p in payloads:
        assert p["heading_path"], p["source_document"]
        assert p["embed_text"].startswith(p["heading_path"][0])
        assert p["section_title"] in p["embed_text"]
    # Hierarchy: identical subsection names are disambiguated by their parent section.
    fault = [
        p
        for p in payloads
        if p["source_document"] == "equipment_manual.pdf"
        and p["section_title"] == "Fault codes"
        and p["chunk_type"] == "table"
    ]
    parents = {p["heading_path"][-2] for p in fault}
    assert {
        "A. Patient Monitoring System - MediAssist BM-500",
        "B. Infusion Pump - DriveFlow IP-200",
    } <= parents


def test_points_have_dense_and_sparse_vectors() -> None:
    client = get_client()
    info = client.get_collection(collection_name())
    assert DENSE_VECTOR in info.config.params.vectors  # type: ignore[operator]
    assert SPARSE_VECTOR in info.config.params.sparse_vectors  # type: ignore[operator]
    points, _ = client.scroll(collection_name(), limit=5, with_vectors=True)
    for pt in points:
        assert isinstance(pt.vector, dict)
        assert len(pt.vector[DENSE_VECTOR]) == 384  # type: ignore[arg-type]
        assert pt.vector[SPARSE_VECTOR].indices  # type: ignore[union-attr]


def test_payload_indexes_exist_for_rbac_fields() -> None:
    schema = get_client().get_collection(collection_name()).payload_schema
    assert "access_roles" in schema and "collection" in schema
