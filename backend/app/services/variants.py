"""Per-variant (size × color) stock resolution.

A product may define explicit `product_variants` rows for some size×color
combinations. When a variant exists it is the authoritative stock for that
combination; when it does not, the product's aggregate `stock` is used (legacy
behaviour). Both the stock pre-check and checkout share this helper so the two
never disagree.
"""

from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

Combo = tuple[str, str, str]


async def load_variants(
    session: AsyncSession, combos: Iterable[Combo], *, for_update: bool = False
) -> dict[Combo, dict]:
    """Return existing variants keyed by (product_id, size, color)."""
    product_ids = sorted({p for p, _s, _c in combos})
    if not product_ids:
        return {}
    sql = (
        "SELECT id, product_id, size, color, stock, active "
        "FROM public.product_variants WHERE product_id = ANY(:ids)"
    )
    if for_update:
        sql += " FOR UPDATE"
    rows = (
        await session.execute(text(sql), {"ids": product_ids})
    ).mappings().all()
    return {(r["product_id"], r["size"], r["color"]): dict(r) for r in rows}


def variant_stock(product_row, variant: dict | None) -> tuple[int, bool]:
    """Effective (stock, available_allowed) for a line.

    A variant can be individually deactivated; that makes the combination
    unavailable even if the product as a whole is in stock.
    """
    if variant is None:
        return int(product_row["stock"]), True
    return int(variant["stock"]), bool(variant["active"])
