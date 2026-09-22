"""Seed a realistic demo dataset on top of the starter catalog (idempotent).

`seed_demo` gives the one bootstrap customer just enough to look at. This module
fills the store with enough *shaped* activity that the admin screens are worth
opening: a customer base, two months of backdated orders across every status,
refund claims in each stage of the [BE-03] lifecycle, reviews, an inbox, extra
coupons and a size × colour variant matrix.

Run from backend/:
    python -m app.seed_mock

Requires DATABASE_URL. Run *after* `app.seed_auth` and `app.seed_products`
(needs the staff accounts and the catalog). Re-runnable: it does nothing when
the mock customers already exist, so it never double-counts revenue.

Everything is deterministic (fixed RNG seed), so the dashboard looks the same on
every fresh database — screenshots and demos stay reproducible.
"""

import asyncio
import json
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.db import engine, startup_ddl
from app.security import hash_password

SHIPPING_FLAT_FEE = 89_000
FREE_SHIPPING_THRESHOLD = 2_000_000

# One marker account: if it exists the whole module is a no-op.
MARKER_EMAIL = "niloofar.ahmadi@example.com"

RNG = random.Random(20260922)

# --- people -------------------------------------------------------------------

CUSTOMERS = [
    ("niloofar.ahmadi@example.com", "نیلوفر احمدی", "09121110011", "تهران", "تهران"),
    ("sara.moradi@example.com", "سارا مرادی", "09122220022", "تهران", "کرج"),
    ("mahsa.rezaei@example.com", "مهسا رضایی", "09133330033", "اصفهان", "اصفهان"),
    ("parisa.karimi@example.com", "پریسا کریمی", "09144440044", "خراسان رضوی", "مشهد"),
    ("elham.jafari@example.com", "الهام جعفری", "09155550055", "فارس", "شیراز"),
    ("zahra.nouri@example.com", "زهرا نوری", "09166660066", "آذربایجان شرقی", "تبریز"),
    ("shirin.abbasi@example.com", "شیرین عباسی", "09177770077", "گیلان", "رشت"),
    ("hanieh.salehi@example.com", "هانیه صالحی", "09188880088", "البرز", "کرج"),
]
CUSTOMER_PASSWORD = "customer1234"

STREETS = [
    "خیابان ولیعصر، کوچه یاس، پلاک {n}",
    "بلوار کشاورز، خیابان نسترن، پلاک {n}، واحد ۲",
    "خیابان شریعتی، نبش کوچه بهار، پلاک {n}",
    "میدان آزادی، خیابان لاله، پلاک {n}، طبقه ۳",
    "خیابان امام خمینی، کوچه شقایق، پلاک {n}",
]

# --- orders -------------------------------------------------------------------

# (status, payment_status) mixes chosen so every admin filter and the donut
# chart have something to show, weighted the way a real store skews.
ORDER_SHAPES = [
    ("delivered", "paid", 9),
    ("shipped", "paid", 5),
    ("processing", "paid", 5),
    ("pending", "unpaid", 4),
    ("cancelled", "unpaid", 3),
    # enough cancelled+paid orders to put a claim in every [BE-03] refund state
    ("cancelled", "paid", 5),
]

REVIEW_TEXTS = [
    (5, "دقیقاً همان چیزی که می‌خواستم",
     "جنس پارچه عالی است و سایزبندی دقیق. حتماً دوباره می‌خرم."),
    (5, "کیفیت بالاتر از انتظار",
     "رنگش کاملاً مثل عکس است و بعد از شست‌وشو تغییری نکرد."),
    (4, "خوب ولی کمی بزرگ",
     "کیفیت دوخت خوب است، فقط یک سایز بزرگ‌تر از حد معمول می‌آید."),
    (4, "راضی‌ام", "ارسال سریع بود و بسته‌بندی مرتب. پارچه نرم و خنک است."),
    (3, "متوسط", "بد نیست ولی برای این قیمت انتظار پارچه ضخیم‌تری داشتم."),
    (5, "برای استفاده روزمره فوق‌العاده",
     "سبک و راحت است؛ برای گرمای تابستان انتخاب خوبی است."),
    (2, "با عکس فرق داشت", "رنگ واقعی کمی تیره‌تر از تصویر سایت است."),
    (4, "خرید دوم من", "بار دوم است که می‌خرم؛ کیفیت ثابت مانده و همین مهم است."),
]

