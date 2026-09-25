"""Customer tiers (AB-FE-06, decision D7b) — the one canonical implementation.

Semantics (D7b, binding for AB-FE-06):

    New       = fewer than 3 delivered orders
    VIP       = 3 or more delivered orders
    Wholesale = explicitly assigned by staff (takes precedence over New/VIP)

The tier is a **customer classification, not an authorization role**:
`role != tier`. Automatic New/VIP is a pure function of the delivered-order
count and is never stored; the explicit Wholesale flag lives in `user_tiers`
(DML-only table, no DDL by the app role — created by `startup_ddl()`), so a
Wholesale customer is not automatically a staff user and vice versa.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# D7b thresholds — the only place the 3-delivered-orders rule lives.
VIP_DELIVERED_ORDERS = 3

TIERS = ("new", "vip", "wholesale")


def resolve_tier(delivered_orders: int, explicit_tier: str | None) -> str:
    """Pure D7b rule: explicit tier wins, else delivered-count based.

    `explicit_tier` is what `user_tiers` holds today (only 'wholesale' exists);
    anything unknown is ignored, so a legacy/bogus row cannot fake a tier.
    """
    if explicit_tier == "wholesale":
        return "wholesale"
    return "vip" if delivered_orders >= VIP_DELIVERED_ORDERS else "new"


async def resolve_tier_for_user(session: AsyncSession, user_id) -> str:
    """The user's tier, from their delivered orders plus any explicit flag."""
    row = (
        await session.execute(
            text(
                "SELECT COALESCE(t.tier, '') AS explicit_tier, "
                "(SELECT COUNT(*) FROM public.orders o "
                " WHERE o.user_id = CAST(:uid AS uuid) AND o.status = 'delivered') "
                "AS delivered "
                "FROM public.users u "
                "LEFT JOIN public.user_tiers t ON t.user_id = u.id "
                "WHERE u.id = CAST(:uid AS uuid)"
            ),
            {"uid": str(user_id)},
        )
    ).mappings().first()
    if row is None:
        raise LookupError(f"user {user_id} not found")
    return resolve_tier(int(row["delivered"]), row["explicit_tier"] or None)


async def get_explicit_tier(session: AsyncSession, user_id) -> str | None:
    """The staff-assigned tier from `user_tiers`, or None."""
    row = await session.execute(
        text("SELECT tier FROM public.user_tiers WHERE user_id = CAST(:uid AS uuid)"),
        {"uid": str(user_id)},
    )
    return row.scalar()


async def set_explicit_tier(session: AsyncSession, user_id, tier: str | None, actor_id) -> None:
    """Set (or clear) the explicit tier; the caller audits + commits."""
    if tier is None:
        await session.execute(
            text("DELETE FROM public.user_tiers WHERE user_id = CAST(:uid AS uuid)"),
            {"uid": str(user_id)},
        )
        return
    await session.execute(
        text(
            "INSERT INTO public.user_tiers (user_id, tier, updated_by, updated_at) "
            "VALUES (CAST(:uid AS uuid), :tier, CAST(:actor AS uuid), now()) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            "  tier = EXCLUDED.tier, updated_by = EXCLUDED.updated_by, updated_at = now()"
        ),
        {"uid": str(user_id), "tier": tier, "actor": str(actor_id)},
    )
