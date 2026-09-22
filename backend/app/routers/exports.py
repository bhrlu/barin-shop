"""Admin export & report endpoints (task B2.2 / spec [BE-08])."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.auth import DbSession, StaffOrders
from app.services import exports

router = APIRouter(prefix="/admin/export", tags=["admin"])

_XLSX_MIME = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def _range_or_400(from_str: str | None, to_str: str | None) -> tuple[datetime, datetime]:
    try:
        return exports.parse_range(from_str, to_str)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


async def _orders_rows(session, from_ts, to_ts, status_filter):
    return await exports.fetch_orders(
        session, from_ts=from_ts, to_ts=to_ts, status=status_filter
    )


@router.get("/orders.csv")
async def export_orders_csv(
    user: StaffOrders,
    session: DbSession,
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    status_filter: str | None = Query(default=None, alias="status"),
) -> Response:
    """Order ledger as CSV: customer shipping details, item breakdown, money splits."""
    from_ts, to_ts = _range_or_400(from_date, to_date)
    rows = await _orders_rows(session, from_ts, to_ts, status_filter)
    body, disposition = exports.orders_csv(rows)
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": disposition},
    )


@router.get("/orders.xlsx")
async def export_orders_xlsx(
    user: StaffOrders,
    session: DbSession,
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    status_filter: str | None = Query(default=None, alias="status"),
) -> Response:
    """Order ledger as Excel (openpyxl, in-memory)."""
    from_ts, to_ts = _range_or_400(from_date, to_date)
    rows = await _orders_rows(session, from_ts, to_ts, status_filter)
    body, disposition = exports.orders_xlsx(rows)
    return Response(
        content=body,
        media_type=_XLSX_MIME,
        headers={"Content-Disposition": disposition},
    )


@router.get("/products.csv")
async def export_products_csv(
    user: StaffOrders, session: DbSession
) -> Response:
    """Full catalog export for stock/price audits."""
    rows = await exports.fetch_products(session)
    body, disposition = exports.products_csv(rows)
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": disposition},
    )


@router.get("/products.xlsx")
async def export_products_xlsx(
    user: StaffOrders, session: DbSession
) -> Response:
    rows = await exports.fetch_products(session)
    body, disposition = exports.products_xlsx(rows)
    return Response(
        content=body,
        media_type=_XLSX_MIME,
        headers={"Content-Disposition": disposition},
    )


@router.get("/report")
async def sales_report(
    user: StaffOrders,
    session: DbSession,
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
):
    """Daily/monthly sales + best-sellers JSON (feeds charts/exports UI)."""
    from_ts, to_ts = _range_or_400(from_date, to_date)
    return await exports.sales_report(session, from_ts=from_ts, to_ts=to_ts)
