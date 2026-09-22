"""Co-purchase recommendation engine (task B2.4).

Learns "customers who bought X also bought Y" pairs from real order items:
every multi-item order contributes one vote to each unordered product pair it
contains (`co_purchases`, votes = number of orders containing both). The table
is refreshed by `refresh_co_purchases` after checkout and at startup
(`STARTUP_DDL` guarantees the table exists before the first refresh).

The public surface stays the two existing endpoints: `/recommendations`
blends co-purchase votes (weight 3) with the heuristic score, falling back to
the pure heuristic when no co-purchase data exists yet — so behaviour is
never worse than before B2.4.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# One row per unordered product pair that appears together in an order.
_CO_PURCHASE_DDL = """
CREATE TABLE IF NOT EXISTS public.co_purchases (
    product_a TEXT NOT NULL,
    product_b TEXT NOT NULL,
    votes INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (product_a, product_b),
    CHECK (product_a < product_b)
)
"""

# Recomputed from order_items; runs in well under a second at this catalog size.
_REFRESH_SQL = """
INSERT INTO public.co_purchases (product_a, product_b, votes, updated_at)
SELECT LEAST(i1.product_id, i2.product_id),
       GREATEST(i1.product_id, i2.product_id),
       COUNT(DISTINCT i1.order_id),
       now()
FROM public.order_items i1
JOIN public.order_items i2
  ON i1.order_id = i2.order_id AND i1.product_id < i2.product_id
GROUP BY 1, 2
ON CONFLICT (product_a, product_b) DO UPDATE
SET votes = EXCLUDED.votes, updated_at = now()
"""

# Co-purchase votes for one product, as a scalar subquery fragment usable in
# any ranking expression (the caller joins it against `public.products p`).
CO_VOTES_SQL = """
    (SELECT COALESCE(SUM(votes), 0) FROM public.co_purchases cp
     WHERE (cp.product_a = :pid AND cp.product_b = p.id)
        OR (cp.product_b = :pid AND cp.product_a = p.id))
"""


async def refresh_co_purchases(session: AsyncSession) -> int:
    """Rebuild the pair table from order_items; returns the pair count."""
    await session.execute(text(_REFRESH_SQL))
    count = (
        await session.execute(text("SELECT COUNT(*) FROM public.co_purchases"))
    ).scalar_one()
    return int(count)


def co_purchase_ddl() -> str:
    return _CO_PURCHASE_DDL
