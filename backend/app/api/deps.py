"""FastAPI dependencies: authentication from the bearer token."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.tokens import AuthError, TokenData, decode_token

_bearer = HTTPBearer(auto_error=False)


def current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> TokenData:
    """The authenticated identity. The role used anywhere downstream comes from here only."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decode_token(creds.credentials)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


CurrentUser = Annotated[TokenData, Depends(current_user)]
