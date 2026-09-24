"""Chunk metadata schema stored as the Qdrant payload of every point."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.rbac import Collection, roles_for_collection

ChunkType = Literal["text", "table", "heading", "code"]

REQUIRED_FIELDS = ("source_document", "collection", "access_roles", "section_title", "chunk_type")

_NAMESPACE = uuid.UUID("5b0f2b4e-6a52-4c37-9a51-6d3f1f2b8a10")


class ChunkRecord(BaseModel):
    """One retrievable chunk. The first five fields are the assignment's mandatory schema."""

    source_document: str = Field(min_length=1)
    collection: Collection
    access_roles: list[str] = Field(min_length=1)
    section_title: str = Field(min_length=1)
    chunk_type: ChunkType

    # Extras used for citations, evaluation and debugging.
    heading_path: list[str] = Field(default_factory=list)
    page_numbers: list[int] = Field(default_factory=list)
    chunk_index: int = Field(ge=0)
    text: str = Field(min_length=1)  # chunk body as shown to the LLM / user
    embed_text: str = Field(min_length=1)  # heading-contextualised text that is embedded

    @field_validator("access_roles")
    @classmethod
    def _roles_unique(cls, v: list[str]) -> list[str]:
        return sorted(set(v))

    @model_validator(mode="after")
    def _roles_match_collection(self) -> ChunkRecord:
        expected = sorted(roles_for_collection(self.collection))
        if self.access_roles != expected:
            raise ValueError(
                f"access_roles {self.access_roles} do not match RBAC matrix for "
                f"{self.collection.value}: {expected}"
            )
        return self

    @property
    def point_id(self) -> str:
        return str(uuid.uuid5(_NAMESPACE, f"{self.source_document}#{self.chunk_index}"))

    def payload(self) -> dict[str, object]:
        data = self.model_dump(mode="json")
        return data


def make_record(
    *,
    source_document: str,
    collection: Collection,
    section_title: str,
    chunk_type: ChunkType,
    heading_path: list[str],
    page_numbers: list[int],
    chunk_index: int,
    text: str,
    embed_text: str,
) -> ChunkRecord:
    """Build a record; ``access_roles`` always derives from the RBAC matrix."""
    return ChunkRecord(
        source_document=source_document,
        collection=collection,
        access_roles=roles_for_collection(collection),
        section_title=section_title,
        chunk_type=chunk_type,
        heading_path=heading_path,
        page_numbers=page_numbers,
        chunk_index=chunk_index,
        text=text,
        embed_text=embed_text,
    )
