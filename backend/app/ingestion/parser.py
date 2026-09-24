"""Structural parsing with Docling (PDF layout + TableFormer, Markdown backend).

Docling recognises headings, paragraphs, list items, tables and code blocks. For PDFs it
reports every section header at the same level, which would lose the hierarchy
("Fault codes" under "B. Infusion Pump" vs "C. Autoclave"). ``assign_heading_levels``
restores it from the rendered heading size (bounding-box height): larger font -> higher level.
Markdown keeps the levels given by ``#``/``##``/``###``.
"""

from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from docling_core.types.doc import DoclingDocument, SectionHeaderItem

if TYPE_CHECKING:
    from docling.document_converter import DocumentConverter

logger = logging.getLogger(__name__)

# Heights closer than this (points) are treated as the same heading style.
_HEIGHT_TOLERANCE = 0.75


@lru_cache(maxsize=1)
def _converter() -> DocumentConverter:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
    return DocumentConverter(
        allowed_formats=[InputFormat.PDF, InputFormat.MD],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)},
    )


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def parse_document(path: Path, cache_dir: Path | None = None) -> DoclingDocument:
    """Convert ``path`` with Docling; caches the DoclingDocument JSON by content hash."""
    cached: Path | None = None
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached = cache_dir / f"{path.stem}.{_file_hash(path)}.json"
        if cached.exists():
            logger.info("Using cached Docling parse for %s", path.name)
            doc = DoclingDocument.load_from_json(cached)
            assign_heading_levels(doc)
            return doc
    logger.info("Parsing %s with Docling", path.name)
    doc = _converter().convert(path).document
    if cached is not None:
        doc.save_as_json(cached)
    assign_heading_levels(doc)
    return doc


def _cluster_heights(heights: list[float]) -> list[float]:
    """Distinct heading heights, largest first, merging values within the tolerance."""
    clusters: list[float] = []
    for h in sorted(heights, reverse=True):
        if not clusters or clusters[-1] - h > _HEIGHT_TOLERANCE:
            clusters.append(h)
    return clusters


def assign_heading_levels(doc: DoclingDocument) -> None:
    """Rebuild the section hierarchy of a PDF from heading sizes (in place).

    No-op when headings carry no layout information (Markdown input) - there the levels
    already come from the Markdown syntax.
    """
    headers = [
        item for item, _ in doc.iterate_items() if isinstance(item, SectionHeaderItem) and item.prov
    ]
    if not headers:
        return
    heights = [h.prov[0].bbox.height for h in headers]
    clusters = _cluster_heights(heights)

    def level_for(height: float) -> int:
        for idx, c in enumerate(clusters):
            if c - height <= _HEIGHT_TOLERANCE:
                return idx + 1
        return len(clusters)

    for header, height in zip(headers, heights, strict=True):
        header.level = level_for(height)
    logger.debug("Heading levels: %s", [(h.text[:40], h.level) for h in headers])
