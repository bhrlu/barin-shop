"""Stock pre-check endpoint — validates cart lines before checkout.

Per-variant (size × color) stock wins when a variant row exists; otherwise the
product's aggregate stock applies. `availability` is a hard gate before any of
that: a `coming_soon` product is never orderable (`preorder` is, since B4.13 —
its lines still report nominal stock here, but checkout decrements nothing for
them). Shares `app.services.variants` and `app.services.availability` with
checkout, so the pre-check and the order always agree.
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.auth import DbSession
from app.schemas import StockCheckLine, StockCheckOut, StockIssue
from app.services.availability import availability_issue, is_preorder
from app.services.variants import load_variants, variant_price, variant_stock

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
                "SELECT id, price, sizes, stock, active, availability "
                "FROM public.products WHERE id = ANY(:ids)"
            ),
            {"ids": product_ids},
        )
    ).mappings().all()
    products = {r["id"]: r for r in rows}

    variants = await load_variants(
        session, [(line.product_id, line.size, line.color) for line in body]
    )

    issues: list[StockIssue] = []
    subtotal = 0
    unit_prices: list[int | None] = []
    for line in body:
        p = products.get(line.product_id)
        variant = variants.get((line.product_id, line.size, line.color))
        unit_prices.append(variant_price(p, variant) if p is not None else None)
        if p is None:
            issues.append(StockIssue(product_id=line.product_id, reason="not_found", available=0))
            continue
        if not p["active"]:
            issues.append(StockIssue(product_id=line.product_id, reason="inactive", available=0))
            continue
        not_available = availability_issue(p)
        if not_available is not None:
            issues.append(
                StockIssue(product_id=line.product_id, reason=not_available, available=0)
            )
            continue
        if p["sizes"] and line.size not in (p["sizes"] or []):
            issues.append(
                StockIssue(
                    product_id=line.product_id,
                    reason="size_invalid",
                    available=int(p["stock"]),
                )
            )
            continue

        available, variant_ok = variant_stock(p, variant)
        if not variant_ok:
            issues.append(
                StockIssue(product_id=line.product_id, reason="inactive", available=0)
            )
            continue
        # B4.13/D4: a preorder line skips the sufficiency check exactly like
        # checkout does (the stock counter is an operational allocation, never
        # the gate) — so the cart never blocks what checkout would accept.
        if not is_preorder(p) and available < line.quantity:
            issues.append(
                StockIssue(
                    product_id=line.product_id,
                    reason="insufficient_stock",
                    available=available,
                )
            )
            continue
        subtotal += variant_price(p, variant) * line.quantity

    return StockCheckOut(ok=not issues, subtotal=subtotal, issues=issues, unit_prices=unit_prices)