SELLER_REPLIES = {
    2: "از بازخورد شما ممنونیم. عکس‌های این محصول را با نور طبیعی به‌روزرسانی کردیم.",
    3: "ممنون از نظرتان؛ مشخصات پارچه را در توضیحات محصول شفاف‌تر نوشتیم.",
}

REFUND_REASONS = [
    "سایز برایم بزرگ بود و امکان تعویض نداشت.",
    "محصول با رنگی که سفارش داده بودم متفاوت بود.",
    "دیگر به این سفارش نیاز ندارم؛ لطفاً مبلغ را برگردانید.",
    "بسته با تأخیر زیاد رسید و سفارش را لغو کردم.",
]

CONTACT_MESSAGES = [
    (
        "مریم حسینی", "maryam.h@example.com",
        "سلام، تی‌شرت اورسایز مینا را در سایز XL موجود می‌کنید؟", "new",
    ),
    (
        "نگار شریفی", "09120009988",
        "سفارشم را دیروز ثبت کردم، چند روز طول می‌کشد تا به شیراز برسد؟", "new",
    ),
    (
        "رها کاظمی", "raha.k@example.com",
        "امکان تعویض سایز بعد از تحویل تا چند روز وجود دارد؟", "answered",
    ),
    (
        "سمانه یوسفی", "samaneh@example.com",
        "آیا برای خرید عمده تخفیف در نظر می‌گیرید؟", "answered",
    ),
    (
        "آیدا فرهادی", "09150001122",
        "کد تخفیف WELCOME500 برای من اعمال نشد، لطفاً بررسی کنید.", "new",
    ),
]

# product_id → [(size, colour, stock)] — the [BE-01] size × colour matrix
VARIANTS = {
    "tshirt-1": [
        ("S", "سفید شکسته", 12), ("M", "سفید شکسته", 8), ("L", "سفید شکسته", 3),
        ("M", "شنی", 6), ("L", "زغالی", 0),
    ],
    "tshirt-2": [("S", "کرم", 9), ("M", "کرم", 4), ("L", "کرم", 2)],
    "crop-5": [("S", "کرم", 7), ("M", "کرم", 1), ("L", "کرم", 0)],
    "socks-13": [("36-38", "کرم", 20), ("39-41", "کرم", 14), ("42-44", "کرم", 2)],
}

EXTRA_COUPONS = [
    # code, percent_off, amount_off, min_subtotal, max_uses, used_count, days_valid, active
    ("SUMMER20", 20, None, 1_000_000, 100, 37, 30, True),
    ("FIRST100", None, 100_000, 800_000, 50, 12, 60, True),
    ("VIP15", 15, None, 0, 20, 20, 45, True),        # exhausted: usage bar at 100%
    ("NOWRUZ25", 25, None, 500_000, None, 214, -10, False),  # expired campaign
]


async def _exists(conn, sql: str, params: dict) -> bool:
    return (await conn.execute(text(sql), params)).first() is not None


