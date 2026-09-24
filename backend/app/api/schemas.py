"""HTTP request/response models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class CollectionInfo(BaseModel):
    name: str
    label: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    username: str
    display_name: str
    role: str
    collections: list[str]


class ChatRequest(BaseModel):
    """Only the question. The role is taken from the bearer token; a ``role`` field is rejected."""

    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)


class Source(BaseModel):
    source_document: str
    section_title: str
    collection: str
    chunk_type: str | None = None
    page_numbers: list[int] = Field(default_factory=list)
    rerank_score: float | None = None


class RankedCandidate(BaseModel):
    """Before/after reranking view of the (already RBAC-filtered) candidate set."""

    source_document: str
    section_title: str
    collection: str
    initial_rank: int
    fusion_score: float
    rerank_score: float | None
    final_rank: int | None
    sent_to_llm: bool


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)
    retrieval_type: Literal["hybrid_rag", "sql_rag"]
    role: str
    access_denied: bool = False
    denied_collections: list[str] = Field(default_factory=list)
    accessible_collections: list[str] = Field(default_factory=list)
    route_method: str | None = None
    llm_used: bool = True
    sql: str | None = None
    sql_row_count: int | None = None
    candidates: list[RankedCandidate] = Field(default_factory=list)


class CollectionsResponse(BaseModel):
    role: str
    role_label: str
    collections: list[CollectionInfo]
    restricted: list[CollectionInfo]
    can_use_sql: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    qdrant: dict[str, object]
    llm_configured: bool
    llm_provider: str
    llm_model: str
    database: bool


class ErrorResponse(BaseModel):
    detail: str
