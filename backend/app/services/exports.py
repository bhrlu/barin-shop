"""Reports & exports (task B2.2 / spec [BE-08]).

Streams order and product data as CSV or XLSX. All money figures are the
store's integer tomans; CSV is RFC-4180-safe via the stdlib module and the
Excel sheets are written by openpyxl in-memory. File names are ASCII (RFC 6266
§5.5: `filename=` must not carry non-ASCII) with the Persian label kept in
`filename*`.
"""

import csv
import io
from datetime import UTC, datetime
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Order rows join the customer profile; items are aggregated into one cell.
_ORDERS_SQL = """
SELECT o.order_number, o.created_at, o.status, o.payment_status, o.payment_method,
       COALESCE(u.email, '') AS email,
       COALESCE(p.full_name, '') AS full_name, COALESCE(p.phone, '') AS phone,
       o.shipping_address,
       o.subtotal, o.discount, o.shipping, o.total,
       COALESCE(o.tracking_code, '') AS tracking_code,
       COALESCE(
           (SELECT string_agg(
                       i.name || CASE WHEN i.size IS NOT NULL THEN ' / ' || i.size ELSE '' END
                       || CASE WHEN i.color IS NOT NULL THEN ' / ' || i.color ELSE '' END
                       || ' × ' || i.quantity, ' | ')
            FROM public.order_items i WHERE i.order_id = o.id),
           '') AS items
FROM public.orders o
LEFT JOIN public.users u ON u.id = o.user_id
LEFT JOIN public.profiles p ON p.id = o.user_id
WHERE o.created_at >= :from_ts AND o.created_at < :to_ts
  AND (CAST(:status AS text) IS NULL OR o.status = :status)
ORDER BY o.created_at
"""

_PRODUCTS_SQL = """
SELECT id, name, category, price, COALESCE(old_price, 0) AS old_price, stock, active,
       COALESCE(low_stock_threshold, 5) AS low_stock_threshold, updated_at
FROM public.products
ORDER BY category, name
"""
ORDER_HEADERS = [
    "order_number", "created_at", "status", "payment_status", "payment_method",
    "customer_email", "customer_name", "customer_phone", "city", "address",
    "postal_code", "items", "subtotal", "discount", "shipping", "total",
    "tracking_code",
]

PRODUCT_HEADERS = [
    "product_id", "name", "category", "price", "old_price", "stock",
    "low_stock_threshold", "active", "updated_at",
]


def _address(addr, key: str) -> str:
    return str(addr.get(key) or "") if isinstance(addr, dict) else ""


def _order_rows(rows) -> list[list]:
    out = []
    for r in rows:
        addr = r["shipping_address"]
        out.append([
            r["order_number"],
            r["created_at"].isoformat(timespec="seconds") if r["created_at"] else "",
            r["status"], r["payment_status"], r["payment_method"],
            r["email"], r["full_name"], r["phone"],
            _address(addr, "city"), _address(addr, "line"), _address(addr, "postal_code"),
            r["items"],
            r["subtotal"], r["discount"], r["shipping"], r["total"],
            r["tracking_code"],
        ])
    return out


def _product_rows(rows) -> list[list]:
    return [
        [
            r["id"], r["name"], r["category"], r["price"], r["old_price"], r["stock"],
            r["low_stock_threshold"], r["active"],
            r["updated_at"].isoformat(timespec="seconds") if r["updated_at"] else "",
        ]
        for r in rows
    ]


def _csv(headers: list[str], rows: list[list]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)  # stdlib: RFC-4180 quoting/escaping
    writer.writerow(headers)
    writer.writerows(rows)
    return buf.getvalue()