async def _seed_customers(conn) -> list[dict]:
    """Create the mock customer base: user row, profile and a default address."""
    people: list[dict] = []
    for index, (email, name, phone, province, city) in enumerate(CUSTOMERS):
        # staggered sign-up dates so the CRM list is not one timestamp
        signed_up = datetime.now(UTC) - timedelta(days=70 - index * 7)
        uid = (
            await conn.execute(
                text(
                    "INSERT INTO public.users (email, password_hash, created_at) "
                    "VALUES (:email, :hash, :created) RETURNING id"
                ),
                {
                    "email": email,
                    "hash": hash_password(CUSTOMER_PASSWORD),
                    "created": signed_up,
                },
            )
        ).scalar_one()
        uid = str(uid)
        # /admin/users shows the *profile's* created_at as the registration date,
        # so it has to carry the same staggered timestamp as the user row
        await conn.execute(
            text(
                "INSERT INTO public.profiles (id, full_name, phone, created_at) "
                "VALUES (CAST(:uid AS uuid), :name, :phone, :created)"
            ),
            {"uid": uid, "name": name, "phone": phone, "created": signed_up},
        )
        await conn.execute(
            text(
                "INSERT INTO public.user_roles (user_id, role) "
                "VALUES (CAST(:uid AS uuid), 'customer')"
            ),
            {"uid": uid},
        )
        address = {
            "title": "خانه",
            "receiver": name,
            "phone": phone,
            "province": province,
            "city": city,
            "postal_code": f"{RNG.randint(1000000000, 9999999999)}",
            "line": RNG.choice(STREETS).format(n=RNG.randint(1, 120)),
        }
        await conn.execute(
            text(
                "INSERT INTO public.addresses "
                "(user_id, title, receiver, phone, province, city, postal_code, line, is_default) "
                "VALUES (CAST(:uid AS uuid), :title, :receiver, :phone, :province, :city, "
                "        :postal_code, :line, true)"
            ),
            {"uid": uid, **address},
        )
        people.append({"id": uid, "name": name, "address": address})
    print(f"  ✓ {len(people)} customers (+ profiles, addresses)")
    return people


async def _seed_favorites(conn, people: list[dict], product_ids: list[str]) -> None:
    total = 0
    for person in people:
        for product_id in RNG.sample(product_ids, RNG.randint(1, 4)):
            await conn.execute(
                text(
                    "INSERT INTO public.favorites (user_id, product_id) "
                    "VALUES (CAST(:uid AS uuid), :pid) ON CONFLICT DO NOTHING"
                ),
                {"uid": person["id"], "pid": product_id},
            )
            total += 1
    print(f"  ✓ {total} favorites")


def _order_number(created: datetime, counter: int) -> str:
    """Mirror the column default's shape but stay collision-free across a batch."""
    return f"{created:%y%m%d}{counter:05d}"


