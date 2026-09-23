"""Role resolution shared by auth dependencies and routers (B5.4).

Staff roles per spec [BE-04]: `super_admin` > `order_manager` > `support`,
plus the legacy `admin` which keeps full staff access (Rule 4 — existing rows
never break). Roles stay in `user_roles`, never on the user row.
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# legacy role kept for compatibility with existing rows
STAFF_ROLES = {"admin", "super_admin", "order_manager", "support"}

# route → roles granted the capability; anything absent is admin/super_admin-only
# (spec names the roles but not the matrix — mapped by role semantics:
#  order_manager owns fulfillment + refund settlement; support is the
#  customer-facing trio of inbox/reviews/KPIs and cannot move money or stock)
ROLE_CAPABILITIES: dict[str, set[str]] = {
    # fulfillment — order_manager owns it, support escalates via the inbox
    "orders": {"admin", "super_admin", "order_manager"},
    "refunds": {"admin", "super_admin", "order_manager"},
    "contact_inbox": STAFF_ROLES,
    # catalog & marketing — support is read-mostly, so catalog edits are
    # super_admin/order_manager only
    "catalog": {"admin", "super_admin", "order_manager"},
    "coupons": {"admin", "super_admin", "order_manager"},
    # sensitive: moderation + user administration
    "reviews": {"admin", "super_admin", "support"},
    "users": {"admin", "super_admin"},
    "audit": {"admin", "super_admin"},
    "stats": STAFF_ROLES,
    # store-wide switches (B2.1 notification channels) — top admins only
    "settings": {"admin", "super_admin"},
}


async def resolve_roles(session: AsyncSession, user_id: UUID) -> set[str]:
    """All roles the user holds; defaults to {'customer'}."""
    row = await session.execute(
        text("SELECT role FROM public.user_roles WHERE user_id = :uid"),
        {"uid": str(user_id)},
    )
    roles = {r[0] for r in row.all()}
    return roles or {"customer"}


async def resolve_role(session: AsyncSession, user_id: UUID) -> str:
    """Highest-privilege role for display purposes; default to customer."""
    roles = await resolve_roles(session, user_id)
    for role in ("super_admin", "admin", "order_manager", "support", "customer"):
        if role in roles:
            return role
    return "customer"


def has_capability(roles: set[str], capability: str) -> bool:
    """Can any of the caller's roles exercise this capability?"""
    required = ROLE_CAPABILITIES.get(capability, {"admin", "super_admin"})
    return bool(roles & required)


def role_lockout_reason(
    *, is_self: bool, target_roles_after: set[str], other_users_holders: int
) -> str | None:
    """Why a role change must be refused (B5.4a), or None when it is allowed.

    The `users` capability is the only way to repair roles from the UI, so a change
    may neither take it from the caller themselves nor leave nobody holding it
    (`other_users_holders` counts every *other* account that holds it).
    """
    keeps = has_capability(target_roles_after, "users")
    if is_self and not keeps:
        return "نمی‌توانید دسترسی مدیریت کاربران را از حساب خودتان بردارید"
    if other_users_holders + (1 if keeps else 0) == 0:
        return "دست‌کم یک حساب باید دسترسی مدیریت کاربران را نگه دارد"
    return None
