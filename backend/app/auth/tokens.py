"""Role-tagged session tokens (JWT, HS256). The role claim is the only source of the role."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt

from app.config import get_settings
from app.rbac import Role, UnknownRoleError, parse_role

logger = logging.getLogger(__name__)

ISSUER = "medibot"


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class TokenData:
    username: str
    role: Role
    display_name: str
    expires_at: datetime


@lru_cache(maxsize=1)
def _secret() -> str:
    secret = get_settings().jwt_secret
    if not secret:
        logger.warning("JWT_SECRET not set - using an ephemeral per-process secret")
        secret = secrets.token_urlsafe(48)
    if len(secret) < 32:
        raise AuthError("JWT_SECRET must be at least 32 characters")
    return secret


def create_access_token(username: str, role: Role, display_name: str = "") -> tuple[str, datetime]:
    s = get_settings()
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=s.jwt_expiry_minutes)
    claims = {
        "sub": username,
        "role": role.value,
        "name": display_name or username,
        "iss": ISSUER,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    return jwt.encode(claims, _secret(), algorithm=s.jwt_algorithm), expires


def decode_token(token: str) -> TokenData:
    s = get_settings()
    try:
        claims = jwt.decode(
            token,
            _secret(),
            algorithms=[s.jwt_algorithm],
            issuer=ISSUER,
            options={"require": ["sub", "role", "exp", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Session expired - please log in again") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid session token") from exc
    try:
        role = parse_role(str(claims["role"]))
    except UnknownRoleError as exc:
        raise AuthError("Token carries an unknown role") from exc
    return TokenData(
        username=str(claims["sub"]),
        role=role,
        display_name=str(claims.get("name") or claims["sub"]),
        expires_at=datetime.fromtimestamp(int(claims["exp"]), tz=UTC),
    )
