"""The inventory ledger (AB-BE-01, spec [BE-01] `inventory_logs`).

The one place a stock movement is recorded (R7): every code path that changes a
stock counter calls `log_stock_change` in the same transaction, so a movement and its
ledger row commit or roll back together. There is no second inventory accounting.

Reasons and who writes them:
* `purchase` — checkout, −quantity per order line (`services/checkout.py`);
* `return` — a cancelled order's items back in stock, +quantity per line
  (`services/order_lifecycle.restore_stock`), so an order's rows net to zero;
* `restock` — the opening stock of a new product or variant;
* `manual_adjustment` — a staff edit of a product's or a variant's stock (the delta).

`variant_id` names the size × colour counter that moved; NULL means the product's
aggregate stock. Checkout and cancellation move a variant and the aggregate together,
so their rows carry the variant when the line had one. The table is append-only and
has no foreign keys: a row keeps the ids it was written with after those rows go.
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

REASONS = frozenset({"purchase", "restock", "return", "manual_adjustment"})


async def log_stock_change(
    session: AsyncSession,
    *,
    product_id: str,
    change: int,
    reason: str,
    actor_id: UUID | str | None = None,
    variant_id: UUID | str | None = None,
    order_id: UUID | str | None = None,
) -> None:
    """Record one stock movement. A zero change is not a movement and writes nothing."""
    if reason not in REASONS:
        raise ValueError(f"unknown inventory reason: {reason}")
    if change == 0:
        return
    await session.execute(
        text(
            "INSERT INTO public.inventory_logs "
            "(product_id, variant_id, order_id, change_amount, reason, created_by) "
            "VALUES (:pid, CAST(:vid AS uuid), CAST(:oid AS uuid), :change, :reason, "
            "        CAST(:uid AS uuid))"
        ),
        {
            "pid": str(product_id),
            "vid": str(variant_id) if variant_id else None,
            "oid": str(order_id) if order_id else None,
            "change": int(change),
            "reason": reason,
            "uid": str(actor_id) if actor_id else None,
        },
    )
