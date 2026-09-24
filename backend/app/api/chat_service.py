"""/chat orchestration: route -> (SQL RAG | hybrid RAG) with RBAC, build the response.

Security boundaries (independent of the router's opinion):
* document retrieval is always Qdrant-filtered by the authenticated role;
* SQL RAG only runs for roles in ``SQL_ROLES``.
The router's collection guess is used only to give a clear, specific denial message.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.api.schemas import ChatResponse, RankedCandidate, Source
from app.llm.client import LLMClient, LLMError, LLMNotConfiguredError, get_llm
from app.rag.pipeline import RagResult, answer_with_documents
from app.rbac import (
    ROLE_LABELS,
    Collection,
    Role,
    allowed_collections,
    can_use_sql,
    describe_access,
)
from app.retrieval.hybrid import hybrid_search
from app.retrieval.models import RetrievedChunk
from app.retrieval.reranker import rerank
from app.router import RouteDecision, route_question
from app.sql_rag.chain import SQLRagError, run_sql_rag

logger = logging.getLogger(__name__)

Router = Callable[[str, LLMClient | None], RouteDecision]


def _article(label: str) -> str:
    return "an" if label[0].lower() in "aeiou" else "a"


def document_denial_message(role: Role, denied: list[Collection]) -> str:
    label = ROLE_LABELS[role].lower()
    names = " and ".join(c.value for c in denied)
    return (
        f"As {_article(label)} {label}, you don't have access to {names} documents. "
        f"I can only answer questions from {describe_access(role)}."
    )


def sql_denial_message(role: Role) -> str:
    label = ROLE_LABELS[role].lower()
    return (
        f"As {_article(label)} {label}, you don't have access to the operations analytics "
        "database (billing claims and maintenance tickets). Analytical SQL queries are available "
        "to billing executives and admins only. I can answer questions from "
        f"{describe_access(role)}."
    )


def sources_from_chunks(chunks: list[RetrievedChunk]) -> list[Source]:
    """One citation per chunk sent to the LLM (de-duplicated by document + section)."""
    seen: set[tuple[str, str]] = set()
    sources: list[Source] = []
    for c in chunks:
        key = (c.source_document, c.section_title)
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            Source(
                source_document=c.source_document,
                section_title=c.section_title,
                collection=c.collection,
                chunk_type=c.chunk_type,
                page_numbers=c.page_numbers,
                rerank_score=c.rerank_score,
            )
        )
    return sources


def ranked_candidates(rag: RagResult) -> list[RankedCandidate]:
    used = {c.point_id for c in rag.used_chunks}
    return [
        RankedCandidate(
            source_document=c.source_document,
            section_title=c.section_title,
            collection=c.collection,
            initial_rank=c.initial_rank,
            fusion_score=round(c.retrieval_score, 5),
            rerank_score=None if c.rerank_score is None else round(c.rerank_score, 4),
            final_rank=c.final_rank,
            sent_to_llm=c.point_id in used,
        )
        for c in sorted(rag.candidates, key=lambda c: c.initial_rank)
    ]


def _extractive_fallback(question: str, role: Role) -> RagResult:
    """Used only when no LLM is configured: show the reranked passages verbatim (labelled)."""
    candidates = hybrid_search(question, role)
    top = rerank(question, candidates)
    if not top:
        answer = (
            "No relevant passages were found in the documents available to your role "
            f"({describe_access(role)})."
        )
    else:
        parts = [
            f"[{i}] {c.source_document} - {c.section_title}\n{c.text}"
            for i, c in enumerate(top, start=1)
        ]
        answer = (
            "The language model is not configured, so here are the most relevant passages "
            "verbatim:\n\n" + "\n\n".join(parts)
        )
    return RagResult(answer=answer, used_chunks=top, candidates=candidates)


def handle_chat(
    question: str,
    role: Role,
    *,
    llm: LLMClient | None = None,
    router: Router = route_question,
) -> ChatResponse:
    accessible = [c.value for c in allowed_collections(role)]
    decision = router(question, llm)

    if decision.route == "sql":
        if not can_use_sql(role):
            logger.info("RBAC: SQL RAG denied for role=%s", role.value)
            return ChatResponse(
                answer=sql_denial_message(role),
                retrieval_type="sql_rag",
                role=role.value,
                access_denied=True,
                denied_collections=["operations_database"],
                accessible_collections=accessible,
                route_method=decision.method,
                llm_used=False,
            )
        try:
            result = run_sql_rag(question, llm=llm)
        except LLMNotConfiguredError as exc:
            return ChatResponse(
                answer=f"SQL analytics needs the language model, which is not configured. {exc}",
                retrieval_type="sql_rag",
                role=role.value,
                accessible_collections=accessible,
                route_method=decision.method,
                llm_used=False,
            )
        except SQLRagError as exc:
            return ChatResponse(
                answer=(
                    "I couldn't translate that question into a safe, valid database query. "
                    f"Please rephrase it. ({exc})"
                ),
                retrieval_type="sql_rag",
                role=role.value,
                accessible_collections=accessible,
                route_method=decision.method,
            )
        return ChatResponse(
            answer=result.answer,
            sources=[],
            retrieval_type="sql_rag",
            role=role.value,
            accessible_collections=accessible,
            route_method=decision.method,
            sql=result.sql,
            sql_row_count=len(result.result.rows),
        )

    allowed = set(allowed_collections(role))
    denied = [c for c in decision.collections if c not in allowed]
    if decision.collections and len(denied) == len(decision.collections):
        # Every collection the question targets is off-limits: explain instead of answering
        # from unrelated permitted documents. (Retrieval would be RBAC-filtered regardless.)
        logger.info("RBAC: role=%s asked about restricted %s", role.value, denied)
        return ChatResponse(
            answer=document_denial_message(role, denied),
            retrieval_type="hybrid_rag",
            role=role.value,
            access_denied=True,
            denied_collections=[c.value for c in denied],
            accessible_collections=accessible,
            route_method=decision.method,
            llm_used=False,
        )

    llm_used = True
    try:
        rag = answer_with_documents(question, role, llm=llm or get_llm())
    except (LLMNotConfiguredError, LLMError) as exc:
        logger.warning("LLM unavailable (%s) - returning extractive answer", exc)
        rag = _extractive_fallback(question, role)
        llm_used = False

    answer = rag.answer
    if denied:
        answer = (
            f"Note: part of your question concerns {', '.join(c.value for c in denied)} "
            f"documents, which your role cannot access; this answer uses only "
            f"{describe_access(role)}.\n\n{answer}"
        )
    return ChatResponse(
        answer=answer,
        sources=sources_from_chunks(rag.used_chunks),
        retrieval_type="hybrid_rag",
        role=role.value,
        denied_collections=[c.value for c in denied],
        accessible_collections=accessible,
        route_method=decision.method,
        llm_used=llm_used,
        candidates=ranked_candidates(rag),
    )