async def _seed_orders(conn, people: list[dict], products: list[dict]) -> list[dict]:
    """Backdated orders across every status, with items, payments and stock effects."""
    shapes: list[tuple[str, str]] = []
    for status, payment_status, weight in ORDER_SHAPES:
        shapes.extend([(status, payment_status)] * weight)
    RNG.shuffle(shapes)

    made: list[dict] = []
    for index, (status, payment_status) in enumerate(shapes):
        person = RNG.choice(people)
        # spread over the last 60 days, denser recently so the trend line rises
        age_days = int(abs(RNG.gauss(0, 1)) * 20) % 60
        created = datetime.now(UTC) - timedelta(
            days=age_days, hours=RNG.randint(0, 23), minutes=RNG.randint(0, 59)
        )

        items = []
        subtotal = 0
        for product in RNG.sample(products, RNG.randint(1, 3)):
            quantity = RNG.randint(1, 2)
            sizes = list(product["sizes"]) or ["Free Size"]
            colors = [c["name"] for c in (product["colors"] or [])] or ["کرم"]
            items.append(
                {
                    "product_id": product["id"],
                    "name": product["name"],
                    "price": int(product["price"]),
                    "size": RNG.choice(sizes),
                    "color": RNG.choice(colors),
                    "image": (product["images"] or [None])[0],
                    "quantity": quantity,
                }
            )
            subtotal += int(product["price"]) * quantity

        # every fourth paid order carries a discount, so the KPI gross/net split
        # and the invoice's discount row are not always zero
        discount = 0
        if payment_status == "paid" and index % 4 == 0:
            discount = min(subtotal // 10, 150_000)
        shipping = 0 if (subtotal - discount) >= FREE_SHIPPING_THRESHOLD else SHIPPING_FLAT_FEE
        total = subtotal - discount + shipping

        address = person["address"]
        shipping_address = {
            "full_name": person["name"],
            "receiver": address["receiver"],
            "phone": address["phone"],
            "province": address["province"],
            "city": address["city"],
            "postal_code": address["postal_code"],
            "line": address["line"],
        }
        # a 24-digit Iran Post code, only once the parcel has actually left
        tracking = (
            "".join(str(RNG.randint(0, 9)) for _ in range(24))
            if status in ("shipped", "delivered")
            else None
        )

        row = (
            await conn.execute(
                text(
                    "INSERT INTO public.orders "
                    "(order_number, user_id, status, payment_status, payment_method, subtotal, "
                    " discount, shipping, total, shipping_address, tracking_code, created_at, "
                    " updated_at) "
                    "VALUES (:onum, CAST(:uid AS uuid), :status, :pstatus, 'online', :subtotal, "
                    "        :discount, :shipping, :total, CAST(:addr AS jsonb), :tracking, "
                    "        :created, :created) "
                    "RETURNING id, order_number"
                ),
                {
                    "onum": _order_number(created, index + 1),
                    "uid": person["id"],
                    "status": status,
                    "pstatus": payment_status,
                    "subtotal": subtotal,
                    "discount": discount,
                    "shipping": shipping,
                    "total": total,
                    "addr": json.dumps(shipping_address, ensure_ascii=False),
                    "tracking": tracking,
                    "created": created,
                },
            )
        ).mappings().first()
        order_id = str(row["id"])

        for item in items:
            await conn.execute(
                text(
                    "INSERT INTO public.order_items "
                    "(order_id, product_id, name, price, size, color, image, quantity) "
                    "VALUES (CAST(:oid AS uuid), :product_id, :name, :price, :size, :color, "
                    "        :image, :quantity)"
                ),
                {"oid": order_id, **item},
            )
            # a live order holds its units; a cancelled one never took them
            # (this mirrors checkout + the [BE-05] restore-on-cancel rule)
            if status != "cancelled":
                await conn.execute(
                    text(
                        "UPDATE public.products SET stock = GREATEST(stock - :qty, 0) "
                        "WHERE id = :pid"
                    ),
                    {"pid": item["product_id"], "qty": item["quantity"]},
                )

        if payment_status == "paid":
            await conn.execute(
                text(
                    "INSERT INTO public.payments "
                    "(order_id, user_id, amount, method, status, reference, authority, created_at) "
                    "VALUES (CAST(:oid AS uuid), CAST(:uid AS uuid), :amount, 'online', "
                    "        'succeeded', :ref, :authority, :created)"
                ),
                {
                    "oid": order_id,
                    "uid": person["id"],
                    "amount": total,
                    "ref": f"SND-{row['order_number']}-{RNG.randint(100000, 999999)}",
                    "authority": f"SIM{RNG.getrandbits(48):012X}",
                    "created": created,
                },
            )
        elif status == "pending" and index % 3 == 0:
            # an abandoned gateway attempt — the payments screen should show these
            await conn.execute(
                text(
                    "INSERT INTO public.payments "
                    "(order_id, user_id, amount, method, status, reference, authority, created_at) "
                    "VALUES (CAST(:oid AS uuid), CAST(:uid AS uuid), :amount, 'online', 'failed', "
                    "        :ref, :authority, :created)"
                ),
                {
                    "oid": order_id,
                    "uid": person["id"],
                    "amount": total,
                    "ref": f"SIM{RNG.getrandbits(48):012X}",
                    "authority": f"SIM{RNG.getrandbits(48):012X}",
                    "created": created,
                },
            )

        made.append(
            {
                "id": order_id,
                "user_id": person["id"],
                "status": status,
                "payment_status": payment_status,
                "total": total,
                "created": created,
            }
        )

    print(f"  ✓ {len(made)} orders (backdated over 60 days, stock adjusted)")
    return made


async def _seed_refunds(conn, orders: list[dict], admin_id: str | None) -> None:
    """One claim per cancelled+paid order, spread across the [BE-03] lifecycle."""
    candidates = [o for o in orders if o["status"] == "cancelled" and o["payment_status"] == "paid"]
    states = ["pending", "approved", "rejected", "refunded"]
    for index, order in enumerate(candidates):
        state = states[index % len(states)]
        resolved = state != "pending"
        await conn.execute(
            text(
                "INSERT INTO public.refund_requests "
                "(order_id, user_id, amount, reason, status, admin_note, bank_tracking_code, "
                " resolved_by, resolved_at, created_at) "
                "VALUES (CAST(:oid AS uuid), CAST(:uid AS uuid), :amount, :reason, :status, "
                "        :note, :bank, :resolver, :resolved_at, :created)"
            ),
            {
                "oid": order["id"],
                "uid": order["user_id"],
                "amount": order["total"],
                "reason": REFUND_REASONS[index % len(REFUND_REASONS)],
                "status": state,
                "note": {
                    "approved": "مرجوعی تأیید شد؛ در انتظار واریز.",
                    "rejected": "خارج از مهلت ۷ روزه تعویض بود.",
                    "refunded": "مبلغ از طریق پایا واریز شد.",
                }.get(state),
                "bank": f"PAYA{RNG.randint(10**11, 10**12 - 1)}" if state == "refunded" else None,
                "resolver": admin_id if resolved else None,
                "resolved_at": order["created"] + timedelta(days=2) if resolved else None,
                "created": order["created"] + timedelta(days=1),
            },
        )
        if state == "refunded":
            # keep the money story consistent: the order reads as refunded and
            # the ledger carries the matching refund row
            await conn.execute(
                text(
                    "UPDATE public.orders SET payment_status = 'refunded' "
                    "WHERE id = CAST(:oid AS uuid)"
                ),
                {"oid": order["id"]},
            )
            await conn.execute(
                text(
                    "INSERT INTO public.payments "
                    "(order_id, user_id, amount, method, status, reference, created_at) "
                    "VALUES (CAST(:oid AS uuid), CAST(:uid AS uuid), :amount, 'refund', "
                    "        'refunded', :ref, :created)"
                ),
                {
                    "oid": order["id"],
                    "uid": order["user_id"],
                    "amount": order["total"],
                    "ref": f"RFD-{order['id'][:8].upper()}",
                    "created": order["created"] + timedelta(days=2),
                },
            )
    print(f"  ✓ {len(candidates)} refund requests (pending/approved/rejected/refunded)")


async def _seed_reviews(conn, orders: list[dict]) -> None:
    """Reviews only from people who actually received the item."""
    delivered = [o for o in orders if o["status"] == "delivered"]
    written: set[tuple[str, str]] = set()
    count = 0
    for order in delivered:
        rows = (
            await conn.execute(
                text(
                    "SELECT product_id FROM public.order_items "
                    "WHERE order_id = CAST(:oid AS uuid) AND product_id IS NOT NULL"
                ),
                {"oid": order["id"]},
            )
        ).all()
        for (product_id,) in rows:
            key = (product_id, order["user_id"])
            if key in written:
                continue
            written.add(key)
            rating, title, body = REVIEW_TEXTS[count % len(REVIEW_TEXTS)]
            reply = SELLER_REPLIES.get(rating)
            await conn.execute(
                text(
                    "INSERT INTO public.product_reviews "
                    "(product_id, user_id, rating, title, body, status, seller_reply, "
                    " seller_replied_at, created_at, updated_at) "
                    "VALUES (:pid, CAST(:uid AS uuid), :rating, :title, :body, :status, :reply, "
                    "        :replied_at, :created, :created) "
                    "ON CONFLICT (product_id, user_id) DO NOTHING"
                ),
                {
                    "pid": product_id,
                    "uid": order["user_id"],
                    "rating": rating,
                    "title": title,
                    "body": body,
                    # one hidden review so the moderation filter has a subject
                    "status": "hidden" if count % 9 == 8 else "published",
                    "reply": reply,
                    "replied_at": order["created"] + timedelta(days=4) if reply else None,
                    "created": order["created"] + timedelta(days=3),
                },
            )
            count += 1
    print(f"  ✓ {count} product reviews (with seller replies + one hidden)")


async def _seed_variants(conn) -> None:
    count = 0
    for product_id, rows in VARIANTS.items():
        if not await _exists(conn, "SELECT 1 FROM public.products WHERE id = :pid",
                             {"pid": product_id}):
            continue
        for size, color, stock in rows:
            await conn.execute(
                text(
                    "INSERT INTO public.product_variants "
                    "(product_id, size, color, sku, stock, active) "
                    "VALUES (:pid, :size, :color, :sku, :stock, :active) "
                    "ON CONFLICT (product_id, size, color) DO NOTHING"
                ),
                {
                    "pid": product_id,
                    "size": size,
                    "color": color,
                    "sku": f"{product_id.upper()}-{size}-{abs(hash(color)) % 1000:03d}",
                    "stock": stock,
                    # a sold-out variant stays visible but inactive
                    "active": stock > 0,
                },
            )
            count += 1
    print(f"  ✓ {count} product variants (size × colour matrix)")


async def _seed_contact(conn) -> None:
    for index, (name, contact, message, status) in enumerate(CONTACT_MESSAGES):
        await conn.execute(
            text(
                "INSERT INTO public.contact_messages "
                "(name, contact, message, status, created_at) "
                "VALUES (:name, :contact, :message, :status, :created)"
            ),
            {
                "name": name,
                "contact": contact,
                "message": message,
                "status": status,
                "created": datetime.now(UTC) - timedelta(days=index * 2, hours=index),
            },
        )
    print(f"  ✓ {len(CONTACT_MESSAGES)} contact messages")


async def _seed_coupons(conn) -> None:
    now = datetime.now(UTC)
    for code, percent, amount, min_subtotal, max_uses, used, days, active in EXTRA_COUPONS:
        await conn.execute(
            text(
                "INSERT INTO public.coupons "
                "(code, percent_off, amount_off, min_subtotal, max_uses, max_uses_per_user, "
                " used_count, starts_at, expires_at, active) "
                "VALUES (:code, :percent, :amount, :min_subtotal, :max_uses, 1, :used, "
                "        :starts, :expires, :active) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {
                "code": code,
                "percent": percent,
                "amount": amount,
                "min_subtotal": min_subtotal,
                "max_uses": max_uses,
                "used": used,
                "starts": now - timedelta(days=30),
                "expires": now + timedelta(days=days),
                "active": active,
            },
        )
    print(f"  ✓ {len(EXTRA_COUPONS)} extra coupons (incl. one exhausted, one expired)")


async def _seed_low_stock(conn) -> None:
    """Force a couple of products under their threshold so the alerts light up."""
    await conn.execute(
        text("UPDATE public.products SET stock = 2 WHERE id = 'crop-6'")
    )
    await conn.execute(
        text("UPDATE public.products SET stock = 0, availability = 'coming_soon' "
             "WHERE id = 'set-18'")
    )
    print("  ✓ low-stock + coming-soon products for the dashboard alerts")


async def main() -> None:
    await startup_ddl()
    print("seeding mock store data…")
    async with engine.begin() as conn:
        if await _exists(
            conn, "SELECT 1 FROM public.users WHERE lower(email) = :email",
            {"email": MARKER_EMAIL},
        ):
            print("  • mock data already present — nothing to do")
            return

        products = (
            await conn.execute(
                text(
                    "SELECT id, name, price, sizes, colors, images FROM public.products "
                    "WHERE active ORDER BY id"
                )
            )
        ).mappings().all()
        if not products:
            print("  • no catalog — run `python -m app.seed_products` first, skipping")
            return
        products = [dict(p) for p in products]
        product_ids = [p["id"] for p in products]

        admin_row = (
            await conn.execute(
                text(
                    "SELECT u.id FROM public.users u JOIN public.user_roles r ON r.user_id = u.id "
                    "WHERE r.role::text IN ('admin', 'super_admin') LIMIT 1"
                )
            )
        ).first()
        admin_id = str(admin_row[0]) if admin_row else None

        people = await _seed_customers(conn)
        await _seed_favorites(conn, people, product_ids)
        orders = await _seed_orders(conn, people, products)
        await _seed_refunds(conn, orders, admin_id)
        await _seed_reviews(conn, orders)
        await _seed_variants(conn)
        await _seed_contact(conn)
        await _seed_coupons(conn)
        await _seed_low_stock(conn)
    print(f"done. mock customers sign in with the password «{CUSTOMER_PASSWORD}».")


if __name__ == "__main__":
    asyncio.run(main())
