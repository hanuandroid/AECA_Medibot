"""Hybrid RAG answer pipeline: RBAC-filtered hybrid retrieval -> rerank -> LLM with citations."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.config import get_settings
from app.llm.client import LLMClient, get_llm
from app.llm.prompts import RAG_SYSTEM_PROMPT, RAG_USER_TEMPLATE
from app.rbac import ROLE_LABELS, Role, describe_access
from app.retrieval.hybrid import hybrid_search
from app.retrieval.models import RetrievedChunk
from app.retrieval.reranker import rerank

logger = logging.getLogger(__name__)


@dataclass
class RagResult:
    answer: str
    used_chunks: list[RetrievedChunk]  # the reranked top-k actually sent to the LLM
    candidates: list[RetrievedChunk] = field(default_factory=list)  # full hybrid candidate set


def build_context(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for i, c in enumerate(chunks, start=1):
        blocks.append(f"[{i}] Source: {c.context_header} (collection: {c.collection})\n{c.text}")
    return "\n\n".join(blocks)


def answer_with_documents(question: str, role: Role, *, llm: LLMClient | None = None) -> RagResult:
    s = get_settings()
    candidates = hybrid_search(question, role, limit=s.retrieval_candidates)
    if not candidates:
        return RagResult(
            answer=(
                "I could not find any relevant information in the documents available to your "
                f"role. As a {ROLE_LABELS[role].lower()} you can search {describe_access(role)}."
            ),
            used_chunks=[],
            candidates=[],
        )
    top = rerank(question, candidates, top_k=s.rerank_top_k)
    prompt = RAG_USER_TEMPLATE.format(
        role=ROLE_LABELS[role], context=build_context(top), question=question
    )
    answer = (llm or get_llm()).complete(RAG_SYSTEM_PROMPT, prompt, max_tokens=900)
    return RagResult(answer=answer, used_chunks=top, candidates=candidates)
