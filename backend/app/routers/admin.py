"""Admin endpoints: dashboard stats, users, refunds, inventory."""

import logging

from fastapi import APIRouter, Query
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


@router.get("/inventory")
async def inventory_summary(user: AdminUser, session: DbSession) -> dict:
    """Stock health across the catalog: counts, units and inventory value."""
    row = (
        await session.execute(
            text(
                "SELECT COUNT(*) AS total_products, "
                "  COALESCE(SUM(stock), 0) AS total_units, "
                "  COALESCE(SUM(price * stock), 0) AS inventory_value, "
                "  COALESCE(SUM(1) FILTER (WHERE stock <= 0), 0) AS out_of_stock, "
                "  COALESCE(SUM(1) FILTER (WHERE stock > 0 AND stock <= low_stock_threshold), 0) "
                "    AS low_stock "
                "FROM public.products WHERE active"
            )
        )
    ).mappings().first()
    variant_row = (
        await session.execute(
            text(
                "SELECT COUNT(*) AS total_variants, "
                "  COALESCE(SUM(1) FILTER (WHERE stock <= 0), 0) AS out_of_stock "
                "FROM public.product_variants WHERE active"
            )
        )
    ).mappings().first()
    return {
        "totalProducts": int(row["total_products"]),
        "totalUnits": int(row["total_units"]),
        "inventoryValue": int(row["inventory_value"]),
        "outOfStock": int(row["out_of_stock"]),
        "lowStock": int(row["low_stock"]),
        "totalVariants": int(variant_row["total_variants"]),
        "variantsOutOfStock": int(variant_row["out_of_stock"]),
    }


@router.get("/inventory/low-stock")
async def low_stock(
    user: AdminUser,
    session: DbSession,
    threshold: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    """Products at or below their low-stock threshold, plus deactivated variants.

    `threshold` overrides each product's own `low_stock_threshold`.
    """
    products = (
        await session.execute(
            text(
                "SELECT id, name, category, stock, low_stock_threshold "
                "FROM public.products "
                "WHERE active AND stock <= COALESCE(:threshold, low_stock_threshold) "
                "ORDER BY stock ASC, name LIMIT :limit"
            ),
            {"threshold": threshold, "limit": limit},
        )
    ).mappings().all()
    variants = (
        await session.execute(
            text(
                "SELECT v.id, v.product_id, p.name AS product_name, v.size, v.color, v.stock "
                "FROM public.product_variants v JOIN public.products p ON p.id = v.product_id "
                "WHERE v.active AND v.stock <= COALESCE(:threshold, p.low_stock_threshold) "
                "ORDER BY v.stock ASC LIMIT :limit"
            ),
            {"threshold": threshold, "limit": limit},
        )
    ).mappings().all()
    return {
        "products": [
            {
                "id": r["id"],
                "name": r["name"],
                "category": r["category"],
                "stock": int(r["stock"]),
                "low_stock_threshold": int(r["low_stock_threshold"]),
            }
            for r in products
        ],
        "variants": [
            {
                "id": str(r["id"]),
                "product_id": r["product_id"],
                "product_name": r["product_name"],
                "size": r["size"],
                "color": r["color"],
                "stock": int(r["stock"]),
            }
            for r in variants
        ],
    }


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
