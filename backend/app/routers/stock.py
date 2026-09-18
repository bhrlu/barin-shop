"""Stock pre-check endpoint — validates cart lines before checkout."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.auth import DbSession
from app.schemas import StockCheckLine, StockCheckOut, StockIssue

router = APIRouter(prefix="/stock", tags=["stock"])


@router.post("/check", response_model=StockCheckOut)
async def check(body: list[StockCheckLine], session: DbSession) -> StockCheckOut:
    """Validate cart lines against live stock; returns subtotal from server prices."""
    if not body:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "سبد خرید خالی است")

    product_ids = sorted({line.product_id for line in body})
    rows = (
        await session.execute(
            text(
                "SELECT id, price, sizes, stock, active FROM public.products "
                "WHERE id = ANY(:ids)"
            ),
            {"ids": product_ids},
        )
    ).mappings().all()
    products = {r["id"]: r for r in rows}

    issues: list[StockIssue] = []
    subtotal = 0
    for line in body:
        p = products.get(line.product_id)
        if p is None:
            issues.append(StockIssue(product_id=line.product_id, reason="not_found", available=0))
            continue
        if not p["active"]:
            issues.append(StockIssue(product_id=line.product_id, reason="inactive", available=0))
            continue
        if p["sizes"] and line.size not in (p["sizes"] or []):
            issues.append(
                StockIssue(
                    product_id=line.product_id,
                    reason="insufficient_stock",
                    available=int(p["stock"]),
                )
            )
            continue
        if p["stock"] < line.quantity:
            issues.append(
                StockIssue(
                    product_id=line.product_id,
                    reason="insufficient_stock",
                    available=int(p["stock"]),
                )
            )
            continue
        subtotal += int(p["price"]) * line.quantity

    return StockCheckOut(ok=not issues, subtotal=subtotal, issues=issues)
