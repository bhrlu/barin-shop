"""Admin endpoints: dashboard stats, user list, refund requests list."""

import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.auth import AdminUser, DbSession

log = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
async def stats(user: AdminUser, session: DbSession) -> dict:
    revenue, pending, order_count = (
        await session.execute(
            text(
                "SELECT COALESCE(SUM(total) FILTER (WHERE status <> 'cancelled'), 0), "
                "       COALESCE(SUM(1) FILTER (WHERE status = 'pending'), 0), "
                "       COUNT(*) FROM public.orders"
            )
        )
    ).first()
    product_count, out_of_stock = (
        await session.execute(
            text(
                "SELECT COUNT(*), COALESCE(SUM(1) FILTER (WHERE stock <= 0), 0) "
                "FROM public.products"
            )
        )
    ).first()
    user_count = (await session.execute(text("SELECT COUNT(*) FROM public.profiles"))).scalar_one()

    latest_rows = (
        await session.execute(
            text(
                "SELECT id, order_number, status, total, created_at FROM public.orders "
                "ORDER BY created_at DESC LIMIT 5"
            )
        )
    ).mappings().all()

    return {
        "revenue": int(revenue or 0),
        "orderCount": int(order_count or 0),
        "pending": int(pending or 0),
        "productCount": int(product_count or 0),
        "outOfStock": int(out_of_stock or 0),
        "userCount": int(user_count or 0),
        "latest": [dict(r) for r in latest_rows],
    }


@router.get("/users")
async def users(user: AdminUser, session: DbSession) -> list[dict]:
    rows = (
        await session.execute(
            text(
                "SELECT p.id, p.full_name, p.phone, p.avatar_url, p.created_at, u.email, "
                "COALESCE(r.roles, '{}') AS roles, "
                "COALESCE(o.order_count, 0) AS order_count, "
                "COALESCE(o.spent, 0) AS spent "
                "FROM public.profiles p "
                "JOIN public.users u ON u.id = p.id "
                "LEFT JOIN (SELECT user_id, array_agg(role::text) AS roles "
                "           FROM public.user_roles GROUP BY user_id) r ON r.user_id = p.id "
                "LEFT JOIN (SELECT user_id, COUNT(*) AS order_count, "
                "                  SUM(total) FILTER (WHERE status <> 'cancelled') AS spent "
                "           FROM public.orders GROUP BY user_id) o ON o.user_id = p.id "
                "ORDER BY p.created_at DESC"
            )
        )
    ).mappings().all()
    return [
        {
            **dict(r),
            "roles": list(r["roles"]),
            "order_count": int(r["order_count"]),
            "spent": int(r["spent"]),
        }
        for r in rows
    ]


@router.get("/refunds")
async def refunds(user: AdminUser, session: DbSession) -> list[dict]:
    rows = (
        await session.execute(
            text(
                "SELECT rr.*, o.order_number FROM public.refund_requests rr "
                "JOIN public.orders o ON o.id = rr.order_id "
                "ORDER BY rr.created_at DESC"
            )
        )
    ).mappings().all()
    return [dict(r) for r in rows]


@router.get("/orders")
async def all_orders(user: AdminUser, session: DbSession) -> list[dict]:
    """All orders with items — same shape as GET /orders but unscoped."""
    from app.routers.orders import _ORDER_SELECT, _order_row

    rows = (
        await session.execute(
            text(_ORDER_SELECT + " GROUP BY o.id ORDER BY o.created_at DESC")
        )
    ).mappings().all()
    return [_order_row(r) for r in rows]


@router.get("/payments")
async def all_payments(user: AdminUser, session: DbSession) -> list[dict]:
    rows = (
        await session.execute(
            text(
                "SELECT pm.id, pm.order_id, pm.user_id, pm.amount, pm.method, pm.status, "
                "pm.reference, pm.created_at, o.order_number "
                "FROM public.payments pm JOIN public.orders o ON o.id = pm.order_id "
                "ORDER BY pm.created_at DESC"
            )
        )
    ).mappings().all()
    return [dict(r) for r in rows]