def _xlsx(sheets: list[tuple[str, list[str], list[list]]]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    for title, headers, rows in sheets:
        ws = wb.create_sheet(title=title[:31])  # Excel sheet-name cap
        ws.append(headers)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _content_disposition(fmt: str, ascii_name: str, fa_name: str) -> str:
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    fname = f"{ascii_name}-{ts}.{fmt}"
    return (
        f"attachment; filename=\"{fname}\"; "
        f"filename*=UTF-8''{quote(f'{fa_name}-{ts}.{fmt}')}"
    )


async def fetch_orders(
    session: AsyncSession,
    *,
    from_ts: datetime,
    to_ts: datetime,
    status: str | None = None,
):
    return (
        await session.execute(
            text(_ORDERS_SQL),
            {"from_ts": from_ts, "to_ts": to_ts, "status": status},
        )
    ).mappings().all()


async def fetch_products(session: AsyncSession):
    return (await session.execute(text(_PRODUCTS_SQL))).mappings().all()


def orders_csv(rows) -> tuple[str, str]:
    body = _csv(ORDER_HEADERS, _order_rows(rows))
    return body, _content_disposition("csv", "sande-orders", "سفارش‌های-ساندِه")


def products_csv(rows) -> tuple[str, str]:
    body = _csv(PRODUCT_HEADERS, _product_rows(rows))
    return body, _content_disposition("csv", "sande-products", "محصولات-ساندِه")


def orders_xlsx(rows) -> tuple[bytes, str]:
    body = _xlsx([("Orders", ORDER_HEADERS, _order_rows(rows))])
    return body, _content_disposition("xlsx", "sande-orders", "سفارش‌های-ساندِه")


def products_xlsx(rows) -> tuple[bytes, str]:
    body = _xlsx([("Products", PRODUCT_HEADERS, _product_rows(rows))])
    return body, _content_disposition("xlsx", "sande-products", "محصولات-ساندِه")


def parse_range(from_str: str | None, to_str: str | None) -> tuple[datetime, datetime]:
    """Clamp the export window; defaults to the last 30 days."""
    to_ts = (
        datetime.fromisoformat(to_str).replace(tzinfo=UTC)
        if to_str
        else datetime.now(UTC)
    )
    if from_str:
        from_ts = datetime.fromisoformat(from_str).replace(tzinfo=UTC)
    else:
        from_ts = datetime.fromordinal(to_ts.toordinal() - 30).replace(
            tzinfo=UTC, hour=0, minute=0, second=0, microsecond=0
        )
    if from_ts >= to_ts:
        raise ValueError("`from` must be before `to`")
    return from_ts, to_ts


def _uuid(value: str | None) -> UUID | None:
    try:
        return UUID(value) if value else None
    except ValueError:
        return None


async def sales_report(
    session: AsyncSession, *, from_ts: datetime, to_ts: datetime
) -> dict:
    """Daily/monthly sales summary + best-sellers (B2.2)."""
    daily = (
        await session.execute(
            text(
                "SELECT to_char(date_trunc('day', created_at), 'YYYY-MM-DD') AS day, "
                "       COUNT(*) AS orders, "
                "       COALESCE(SUM(total) FILTER (WHERE status <> 'cancelled'), 0) AS revenue "
                "FROM public.orders WHERE created_at >= :f AND created_at < :t "
                "GROUP BY 1 ORDER BY 1"
            ),
            {"f": from_ts, "t": to_ts},
        )
    ).mappings().all()
    monthly = (
        await session.execute(
            text(
                "SELECT to_char(date_trunc('month', created_at), 'YYYY-MM') AS month, "
                "       COUNT(*) AS orders, "
                "       COALESCE(SUM(total) FILTER (WHERE status <> 'cancelled'), 0) AS revenue "
                "FROM public.orders WHERE created_at >= :f AND created_at < :t "
                "GROUP BY 1 ORDER BY 1"
            ),
            {"f": from_ts, "t": to_ts},
        )
    ).mappings().all()
    best = (
        await session.execute(
            text(
                "SELECT i.product_id, i.name, SUM(i.quantity) AS units, "
                "       SUM(i.quantity * i.price) AS revenue "
                "FROM public.order_items i JOIN public.orders o ON o.id = i.order_id "
                "WHERE o.created_at >= :f AND o.created_at < :t "
                "  AND o.status <> 'cancelled' "
                "GROUP BY i.product_id, i.name ORDER BY units DESC LIMIT 10"
            ),
            {"f": from_ts, "t": to_ts},
        )
    ).mappings().all()
    return {
        "from": from_ts.isoformat(),
        "to": to_ts.isoformat(),
        "daily": [dict(r) for r in daily],
        "monthly": [dict(r) for r in monthly],
        "bestSellers": [
            {
                "productId": r["product_id"],
                "name": r["name"],
                "units": int(r["units"]),
                "revenue": int(r["revenue"]),
            }
            for r in best
        ],
    }
