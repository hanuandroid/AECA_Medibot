"""MediBot FastAPI application.

Endpoints: POST /login, POST /chat, GET /collections/{role}, GET /health
Run: ``uvicorn app.api.main:app --reload`` (from backend/)
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat_service import handle_chat
from app.api.deps import CurrentUser
from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    CollectionInfo,
    CollectionsResponse,
    HealthResponse,
    LoginRequest,
    LoginResponse,
)
from app.auth.tokens import create_access_token
from app.auth.users import UsersNotConfiguredError, authenticate
from app.config import get_settings
from app.rbac import (
    COLLECTION_LABELS,
    ROLE_LABELS,
    Role,
    UnknownRoleError,
    allowed_collections,
    can_use_sql,
    parse_role,
    restricted_collections,
)
from app.retrieval.hybrid import RBACViolationError
from app.retrieval.qdrant_store import index_status

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    if get_settings().warmup_models:
        from app.retrieval.embeddings import warmup

        logger.info("Warming up embedding and reranker models...")
        warmup()
    yield


app = FastAPI(
    title="MediBot API",
    description="Advanced RAG assistant for MediAssist Health Network with Qdrant-level RBAC.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    s = get_settings()
    qdrant = index_status()
    ok = bool(qdrant.get("reachable")) and bool(qdrant.get("points"))
    return HealthResponse(
        status="ok" if ok else "degraded",
        qdrant=qdrant,
        llm_configured=s.llm_configured,
        llm_provider=s.llm_provider,
        llm_model=s.llm_model,
        database=s.sqlite_path.exists(),
    )


@app.post("/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    try:
        user = authenticate(body.username, body.password)
    except UsersNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    token, expires = create_access_token(user.username, user.role, user.display_name)
    return LoginResponse(
        access_token=token,
        expires_at=expires,
        username=user.username,
        display_name=user.display_name,
        role=user.role.value,
        collections=[c.value for c in allowed_collections(user.role)],
    )


@app.get("/collections/{role}", response_model=CollectionsResponse)
def collections(role: str, user: CurrentUser) -> CollectionsResponse:
    try:
        requested = parse_role(role)
    except UnknownRoleError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown role: {role}") from exc
    if requested != user.role and user.role != Role.ADMIN:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You can only view the collections of your own role"
        )
    return CollectionsResponse(
        role=requested.value,
        role_label=ROLE_LABELS[requested],
        collections=[
            CollectionInfo(name=c.value, label=COLLECTION_LABELS[c])
            for c in allowed_collections(requested)
        ],
        restricted=[
            CollectionInfo(name=c.value, label=COLLECTION_LABELS[c])
            for c in restricted_collections(requested)
        ],
        can_use_sql=can_use_sql(requested),
    )


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, user: CurrentUser) -> ChatResponse:
    # The role comes exclusively from the verified token (ChatRequest has no role field).
    try:
        return handle_chat(body.question.strip(), user.role)
    except RBACViolationError:
        logger.exception("RBAC tripwire fired")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Access-control check failed"
        ) from None
