"""Role-based FastAPI dependencies backed by the backend's own JWTs.

Tokens are issued by /auth/login (HS256, aud=authenticated). The caller's
roles come from the token claim and are cross-checked against public.user_roles
(DB is the source of truth). Staff authorization is capability-based (B5.4):
routes declare what they need via `require_staff(capability)`, and
`app/services/roles.py::ROLE_CAPABILITIES` maps capabilities to staff roles.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.security import decode_access_token
from app.services.roles import has_capability, resolve_roles

bearer_scheme = HTTPBearer(auto_error=False)


class AuthUser:
    """Authenticated caller extracted from the backend's own JWT."""

    def __init__(self, user_id: UUID, email: str | None, roles: set[str]):
        self.id = user_id
        self.email = email
        self.roles = roles  # {"customer"} or a mix of staff roles

    @property
    def role(self) -> str:
        """Highest-privilege role (display/compat; authorization uses roles)."""
        for role in ("super_admin", "admin", "order_manager", "support", "customer"):
            if role in self.roles:
                return role
        return "customer"

    @property
    def is_admin(self) -> bool:
        return bool(self.roles & {"admin", "super_admin"})


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
    if await _session_revoked(session, user_id, payload.get("iat")):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "نشست شما پایان یافته است؛ دوباره وارد شوید"
        )
    roles = await _resolve_roles(session, user_id, payload.get("role"))
    return AuthUser(user_id=user_id, email=payload.get("email"), roles=roles)


async def _session_revoked(session: AsyncSession, user_id: UUID, issued_at) -> bool:
    """B6.14: a token issued before the account's last password change is dead.

    JWTs are stateless for 7 days, so without this a token stolen before a reset
    kept working after it. `iat` is whole seconds, so the cutoff is compared at
    whole-second precision: the login right after a reset (same second) must work;
    the price is that a token issued in that same second before the reset survives.
    """
    cutoff = (
        await session.execute(
            text(
                "SELECT floor(extract(epoch FROM password_changed_at)) "
                "FROM public.users WHERE id = :uid"
            ),
            {"uid": str(user_id)},
        )
    ).scalar()
    if cutoff is None:
        return False  # never changed through a reset (or no such user): no cutoff
    try:
        return int(issued_at) < int(cutoff)
    except (TypeError, ValueError):
        return True  # a token without a usable `iat` cannot prove it is newer


async def _resolve_roles(session: AsyncSession, user_id: UUID, token_role: str | None) -> set[str]:
    """DB is the source of truth for privileges.

    The token's `role` claim is never promoted to a staff role: a user demoted in
    `user_roles` would otherwise keep admin access until their (7-day) token
    expired. Only the harmless `customer` default is taken from the claim, for
    rows seeded before the role table existed.
    """
    roles = await resolve_roles(session, user_id)
    if roles == {"customer"} and token_role == "customer":
        return {"customer"}
    return roles


async def require_admin(
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> AuthUser:
    """Only `admin` / `super_admin` pass (`AuthUser.is_admin`). Other staff roles are
    refused — guard staff routes with `require_staff(<capability>)` instead (B6.17)."""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


def require_staff(capability: str) -> Callable[[AuthUser], AuthUser]:
    """Dependency factory: any staff role granted this capability passes.

    Per spec [BE-04] the role check happens here, per route, from the DB-backed
    role set — never from a column on the user row.
    """

    async def _guard(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
        if not has_capability(user.roles, capability):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "دسترسی لازم برای این بخش را ندارید"
            )
        return user

    return _guard


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
        if await _session_revoked(session, user_id, payload.get("iat")):
            return None  # an ended session is just an anonymous caller here
        roles = await _resolve_roles(session, user_id, payload.get("role"))
    except (JWTError, ValueError):
        return None
    return AuthUser(user_id=user_id, email=payload.get("email"), roles=roles)


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
AdminUser = Annotated[AuthUser, Depends(require_admin)]
OptionalUser = Annotated[AuthUser | None, Depends(get_optional_user)]

# per-capability staff guards (B5.4) — import and annotate routes with these
StaffOrders = Annotated[AuthUser, Depends(require_staff("orders"))]
StaffRefunds = Annotated[AuthUser, Depends(require_staff("refunds"))]
StaffCatalog = Annotated[AuthUser, Depends(require_staff("catalog"))]
StaffCoupons = Annotated[AuthUser, Depends(require_staff("coupons"))]
StaffReviews = Annotated[AuthUser, Depends(require_staff("reviews"))]
StaffContactInbox = Annotated[AuthUser, Depends(require_staff("contact_inbox"))]
StaffUsers = Annotated[AuthUser, Depends(require_staff("users"))]
StaffStats = Annotated[AuthUser, Depends(require_staff("stats"))]
StaffAudit = Annotated[AuthUser, Depends(require_staff("audit"))]
StaffSettings = Annotated[AuthUser, Depends(require_staff("settings"))]
DbSession = Annotated[AsyncSession, Depends(get_session)]
