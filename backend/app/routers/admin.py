"""Admin endpoints: dashboard stats, users, refunds, inventory, KPIs, audit log."""

import logging
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import text

from app.auth import DbSession, StaffAudit, StaffOrders, StaffRefunds, StaffStats, StaffUsers
from app.services.audit import record_audit
from app.services.catalog_filters import split_multi
from app.services.pagination import clamp_page_size, count_rows, envelope
from app.services.roles import ROLE_CAPABILITIES, STAFF_ROLES, role_lockout_reason

log = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

_KPI_RANGES = {"today": "1 day", "7d": "7 days", "30d": "30 days", "all": None}


def _iso(value):
    return value.isoformat() if value is not None else None


@router.get("/stats")
async def stats(user: StaffStats, session: DbSession) -> dict:
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


# F4.3 (admin data table): optional server-side search / filter / sort for the admin
# lists; omitted parameters keep the old answer exactly
_USER_SORTS = {
    "new": "p.created_at DESC",
    "spent": "COALESCE(o.spent, 0) DESC, p.created_at DESC",
    "orders": "COALESCE(o.order_count, 0) DESC, p.created_at DESC",
}
_STAFF_ROLE_LIST = sorted(STAFF_ROLES)


def _like(term: str) -> str:
    """`%term%` with LIKE wildcards in the term escaped (`\\` is the default escape)."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get("/users")
async def users(
    user: StaffUsers,
    session: DbSession,
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=0, ge=0, le=100),
    q: str | None = Query(default=None, max_length=100, description="email, name or phone"),
    role: Literal["staff", "customer"] | None = None,
    sort: Literal["new", "spent", "orders"] = "new",
) -> list[dict] | dict:
    """Customers with role/order aggregates; envelope when `page` is given."""
    base_sql = (
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
        "           FROM public.orders GROUP BY user_id) o ON o.user_id = p.id"
    )
    conditions: list[str] = []
    params: dict = {}
    if q and q.strip():
        conditions.append(
            "(u.email ILIKE :q OR p.full_name ILIKE :q OR p.phone ILIKE :q)"
        )
        params["q"] = _like(q.strip())
    if role is not None:
        staff = "COALESCE(r.roles, '{}') && CAST(:staff AS text[])"
        conditions.append(staff if role == "staff" else f"NOT ({staff})")
        params["staff"] = _STAFF_ROLE_LIST
    if conditions:
        base_sql += " WHERE " + " AND ".join(conditions)
    page, page_size = clamp_page_size(page, page_size, default_size=20)
    sql = base_sql + " ORDER BY " + _USER_SORTS[sort]
    total = 0
    if page > 0:
        total = await count_rows(session, base_sql, params)
        sql += f" LIMIT {page_size} OFFSET {(page - 1) * page_size}"
    rows = (await session.execute(text(sql), params)).mappings().all()
    items = [
        {
            **dict(r),
            "roles": list(r["roles"]),
            "order_count": int(r["order_count"]),
            "spent": int(r["spent"]),
        }
        for r in rows
    ]
    if page > 0:
        return envelope(items, total, page, page_size)
    return items


@router.get("/refunds")
async def refunds(user: StaffRefunds, session: DbSession) -> list[dict]:
    """All refund requests with the claimant's contact details and, for settled
    ones, who resolved them ([BE-03] resolved_by → profiles/users)."""
    rows = (
        await session.execute(
            text(
                "SELECT rr.*, o.order_number, u.email AS user_email, "
                "COALESCE(p.full_name, u.email) AS user_name "
                "FROM public.refund_requests rr "
                "JOIN public.orders o ON o.id = rr.order_id "
                "JOIN public.users u ON u.id = rr.user_id "
                "LEFT JOIN public.profiles p ON p.id = rr.user_id "
                "ORDER BY rr.created_at DESC"
            )
        )
    ).mappings().all()
    return [dict(r) for r in rows]


@router.get("/kpis")
async def kpis(
    user: StaffStats,
    session: DbSession,
    range: str = Query(default="30d"),
) -> dict:
    """Dashboard KPI aggregation (spec [BE-09], B5.2).

    Replaces the client-side aggregation the dashboard used to do. `range`
    windows the *revenue/orders* metrics; refunds and low-stock counts are
    store-wide. Deltas compare the window against the preceding window of the
    same length ('all' has no delta).
    """
    if range not in _KPI_RANGES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "بازه نامعتبر است")
    window = _KPI_RANGES[range]

    if window is None:
        where = "WHERE o.status <> 'cancelled'"
        prev_where = "WHERE FALSE"
    else:
        where = (
            f"WHERE o.status <> 'cancelled' "
            f"AND o.created_at >= now() - INTERVAL '{window}'"
        )
        prev_where = (
            f"WHERE o.status <> 'cancelled' "
            f"AND o.created_at >= now() - INTERVAL '{window}' * 2 "
            f"AND o.created_at < now() - INTERVAL '{window}'"
        )

    async def _period(conditions: str) -> dict:
        row = (
            await session.execute(
                text(
                    "SELECT COALESCE(SUM(o.total), 0) AS gross, "
                    "  COALESCE(SUM(o.total) FILTER (WHERE o.payment_status = 'paid'), 0) "
                    "    AS net, "
                    "  COALESCE(COUNT(*) FILTER (WHERE o.payment_status = 'paid'), 0) "
                    "    AS paid_orders "
                    "FROM public.orders o "
                    + conditions
                )
            )
        ).mappings().first()
        gross, net, paid = int(row["gross"]), int(row["net"]), int(row["paid_orders"])
        return {
            "gross": gross,
            "net": net,
            "paidOrders": paid,
            "aov": round(net / paid) if paid else 0,
        }

    current = await _period(where)
    previous = await _period(prev_where)

    def _delta(cur: int, prev: int) -> int | None:
        if window is None or prev == 0:
            return None
        return round((cur - prev) / prev * 100)

    pending_refunds = (
        await session.execute(
            text(
                "SELECT COUNT(*) FROM public.refund_requests "
                "WHERE status IN ('pending', 'approved')"
            )
        )
    ).scalar_one()
    low_stock = (
        await session.execute(
            text(
                "SELECT COALESCE(COUNT(*) FILTER "
                "(WHERE active AND stock <= low_stock_threshold), 0) "
                "FROM public.products"
            )
        )
    ).scalar_one()

    # daily revenue series for the area chart (paid, cancelled excluded)
    if window is None:
        series_sql = (
            "SELECT to_char(d.day, 'YYYY-MM-DD') AS date, "
            "COALESCE(SUM(o.total) FILTER (WHERE o.payment_status = 'paid'), 0) AS revenue "
            "FROM generate_series(date_trunc('day', now() - INTERVAL '29 days'), "
            "date_trunc('day', now()), INTERVAL '1 day') AS d(day) "
            "LEFT JOIN public.orders o ON date_trunc('day', o.created_at) = d.day "
            "AND o.status <> 'cancelled' "
            "GROUP BY d.day ORDER BY d.day"
        )
        params: dict = {}
    else:
        # `window` comes from the _KPI_RANGES whitelist (never raw user input);
        # asyncpg refuses to CAST a text *parameter* to interval, so the whitelisted
        # literal is inlined instead
        series_sql = (
            "SELECT to_char(d.day, 'YYYY-MM-DD') AS date, "
            "COALESCE(SUM(o.total) FILTER (WHERE o.payment_status = 'paid'), 0) AS revenue "
            "FROM generate_series(date_trunc('day', now() - INTERVAL '"
            f"{window}'), "
            "date_trunc('day', now()), INTERVAL '1 day') AS d(day) "
            "LEFT JOIN public.orders o ON date_trunc('day', o.created_at) = d.day "
            "AND o.status <> 'cancelled' "
            "GROUP BY d.day ORDER BY d.day"
        )
        params: dict = {}

    series_rows = (await session.execute(text(series_sql), params)).mappings().all()

    status_rows = (
        await session.execute(
            text(
                "SELECT o.status, COUNT(*) AS count FROM public.orders o "
                + where
                + " GROUP BY o.status"
            )
        )
    ).mappings().all()

    return {
        "range": range,
        "grossRevenue": current["gross"],
        "netRevenue": current["net"],
        "paidOrders": current["paidOrders"],
        "aov": current["aov"],
        "pendingRefunds": int(pending_refunds),
        "lowStock": int(low_stock),
        "deltas": {
            "grossRevenue": _delta(current["gross"], previous["gross"]),
            "netRevenue": _delta(current["net"], previous["net"]),
            "paidOrders": _delta(current["paidOrders"], previous["paidOrders"]),
            "aov": _delta(current["aov"], previous["aov"]),
        },
        "series": [
            {"date": r["date"], "revenue": int(r["revenue"])} for r in series_rows
        ],
        "statusBreakdown": [
            {"status": r["status"], "count": int(r["count"])} for r in status_rows
        ],
    }


@router.get("/audit-logs")
async def audit_logs(
    user: StaffAudit,
    session: DbSession,
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    admin_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """Audit trail, newest first (B5.1). Filters: action, entity_type,
    entity_id, admin_id. Keyset-free deep paging via limit/offset."""
    sql = (
        "SELECT a.id, a.admin_id, u.email AS admin_email, "
        "COALESCE(p.full_name, u.email) AS admin_name, "
        "a.action, a.entity_type, a.entity_id, a.old_values, a.new_values, "
        "a.ip_address, a.created_at "
        "FROM public.audit_logs a "
        "LEFT JOIN public.users u ON u.id = a.admin_id "
        "LEFT JOIN public.profiles p ON p.id = a.admin_id"
    )
    conditions: list[str] = []
    params: dict = {"limit": limit}
    if action:
        conditions.append("a.action = :action")
        params["action"] = action
    if entity_type:
        conditions.append("a.entity_type = :entity_type")
        params["entity_type"] = entity_type
    if entity_id:
        conditions.append("a.entity_id = :entity_id")
        params["entity_id"] = entity_id
    if admin_id:
        conditions.append("a.admin_id = CAST(:admin_id AS uuid)")
        params["admin_id"] = admin_id
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    params["offset"] = offset
    sql += " ORDER BY a.created_at DESC LIMIT :limit OFFSET :offset"

    rows = (await session.execute(text(sql), params)).mappings().all()
    return [
        {
            "id": str(r["id"]),
            "admin_id": str(r["admin_id"]) if r["admin_id"] else None,
            "admin_email": r["admin_email"],
            "admin_name": r["admin_name"],
            "action": r["action"],
            "entity_type": r["entity_type"],
            "entity_id": r["entity_id"],
            "old_values": r["old_values"],
            "new_values": r["new_values"],
            "ip_address": r["ip_address"],
            "created_at": _iso(r["created_at"]),
        }
        for r in rows
    ]


_ORDER_SORTS = {
    "new": "o.created_at DESC",
    "old": "o.created_at ASC",
    "total_desc": "o.total DESC, o.created_at DESC",
    "total_asc": "o.total ASC, o.created_at DESC",
}


@router.get("/orders")
async def all_orders(
    user: StaffOrders,
    session: DbSession,
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=0, ge=0, le=100),
    status_filter: Annotated[
        list[str] | None,
        Query(alias="status", description="repeatable and/or comma-separated order statuses"),
    ] = None,
    payment_status: str | None = None,
    q: str | None = Query(
        default=None, max_length=100,
        description="order number, customer name, phone, email or tracking code",
    ),
    sort: Literal["new", "old", "total_desc", "total_asc"] = "new",
) -> list[dict] | dict:
    """All orders with items — same shape as GET /orders but unscoped.
    Envelope when `page` is given."""
    from app.routers.orders import (
        _ALLOWED_PAYMENT_STATUS,
        _ALLOWED_STATUS,
        _ORDER_SELECT,
        _order_row,
    )

    conditions: list[str] = []
    params: dict = {}
    statuses = split_multi(status_filter)
    if statuses:
        if not set(statuses) <= _ALLOWED_STATUS:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "وضعیت نامعتبر است")
        conditions.append("o.status = ANY(:statuses)")
        params["statuses"] = statuses
    if payment_status:
        if payment_status not in _ALLOWED_PAYMENT_STATUS:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "وضعیت پرداخت نامعتبر است")
        conditions.append("o.payment_status = :payment_status")
        params["payment_status"] = payment_status
    if q and q.strip():
        conditions.append(
            "(o.order_number ILIKE :q OR o.tracking_code ILIKE :q "
            " OR o.shipping_address->>'full_name' ILIKE :q "
            " OR o.shipping_address->>'receiver' ILIKE :q "
            " OR o.shipping_address->>'phone' ILIKE :q "
            " OR o.user_id IN (SELECT id FROM public.users WHERE email ILIKE :q))"
        )
        params["q"] = _like(q.strip())
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    base_sql = _ORDER_SELECT + where + " GROUP BY o.id"
    page, page_size = clamp_page_size(page, page_size, default_size=20)
    sql = base_sql + " ORDER BY " + _ORDER_SORTS[sort]
    total = 0
    if page > 0:
        # count over the join without the item aggregation ordering; the
        # GROUP BY keeps one row per order so COUNT(*) is the order count
        total = await count_rows(session, base_sql, params)
        sql += f" LIMIT {page_size} OFFSET {(page - 1) * page_size}"
    rows = (await session.execute(text(sql), params)).mappings().all()
    items = [_order_row(r) for r in rows]
    if page > 0:
        return envelope(items, total, page, page_size)
    return items


@router.get("/inventory")
async def inventory_summary(user: StaffStats, session: DbSession) -> dict:
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
    user: StaffStats,
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
async def all_payments(
    user: StaffOrders,
    session: DbSession,
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=0, ge=0, le=100),
) -> list[dict] | dict:
    base_sql = (
        "SELECT pm.id, pm.order_id, pm.user_id, pm.amount, pm.method, pm.status, "
        "pm.reference, pm.created_at, o.order_number "
        "FROM public.payments pm JOIN public.orders o ON o.id = pm.order_id"
    )
    page, page_size = clamp_page_size(page, page_size, default_size=20)
    sql = base_sql + " ORDER BY pm.created_at DESC"
    total = 0
    if page > 0:
        total = await count_rows(session, base_sql, {})
        sql += f" LIMIT {page_size} OFFSET {(page - 1) * page_size}"
    rows = (await session.execute(text(sql), {})).mappings().all()
    items = [dict(r) for r in rows]
    if page > 0:
        return envelope(items, total, page, page_size)
    return items


_ALLOWED_ROLES = ("super_admin", "order_manager", "support")


class RolesIn(BaseModel):
    """Full replacement set of staff roles for a user (PUT semantics)."""

    roles: list[Literal["super_admin", "order_manager", "support"]]


@router.put("/users/{user_id}/roles")
async def set_user_roles(
    user_id: UUID,
    body: RolesIn,
    user: StaffUsers,
    session: DbSession,
) -> dict:
    """Replace a user's staff roles (B5.4). Admin/super_admin only — granted by
    the `users` capability. Audited with the old and new role sets."""
    target = (
        await session.execute(
            text("SELECT id FROM public.users WHERE id = cast(:uid as uuid)"),
            {"uid": str(user_id)},
        )
    ).first()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کاربر پیدا نشد")

    # B5.4a: one role change at a time, so two admins demoting each other
    # concurrently cannot both pass the lockout check below
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended('roles:users', 0))")
    )

    old_rows = (
        await session.execute(
            text(
                "SELECT role::text FROM public.user_roles "
                "WHERE user_id = cast(:uid as uuid) AND role::text = ANY(:roles)"
            ),
            {"uid": str(user_id), "roles": list(_ALLOWED_ROLES)},
        )
    ).all()
    old_roles = sorted(r[0] for r in old_rows)
    new_roles = sorted(set(body.roles))

    # the roles this endpoint does not manage (legacy `admin`, `customer`) stay
    kept = {
        r[0]
        for r in (
            await session.execute(
                text(
                    "SELECT role::text FROM public.user_roles "
                    "WHERE user_id = cast(:uid as uuid) AND NOT (role::text = ANY(:roles))"
                ),
                {"uid": str(user_id), "roles": list(_ALLOWED_ROLES)},
            )
        ).all()
    }
    other_holders = (
        await session.execute(
            text(
                "SELECT COUNT(DISTINCT user_id) FROM public.user_roles "
                "WHERE role::text = ANY(:users_roles) AND user_id <> cast(:uid as uuid)"
            ),
            {"users_roles": sorted(ROLE_CAPABILITIES["users"]), "uid": str(user_id)},
        )
    ).scalar_one()
    reason = role_lockout_reason(
        is_self=user_id == user.id,
        target_roles_after=kept | set(new_roles),
        other_users_holders=int(other_holders),
    )
    if reason:
        raise HTTPException(status.HTTP_409_CONFLICT, reason)

    await session.execute(
        text(
            "DELETE FROM public.user_roles "
            "WHERE user_id = cast(:uid as uuid) AND role::text = ANY(:roles)"
        ),
        {"uid": str(user_id), "roles": list(_ALLOWED_ROLES)},
    )
    for role in new_roles:
        await session.execute(
            text(
                "INSERT INTO public.user_roles (user_id, role) "
                "VALUES (cast(:uid as uuid), :role) "
                "ON CONFLICT (user_id, role) DO NOTHING"
            ),
            {"uid": str(user_id), "role": role},
        )

    await record_audit(
        session,
        admin_id=user.id,
        action="update_user_roles",
        entity_type="user",
        entity_id=str(user_id),
        old_values={"roles": old_roles},
        new_values={"roles": new_roles},
    )
    await session.commit()
    return {"userId": str(user_id), "roles": new_roles}
