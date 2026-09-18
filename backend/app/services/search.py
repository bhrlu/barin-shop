"""Product full-text search over the existing products table.

Uses Postgres trigram-ish ILIKE matching (no extension needed) across name,
description, material and category, ranked: name match > category match >
description match. Good enough for a small catalog; can be swapped for
pg_trgm/pgroonga later without changing the API.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def search_products(
    session: AsyncSession,
    query: str,
    *,
    category: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    q = query.strip()
    if not q:
        return {"query": q, "total": 0, "hits": []}

    pattern = f"%{q}%"
    rows = (
        await session.execute(
            text(
                """
                SELECT id, name, category, price, old_price, images, stock, is_new,
                       (name ILIKE :pat) AS name_hit,
                       (category ILIKE :pat) AS cat_hit,
                       COUNT(*) OVER() AS total
                FROM public.products
                WHERE active
                  AND (name ILIKE :pat OR description ILIKE :pat
                       OR material ILIKE :pat OR category ILIKE :pat)
                  AND (:category IS NULL OR category = :category)
                ORDER BY name_hit DESC, cat_hit DESC, is_new DESC, created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {
                "pat": pattern,
                "category": category,
                "limit": limit,
                "offset": offset,
            },
        )
    ).mappings().all()

    total = int(rows[0]["total"]) if rows else 0
    hits = [
        {
            "id": r["id"],
            "name": r["name"],
            "category": r["category"],
            "price": int(r["price"]),
            "old_price": int(r["old_price"]) if r["old_price"] is not None else None,
            "image": (r["images"] or [None])[0],
            "stock": int(r["stock"]),
            "is_new": bool(r["is_new"]),
        }
        for r in rows
    ]
    return {"query": q, "total": total, "hits": hits}
