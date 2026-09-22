"""Order lifecycle state machine (spec [BE-05] / task B6.1).

The map is the single source of truth for which status → status moves are
legal. It is enforced in `PATCH /orders/{id}` and `POST /orders/{id}/cancel`
so an order can never be walked backwards, skip fulfilment stages, or be
revived after cancellation. Stock taken at checkout is restored here when a
not-yet-shipped order is cancelled (variants first, product aggregate second —
mirroring checkout's decrement order), inside the caller's transaction.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Shipped orders are physically gone — the store can no longer restock them,
# so the cancel guard keeps refusing them (same behavior as before B6.1).
CANCELLABLE_STATUSES = {"pending", "processing"}


class CancelError(Exception):
    """Order cannot be cancelled from its current status (caller maps to 409)."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

# Legal linear fulfilment transitions (Rule 4: the status strings are frozen).
# `cancelled` and `delivered` are terminal — nothing may leave them. Anything
# not listed here (e.g. shipped → pending, delivered → anything) is rejected.
ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"processing", "cancelled"},
    "processing": {"shipped", "cancelled"},
    "shipped": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}


class IllegalTransition(Exception):
    """Requested status move is not allowed by the state machine."""

    def __init__(self, old: str, new: str) -> None:
        self.old = old
        self.new = new
        super().__init__(f"illegal order transition: {old} -> {new}")


def assert_transition(old: str, new: str) -> None:
    """Raise IllegalTransition unless old → new is a legal move."""
    if new == old:
        return  # idempotent no-op writes stay legal
    if new not in ALLOWED_STATUS_TRANSITIONS.get(old, set()):
        raise IllegalTransition(old, new)


async def restore_stock(session: AsyncSession, order_id: str) -> int:
    """Return the items of a cancelled order to inventory (spec [BE-05]).

    Variant rows are restored first, then the product aggregate — the exact
    mirror of checkout's decrement order, so the two stay consistent under
    concurrency. Rows missing their `variant_id` (legacy items) only bump the
    product aggregate. Returns the number of items processed.
    """
    # `variant_id` may not exist on order_items in older stacks (the column is
    # only added by the variants DDL). Check before selecting it.
    has_variant_col = (
        await session.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.columns "
                "  WHERE table_schema = 'public' AND table_name = 'order_items' "
                "  AND column_name = 'variant_id')"
            )
        )
    ).scalar()
    select_cols = "product_id, variant_id, quantity" if has_variant_col else "product_id, quantity"
    items = (
        await session.execute(
            text(
                f"SELECT {select_cols} "
                "FROM public.order_items WHERE order_id = CAST(:oid AS uuid)"
            ),
            {"oid": order_id},
        )
    ).mappings().all()

    for item in items:
        qty = int(item["quantity"])
        if has_variant_col and item.get("variant_id"):
            await session.execute(
                text(
                    "UPDATE public.product_variants SET stock = stock + :qty, "
                    "updated_at = now() WHERE id = :vid"
                ),
                {"vid": str(item["variant_id"]), "qty": qty},
            )
        # NB: products.id is TEXT in this schema (seeded slugs) — raw equality,
        # exactly like checkout's decrement.
        await session.execute(
            text("UPDATE public.products SET stock = stock + :qty WHERE id = :pid"),
            {"pid": str(item["product_id"]), "qty": qty},
        )
    return len(items)


async def cancel_order_tx(session: AsyncSession, order_id: str, old_status: str) -> None:
    """Flip the order to `cancelled` and restore its stock atomically.

    Runs on the caller's session/transaction — checkout decrements stock in the
    same transaction that creates the order, so the restore belongs in one too
    (spec [BE-05]: atomic transaction safeguards inventory consistency).
    Raises CancelError for terminal/uncancellable states (caller maps to HTTP).
    """
    if old_status not in CANCELLABLE_STATUSES:
        raise CancelError(f"سفارش در وضعیت {old_status} قابل لغو نیست")
    await session.execute(
        text("UPDATE public.orders SET status = 'cancelled' WHERE id = CAST(:oid AS uuid)"),
        {"oid": order_id},
    )
    await restore_stock(session, order_id)
