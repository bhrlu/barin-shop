"""Role-based FastAPI dependencies backed by the backend's own JWTs.

Tokens are issued by /auth/login (HS256, aud=authenticated). The caller's
role comes from the token claim and is cross-checked against public.user_roles.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


class AuthUser:
    """Authenticated caller extracted from the backend's own JWT."""

    def __init__(self, user_id: UUID, email: str | None, role: str):
        self.id = user_id
        self.email = email
        self.role = role  # "admin" | "customer"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")

    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}") from exc

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has no subject")

    user_id = UUID(sub)
    role = await _resolve_role(session, user_id, payload.get("role"))
    return AuthUser(user_id=user_id, email=payload.get("email"), role=role)


async def _resolve_role(session: AsyncSession, user_id: UUID, token_role: str | None) -> str:
    """DB is the source of truth; fall back to the token claim, then customer."""
    row = await session.execute(
        text("SELECT role FROM public.user_roles WHERE user_id = :uid"),
        {"uid": str(user_id)},
    )
    roles = {r[0] for r in row.all()}
    if "admin" in roles:
        return "admin"
    if "customer" in roles:
        return "customer"
    return token_role if token_role in ("admin", "customer") else "customer"


async def require_admin(
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> AuthUser:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthUser | None:
    """Resolve the caller when a valid token is present; anonymous otherwise.

    Used by endpoints that work for everyone but personalise for signed-in users
    (e.g. saving search history).
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        sub = payload.get("sub")
        if not sub:
            return None
        user_id = UUID(sub)
        role = await _resolve_role(session, user_id, payload.get("role"))
    except (JWTError, ValueError):
        return None
    return AuthUser(user_id=user_id, email=payload.get("email"), role=role)


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
AdminUser = Annotated[AuthUser, Depends(require_admin)]
OptionalUser = Annotated[AuthUser | None, Depends(get_optional_user)]
DbSession = Annotated[AsyncSession, Depends(get_session)]
