"""Transactional checkout with concurrency-safe stock decrement.

All operations run inside ONE database transaction:
  1. Lock product rows FOR UPDATE (prevents oversell under concurrency)
  2. Validate activity, availability, size membership and stock; server-side prices
  3. Create order (pending/unpaid) + order_items
  4. Validate + record coupon redemption
  5. Decrement stock with a guarded UPDATE ... WHERE stock >= qty

If any step fails the whole transaction rolls back — no half-orders, no negative stock.
"""

import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.availability import availability_issue
from app.services.coupons import (
    CouponError,
    count_user_redemptions,
    get_coupon_for_update,
    record_redemption,
    validate_coupon,
)
from app.services.inventory_log import log_stock_change
from app.services.notifications import notify_order_event
from app.services.pricing import quote
from app.services.recommendations import refresh_co_purchases
from app.services.variants import load_variants, variant_price, variant_stock

log = logging.getLogger(__name__)


class CheckoutError(Exception):
    def __init__(self, code: str, message_fa: str, issues: list[dict] | None = None):
        self.code = code
        self.message_fa = message_fa
        self.issues = issues or []
        super().__init__(message_fa)


def _line_image(images: list | None) -> str | None:
    return (images or [None])[0]


async def create_order(
    session: AsyncSession,
    user_id: UUID,
    lines: list[dict],
    address: dict,
    coupon_code: str | None,
) -> dict:
    """lines: [{product_id, size, color, quantity}] → order dict or raises CheckoutError."""
    if not lines:
        raise CheckoutError("empty_cart", "سبد خرید خالی است")

    # 1) Lock and load all products in one query (sorted ids → deterministic locks)
    product_ids = sorted({line["product_id"] for line in lines})
    rows = (
        await session.execute(
            text(
                "SELECT id, name, price, sizes, images, stock, active, availability "
                "FROM public.products WHERE id = ANY(:ids) ORDER BY id FOR UPDATE"
            ),
            {"ids": product_ids},
        )
    ).mappings().all()
    products = {row["id"]: row for row in rows}

    # 1b) Lock any per-variant rows for these size×color combinations
    variants = await load_variants(
        session,
        [(line["product_id"], line["size"], line["color"]) for line in lines],
        for_update=True,
    )

    # 2) Validate activity / availability / size / stock; fill authoritative name/price/image
    issues: list[dict] = []
    for line in lines:
        p = products.get(line["product_id"])
        if p is None:
            issues.append({"product_id": line["product_id"], "reason": "not_found", "available": 0})
            continue
        if not p["active"]:
            issues.append({"product_id": line["product_id"], "reason": "inactive", "available": 0})
            continue
        not_available = availability_issue(p)
        if not_available is not None:
            issues.append(
                {"product_id": line["product_id"], "reason": not_available, "available": 0}
            )
            continue
        if p["sizes"] and line["size"] not in (p["sizes"] or []):
            issues.append(
                {
                    "product_id": line["product_id"],
                    "reason": "size_invalid",
                    "available": int(p["stock"]),
                }
            )
            continue

        variant = variants.get((line["product_id"], line["size"], line["color"]))
        available, variant_ok = variant_stock(p, variant)
        if not variant_ok:
            issues.append(
                {"product_id": line["product_id"], "reason": "inactive", "available": 0}
            )
            continue
        if available < line["quantity"]:
            issues.append(
                {
                    "product_id": line["product_id"],
                    "reason": "insufficient_stock",
                    "available": available,
                }
            )
            continue
        line["price"] = variant_price(p, variant)
        line["name"] = p["name"]
        line["image"] = _line_image(p["images"])
        line["variant_id"] = variant["id"] if variant else None

    if issues:
        raise CheckoutError("stock_conflict", "برخی اقلام موجودی کافی ندارند", issues)

    # 3) Server-side totals
    subtotal = sum(line["price"] * line["quantity"] for line in lines)

    # 4) Coupon (row-locked inside the same transaction)
    coupon = None
    discount = 0
    if coupon_code:
        coupon = await get_coupon_for_update(session, coupon_code)
        if coupon is None:
            raise CheckoutError("coupon_invalid", "کد تخفیف معتبر نیست")
        prior = await count_user_redemptions(session, coupon.id, user_id)
        try:
            discount = validate_coupon(coupon, subtotal, user_id, prior)
        except CouponError as exc:
            raise CheckoutError(f"coupon_{exc.code}", exc.message_fa) from exc

    q = quote(subtotal, discount)

    # 5) Insert order + items -----------------------------------------------------
    shipping_address = {
        "full_name": address["full_name"],
        "phone": address["phone"],
        "province": address.get("province"),
        "city": address["city"],
        "line": address["line"],
        "postal_code": address.get("postal_code"),
    }
    if address.get("note"):
        shipping_address["note"] = address["note"]

    result = await session.execute(
        text(
            "INSERT INTO public.orders "
            "(user_id, status, payment_status, payment_method, subtotal, discount, shipping, "
            " total, shipping_address, note) "
            "VALUES (:uid, 'pending', 'unpaid', 'online', :subtotal, :discount, :shipping, "
            "        :total, CAST(:addr AS jsonb), :note) "
            "RETURNING id, order_number"
        ),
        {
            "uid": str(user_id),
            "subtotal": q.subtotal,
            "discount": q.discount,
            "shipping": q.shipping,
            "total": q.total,
            "addr": _json_dumps(shipping_address),
            "note": address.get("note"),
        },
    )
    order_row = result.mappings().first()
    order_id = order_row["id"]
    order_number = order_row["order_number"]

    for line in lines:
        await session.execute(
            text(
                "INSERT INTO public.order_items "
                "(order_id, product_id, name, price, size, color, image, quantity, variant_id) "
                "VALUES (:oid, :pid, :name, :price, :size, :color, :image, :qty, "
                "        CAST(:vid AS uuid))"
            ),
            {
                "oid": str(order_id),
                "pid": line["product_id"],
                "name": line["name"],
                "price": line["price"],
                "size": line["size"],
                "color": line["color"],
                "image": line["image"],
                "qty": line["quantity"],
                # B6.8: remembered so cancellation gives the stock back to the
                # exact variant it was taken from (NULL when the product has no
                # matrix row for this size×color).
                "vid": str(line["variant_id"]) if line.get("variant_id") else None,
            },
        )

    # 6) Coupon redemption record + used_count increment
    if coupon is not None:
        await record_redemption(session, coupon, order_id, user_id, q.discount)

    # 7) Stock decrement — guarded so it can never go negative. Variant rows
    #    (when present) are decremented too, and the product aggregate stays in sync.
    for line in lines:
        updated = await session.execute(
            text(
                "UPDATE public.products SET stock = stock - :qty "
                "WHERE id = :pid AND stock >= :qty"
            ),
            {"pid": line["product_id"], "qty": line["quantity"]},
        )
        if updated.rowcount != 1:
            # Extremely unlikely after FOR UPDATE, but keep the invariant absolute
            raise CheckoutError(
                "stock_conflict",
                "برخی اقلام موجودی کافی ندارند",
                [
                    {
                        "product_id": line["product_id"],
                        "reason": "insufficient_stock",
                        "available": None,
                    }
                ],
            )
        if line.get("variant_id"):
            variant_updated = await session.execute(
                text(
                    "UPDATE public.product_variants SET stock = stock - :qty, "
                    "updated_at = now() WHERE id = :vid AND stock >= :qty"
                ),
                {"vid": str(line["variant_id"]), "qty": line["quantity"]},
            )
            if variant_updated.rowcount != 1:
                raise CheckoutError(
                    "stock_conflict",
                    "برخی اقلام موجودی کافی ندارند",
                    [
                        {
                            "product_id": line["product_id"],
                            "reason": "insufficient_stock",
                            "available": None,
                        }
                    ],
                )
        # AB-BE-01: the ledger row for this line, in the same transaction
        await log_stock_change(
            session,
            product_id=line["product_id"],
            variant_id=line.get("variant_id"),
            order_id=order_id,
            change=-line["quantity"],
            reason="purchase",
            actor_id=user_id,
        )

    # 8) Co-purchase pairs refreshed in the same transaction (B2.4) so the
    #    recommendation engine learns from this order immediately.
    if len(lines) > 1:
        await refresh_co_purchases(session)

    # 9) "order created" notification (B2.1) — same transaction, so a checkout
    #    that fails above leaves no notification behind
    await notify_order_event(session, order_id, "created")

    return {
        "order_id": str(order_id),
        "order_number": order_number,
        "subtotal": q.subtotal,
        "discount": q.discount,
        "shipping": q.shipping,
        "total": q.total,
        "coupon_applied": coupon.code if coupon else None,
    }


def _json_dumps(value: dict) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)
