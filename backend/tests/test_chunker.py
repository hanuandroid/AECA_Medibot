"""Chunking logic: chunk_type classification, heading hierarchy, heading context, metadata."""

from __future__ import annotations

import pytest
from docling_core.types.doc import DocItemLabel, DoclingDocument
from docling_core.types.doc.base import BoundingBox
from docling_core.types.doc.document import ProvenanceItem, Size

from app.ingestion.chunker import chunk_document, classify_chunk_type
from app.ingestion.metadata import REQUIRED_FIELDS, ChunkRecord, make_record
from app.ingestion.parser import assign_heading_levels
from app.rbac import Collection


@pytest.mark.parametrize(
    ("labels", "expected"),
    [
        ([DocItemLabel.TEXT, DocItemLabel.LIST_ITEM], "text"),
        ([DocItemLabel.TEXT, DocItemLabel.TABLE], "table"),
        ([DocItemLabel.CODE], "code"),
        ([DocItemLabel.SECTION_HEADER], "heading"),
        ([DocItemLabel.TITLE, DocItemLabel.SECTION_HEADER], "heading"),
        ([], "text"),
    ],
)
def test_classify_chunk_type(labels: list[DocItemLabel], expected: str) -> None:
    assert classify_chunk_type(labels) == expected


def _prov(height: float, page: int = 1) -> ProvenanceItem:
    return ProvenanceItem(
        page_no=page, bbox=BoundingBox(l=0, t=height, r=100, b=0), charspan=(0, 1)
    )


def _pdf_like_doc() -> DoclingDocument:
    """Mimics Docling PDF output: every header at level 1, sizes differ."""
    doc = DoclingDocument(name="equipment_manual")
    doc.add_page(page_no=1, size=Size(width=600, height=800))
    doc.add_heading("Equipment Manual", level=1, prov=_prov(21.9))
    doc.add_heading("A. Monitor BM-500", level=1, prov=_prov(13.5))
    doc.add_heading("Fault codes", level=1, prov=_prov(9.1))
    doc.add_text(DocItemLabel.TEXT, "E-12 means internal sensor failure.", prov=_prov(8))
    doc.add_heading("B. Infusion Pump IP-200", level=1, prov=_prov(13.5))
    doc.add_heading("Fault codes", level=1, prov=_prov(9.1))
    doc.add_text(DocItemLabel.TEXT, "F-03 means occlusion; check for kinks.", prov=_prov(8))
    return doc


def test_assign_heading_levels_restores_hierarchy() -> None:
    doc = _pdf_like_doc()
    assign_heading_levels(doc)
    levels = [(h.text, h.level) for h in doc.texts if h.label == DocItemLabel.SECTION_HEADER]
    assert levels == [
        ("Equipment Manual", 1),
        ("A. Monitor BM-500", 2),
        ("Fault codes", 3),
        ("B. Infusion Pump IP-200", 2),
        ("Fault codes", 3),
    ]


def test_chunks_carry_parent_heading_context_and_metadata() -> None:
    doc = _pdf_like_doc()
    assign_heading_levels(doc)
    records = chunk_document(
        doc, source_document="equipment_manual.pdf", collection=Collection.EQUIPMENT
    )
    content = [r for r in records if r.chunk_type == "text"]
    f03 = next(r for r in content if "F-03" in r.text)
    # The chunk is under "Fault codes" but must know WHICH device's fault codes.
    assert f03.heading_path == ["Equipment Manual", "B. Infusion Pump IP-200", "Fault codes"]
    assert f03.section_title == "Fault codes"
    assert "B. Infusion Pump IP-200" in f03.embed_text
    assert "A. Monitor BM-500" not in f03.embed_text
    assert f03.access_roles == ["admin", "technician"]
    for r in records:
        payload = r.payload()
        for field in REQUIRED_FIELDS:
            assert payload[field], field
    outline = [r for r in records if r.chunk_type == "heading"]
    assert any("B. Infusion Pump IP-200" in r.text for r in outline)


def test_make_record_derives_access_roles_from_rbac() -> None:
    rec = make_record(
        source_document="drug_formulary.pdf",
        collection=Collection.CLINICAL,
        section_title="1. Antimicrobials",
        chunk_type="table",
        heading_path=["x"],
        page_numbers=[2],
        chunk_index=0,
        text="t",
        embed_text="x\nt",
    )
    assert rec.access_roles == ["admin", "doctor"]


def test_record_rejects_access_roles_that_disagree_with_matrix() -> None:
    with pytest.raises(ValueError):
        ChunkRecord(
            source_document="billing_codes.pdf",
            collection=Collection.BILLING,
            access_roles=["billing_executive", "admin", "nurse"],
            section_title="s",
            chunk_type="text",
            chunk_index=0,
            text="t",
            embed_text="t",
        )


def test_point_ids_are_deterministic() -> None:
    kw = dict(
        source_document="a.pdf",
        collection=Collection.GENERAL,
        section_title="s",
        chunk_type="text",
        heading_path=[],
        page_numbers=[],
        chunk_index=3,
        text="t",
        embed_text="t",
    )
    assert make_record(**kw).point_id == make_record(**kw).point_id  # type: ignore[arg-type]
