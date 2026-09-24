"""Hierarchical, token-aware chunking with Docling's HybridChunker.

Pass 1 (hierarchical): the document tree is walked section -> subsection -> paragraph / list /
table / code; a chunk never spans two sections, and each chunk records its heading path.
Pass 2 (token-aware): oversized chunks are split (tables row-wise, repeating the header row)
and undersized neighbours under the *same* headings are merged, using the tokenizer of the
dense embedding model so chunks fit its context window.

Tables are serialised as Markdown tables (not Docling's default "triplet" flattening).

Besides content chunks, one ``heading`` chunk is emitted per section that has subsections
(an outline: heading path + child headings), so structure questions are answerable too.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from docling_core.transforms.chunker.hierarchical_chunker import (
    ChunkingDocSerializer,
    ChunkingSerializerProvider,
    DocChunk,
)
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling_core.transforms.serializer.markdown import MarkdownTableSerializer
from docling_core.types.doc import DocItemLabel, DoclingDocument, SectionHeaderItem, TitleItem

from app.config import get_settings
from app.ingestion.metadata import ChunkRecord, ChunkType, make_record
from app.rbac import Collection

logger = logging.getLogger(__name__)

_HEADING_LABELS = {DocItemLabel.SECTION_HEADER, DocItemLabel.TITLE}


class MarkdownTableSerializerProvider(ChunkingSerializerProvider):
    """Serialise tables as Markdown so rows/columns stay aligned inside a chunk."""

    def get_serializer(self, doc: DoclingDocument) -> ChunkingDocSerializer:
        return ChunkingDocSerializer(doc=doc, table_serializer=MarkdownTableSerializer())


@lru_cache(maxsize=1)
def get_chunker() -> HybridChunker:
    s = get_settings()
    tokenizer = HuggingFaceTokenizer.from_pretrained(
        model_name=s.dense_model, max_tokens=s.chunk_max_tokens
    )
    return HybridChunker(
        tokenizer=tokenizer,
        merge_peers=True,
        repeat_table_header=True,
        serializer_provider=MarkdownTableSerializerProvider(),
    )


def classify_chunk_type(labels: list[DocItemLabel]) -> ChunkType:
    """Map the Docling item labels inside a chunk to the assignment's chunk_type enum."""
    label_set = set(labels)
    if DocItemLabel.TABLE in label_set:
        return "table"
    if DocItemLabel.CODE in label_set:
        return "code"
    if label_set and label_set <= _HEADING_LABELS:
        return "heading"
    return "text"


def _document_title(doc: DoclingDocument, fallback: str) -> str:
    for item, _ in doc.iterate_items():
        if isinstance(item, TitleItem | SectionHeaderItem):
            return item.text.strip()
    return fallback


def _outline_chunks(doc: DoclingDocument) -> list[tuple[list[str], list[str]]]:
    """(heading_path, child_headings) for every heading that has sub-headings."""
    stack: list[tuple[int, str]] = []
    children: dict[tuple[str, ...], list[str]] = {}
    order: list[tuple[str, ...]] = []
    for item, _ in doc.iterate_items():
        if not isinstance(item, TitleItem | SectionHeaderItem):
            continue
        level = item.level if isinstance(item, SectionHeaderItem) else 0
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = tuple(t for _, t in stack)
        if parent:
            if parent not in children:
                children[parent] = []
                order.append(parent)
            children[parent].append(item.text.strip())
        stack.append((level, item.text.strip()))
    return [(list(p), children[p]) for p in order if children[p]]


def chunk_document(
    doc: DoclingDocument, *, source_document: str, collection: Collection
) -> list[ChunkRecord]:
    chunker = get_chunker()
    title = _document_title(doc, fallback=source_document)
    records: list[ChunkRecord] = []

    for base_chunk in chunker.chunk(dl_doc=doc):
        chunk = DocChunk.model_validate(base_chunk)
        body = chunk.text.strip()
        if not body:
            continue
        headings = [h.strip() for h in (chunk.meta.headings or []) if h and h.strip()]
        labels = [it.label for it in chunk.meta.doc_items]
        pages = sorted({p.page_no for it in chunk.meta.doc_items for p in (it.prov or [])})
        embed_text = chunker.contextualize(chunk=chunk).strip()
        records.append(
            make_record(
                source_document=source_document,
                collection=collection,
                section_title=headings[-1] if headings else title,
                chunk_type=classify_chunk_type(labels),
                heading_path=headings or [title],
                page_numbers=pages,
                chunk_index=len(records),
                text=body,
                embed_text=embed_text if headings else f"{title}\n{body}",
            )
        )

    for path, child_headings in _outline_chunks(doc):
        body = "Sections:\n" + "\n".join(f"- {h}" for h in child_headings)
        records.append(
            make_record(
                source_document=source_document,
                collection=collection,
                section_title=path[-1],
                chunk_type="heading",
                heading_path=path,
                page_numbers=[],
                chunk_index=len(records),
                text=body,
                embed_text="\n".join(path) + "\n" + body,
            )
        )

    logger.info("%s: %d chunks", source_document, len(records))
    return records
