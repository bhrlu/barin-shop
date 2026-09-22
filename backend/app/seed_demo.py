"""Seed demo activity for the bootstrap customer (idempotent).

Gives the account + admin pages something to show after the frontend cut-over:
two addresses, three favorites, and two orders (one paid/processing, one
pending/unpaid) with items and their payment rows.

Run from backend/:
    python -m app.seed_demo
Requires DATABASE_URL. Run *after* `app.seed_auth` (needs the customer user) and
`app.seed_products` (order items reference product ids). Skips cleanly when the
demo customer is absent, and only seeds a section that is still empty.
"""

import asyncio
import json

from sqlalchemy import text

from app.db import engine, startup_ddl

CUSTOMER_EMAIL = "customer@sande.local"

SHIPPING_FLAT_FEE = 89_000
FREE_SHIPPING_THRESHOLD = 2_000_000

_ADDRESSES = [
    {
        "title": "خانه",
        "receiver": "مشتری نمونه",
        "phone": "09120000000",
        "province": "تهران",
        "city": "تهران",
        "postal_code": "1998765432",
        "line": "خیابان ولیعصر، کوچه بهار، پلاک ۱۲، واحد ۳",
        "is_default": True,
    },
    {
        "title": "محل کار",
        "receiver": "مشتری نمونه",
        "phone": "09120000000",
        "province": "تهران",
        "city": "تهران",
        "postal_code": "1517964731",
        "line": "خیابان آزادی، برج اداری نگین، طبقه ۵",
        "is_default": False,
    },
]

_FAVORITES = ["tshirt-1", "crop-5", "set-17"]

# order → (status, payment_status, [(product_id, size, color, quantity)])
_ORDERS = [
    (
        "delivered",
        "paid",
        [("tshirt-1", "M", "شنی", 1), ("crop-5", "S", "کرم", 1)],
    ),
    (
        "pending",
        "unpaid",
        [("socks-13", "39-41", "کرم", 2)],
    ),
]


async def _seed_addresses(conn, uid: str) -> None:
    count = (
        await conn.execute(
            text("SELECT COUNT(*) FROM public.addresses WHERE user_id = CAST(:uid AS uuid)"),
            {"uid": uid},
        )
    ).scalar_one()
    if count:
        print("  • addresses already present")
        return
    for address in _ADDRESSES:
        await conn.execute(
            text(
                "INSERT INTO public.addresses "
                "(user_id, title, receiver, phone, province, city, postal_code, line, is_default) "
                "VALUES (CAST(:uid AS uuid), :title, :receiver, :phone, :province, :city, "
                "        :postal_code, :line, :is_default)"
            ),
            {"uid": uid, **address},
        )
    print(f"  ✓ {len(_ADDRESSES)} addresses")


async def _seed_favorites(conn, uid: str) -> None:
    count = (
        await conn.execute(
            text("SELECT COUNT(*) FROM public.favorites WHERE user_id = CAST(:uid AS uuid)"),
            {"uid": uid},
        )
    ).scalar_one()
    if count:
        print("  • favorites already present")
        return
    added = 0
    for product_id in _FAVORITES:
        exists = (
            await conn.execute(
                text("SELECT 1 FROM public.products WHERE id = :pid"), {"pid": product_id}
            )
        ).first()
        if exists is None:
            continue
        await conn.execute(
            text(
                "INSERT INTO public.favorites (user_id, product_id) "
                "VALUES (CAST(:uid AS uuid), :pid) ON CONFLICT (user_id, product_id) DO NOTHING"
            ),
            {"uid": uid, "pid": product_id},
        )
        added += 1
    print(f"  ✓ {added} favorites")


async def _seed_orders(conn, uid: str) -> None:
    count = (
        await conn.execute(
            text("SELECT COUNT(*) FROM public.orders WHERE user_id = CAST(:uid AS uuid)"),
            {"uid": uid},
        )
    ).scalar_one()
    if count:
        print("  • orders already present")
        return

    order_ids: list[str] = []
    for status, payment_status, lines in _ORDERS:
        items: list[dict] = []
        subtotal = 0
        for product_id, size, color, quantity in lines:
            product = (
                await conn.execute(
                    text("SELECT name, price FROM public.products WHERE id = :pid"),
                    {"pid": product_id},
                )
            ).mappings().first()
            if product is None:
                raise RuntimeError(
                    f"product {product_id} missing — run `python -m app.seed_products` first"
                )
            subtotal += int(product["price"]) * quantity
            items.append(
                {
                    "product_id": product_id,
                    "name": product["name"],
                    "price": int(product["price"]),
                    "size": size,
                    "color": color,
                    "quantity": quantity,
                }
            )

        shipping = 0 if subtotal >= FREE_SHIPPING_THRESHOLD else SHIPPING_FLAT_FEE
        address = {k: _ADDRESSES[0][k] for k in ("receiver", "phone", "province", "city", "line")}

        row = (
            await conn.execute(
                text(
                    "INSERT INTO public.orders "
                    "(user_id, status, payment_status, payment_method, subtotal, discount, "
                    " shipping, total, shipping_address) "
                    "VALUES (CAST(:uid AS uuid), :status, :pstatus, 'online', :subtotal, 0, "
                    "        :shipping, :total, CAST(:addr AS jsonb)) "
                    "RETURNING id, order_number"
                ),
                {
                    "uid": uid,
                    "status": status,
                    "pstatus": payment_status,
                    "subtotal": subtotal,
                    "shipping": shipping,
                    "total": subtotal + shipping,
                    "addr": json.dumps(address, ensure_ascii=False),
                },
            )
        ).mappings().first()
        order_id = str(row["id"])
        order_ids.append(order_id)

        for item in items:
            await conn.execute(
                text(
                    "INSERT INTO public.order_items "
                    "(order_id, product_id, name, price, size, color, quantity) "
                    "VALUES (CAST(:oid AS uuid), :product_id, :name, :price, :size, :color, "
                    "        :quantity)"
                ),
                {"oid": order_id, **item},
            )

        if payment_status == "paid":
            await conn.execute(
                text(
                    "INSERT INTO public.payments "
                    "(order_id, user_id, amount, method, status, reference) "
                    "VALUES (CAST(:oid AS uuid), CAST(:uid AS uuid), :amount, 'online', "
                    "        'succeeded', :ref)"
                ),
                {
                    "oid": order_id,
                    "uid": uid,
                    "amount": subtotal + shipping,
                    "ref": f"SND-{row['order_number']}-{order_id[:6].upper()}",
                },
            )

    print(f"  ✓ {len(order_ids)} demo orders")


async def main() -> None:
    await startup_ddl()
    print("seeding demo customer data…")
    async with engine.begin() as conn:
        row = (
            await conn.execute(
                text("SELECT id FROM public.users WHERE lower(email) = :email"),
                {"email": CUSTOMER_EMAIL},
            )
        ).first()
        if row is None:
            print(f"  • no user {CUSTOMER_EMAIL} — run `python -m app.seed_auth` first, skipping")
            return
        uid = str(row[0])
        await _seed_addresses(conn, uid)
        await _seed_favorites(conn, uid)
        await _seed_orders(conn, uid)
    print("done.")


if __name__ == "__main__":
    asyncio.run(main())
