"""Variant SKU / price override / swatch colour (AB-BE-02, spec [BE-01]).

* `sku` is unique when set (partial unique index); a duplicate is a clean 409 with its
  own message, blank means none;
* `price_override` (NULL = the product's price) is honoured by `POST /stock/check` and
  `POST /checkout` through one helper, read from the database only — a line cannot
  bring its own price;
* `color_hex` is `#rrggbb`;
* PATCH clears with `sku: ""`, `price_override: 0`, `color_hex: ""` (F5.16 convention).

Live-DB tests; they skip when no database is reachable.
"""

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text

from app.db import MigratorSessionLocal, SessionLocal, engine, startup_ddl
from app.main import app
from app.security import create_access_token

ADDRESS = {
    "full_name": "آزمون تنوع", "phone": "09120000000", "province": "تهران",
    "city": "تهران", "line": "خیابان آزمون، پلاک ۱", "postal_code": "1234567890",
}


async def _db_available() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture
async def db():
    await engine.dispose()
    if not await _db_available():
        pytest.skip("no database reachable — integration test skipped")
    await startup_ddl()
    async with SessionLocal() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def ctx(db):
    """An admin, a customer and two fresh products (100 000 / 250 000 tomans)."""
    tag = uuid4().hex[:6]
    users = {}
    for who, role in (("admin", "admin"), ("customer", None)):
        email = f"abbe02-{who}-{tag}@test.local"
        uid = (
            await db.execute(
                text("INSERT INTO public.users (email, password_hash) VALUES (:e, 'x') "
                     "RETURNING id"),
                {"e": email},
            )
        ).scalar()
        if role:
            await db.execute(
                text("INSERT INTO public.user_roles (user_id, role) VALUES (:u, :r)"),
                {"u": str(uid), "r": role},
            )
        users[who] = (uid, create_access_token(uid, email, "customer"))
    await db.commit()
    data = {"admin": users["admin"][1], "customer": users["customer"][1], "tag": tag}
    for key, price in (("p1", 100_000), ("p2", 250_000)):
        res = await _call("POST", "/products", data["admin"], json={
            "name": f"ABBE02-{tag}-{key}", "category": "tshirt", "price": price,
            "sizes": ["S", "M", "L"], "colors": [{"name": "کرم", "hex": "#f0ebe3"}],
            "stock": 50,
        })
        assert res.status_code == 201, res.text
        data[key] = res.json()["id"]
    yield data
    await db.rollback()
    await db.execute(
        text("DELETE FROM public.orders WHERE user_id = :u"), {"u": str(users["customer"][0])}
    )
    await db.execute(text("DELETE FROM public.products WHERE name LIKE :n"),
                     {"n": f"ABBE02-{tag}-%"})
    await db.execute(text("DELETE FROM public.users WHERE id = ANY(CAST(:ids AS uuid[]))"),
                     {"ids": [str(u[0]) for u in users.values()]})
    await db.commit()


async def _call(method: str, path: str, token: str | None, **kw) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return await client.request(method, path, headers=headers, **kw)


async def _variant(ctx, product: str, **body) -> httpx.Response:
    return await _call("POST", f"/products/{ctx[product]}/variants", ctx["admin"],
                       json={"size": "M", "color": "کرم", "stock": 10, **body})


async def test_ddl_is_in_place_and_idempotent(db):
    cols = (await db.execute(text(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'product_variants' "
        "AND column_name IN ('price_override', 'color_hex')"
    ))).all()
    assert dict(cols) == {"price_override": "integer", "color_hex": "text"}
    index = (await db.execute(text(
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'product_variants_sku_key'"
    ))).scalar()
    assert "UNIQUE" in index and "WHERE (sku IS NOT NULL)" in index
    await startup_ddl()  # a second boot changes nothing and does not fail


async def test_create_returns_the_new_fields(ctx):
    sku = f"ABBE02-{ctx['tag']}-M"
    res = await _variant(ctx, "p1", sku=f"  {sku} ", price_override=80_000, color_hex="#AA3300")
    assert res.status_code == 201, res.text
    body = res.json()
    assert (body["sku"], body["price_override"], body["color_hex"]) == (sku, 80_000, "#AA3300")
    listed = (await _call("GET", f"/products/{ctx['p1']}/variants", None)).json()
    assert listed[0]["price_override"] == 80_000 and listed[0]["color_hex"] == "#AA3300"


async def test_duplicate_sku_is_a_clean_409_even_across_products(ctx):
    sku = f"ABBE02-{ctx['tag']}-DUP"
    assert (await _variant(ctx, "p1", sku=sku)).status_code == 201
    dup = await _variant(ctx, "p2", sku=sku)
    assert dup.status_code == 409
    assert dup.json()["detail"] == "این SKU قبلاً برای تنوع دیگری ثبت شده است"
    # the size×colour rule keeps its own message
    same_combo = await _variant(ctx, "p1", size="M", sku=f"{sku}-2")
    assert same_combo.status_code == 409
    assert same_combo.json()["detail"] == "این ترکیب سایز و رنگ قبلاً ثبت شده است"
    # PATCH onto a taken SKU is the same 409
    other = (await _variant(ctx, "p2", size="S", sku=f"{sku}-3")).json()
    moved = await _call("PATCH", f"/variants/{other['id']}", ctx["admin"], json={"sku": sku})
    assert moved.status_code == 409 and moved.json()["detail"].startswith("این SKU")


async def test_blank_skus_are_none_and_never_collide(ctx):
    a = await _variant(ctx, "p1", size="S", sku="")
    b = await _variant(ctx, "p1", size="L", sku="   ")
    assert a.status_code == b.status_code == 201
    assert a.json()["sku"] is None and b.json()["sku"] is None


@pytest.mark.parametrize(
    "bad",
    [{"price_override": 0}, {"price_override": -5}, {"color_hex": "red"}, {"color_hex": "#12345"}],
)
async def test_invalid_values_are_422(ctx, bad):
    assert (await _variant(ctx, "p1", **bad)).status_code == 422


async def test_patch_sets_clears_and_leaves_unchanged(ctx, db):
    v = (await _variant(ctx, "p1", sku=f"ABBE02-{ctx['tag']}-P", price_override=90_000,
                        color_hex="#112233")).json()
    path = f"/variants/{v['id']}"
    res = await _call("PATCH", path, ctx["admin"], json={"stock": 4})
    assert (res.json()["price_override"], res.json()["color_hex"]) == (90_000, "#112233")
    res = await _call("PATCH", path, ctx["admin"],
                      json={"price_override": 0, "color_hex": "", "sku": ""})
    assert res.status_code == 200
    assert (res.json()["price_override"], res.json()["color_hex"], res.json()["sku"]) == (
        None, None, None)
    res = await _call("PATCH", path, ctx["admin"], json={"price_override": 70_000})
    assert res.json()["price_override"] == 70_000
    await db.commit()
    audit = (await db.execute(text(
        "SELECT old_values, new_values FROM public.audit_logs WHERE action = 'update_variant' "
        "AND entity_id = :e ORDER BY created_at DESC LIMIT 1"), {"e": v["id"]})).mappings().first()
    assert audit["old_values"] == {"price_override": None}
    assert audit["new_values"] == {"price_override": 70_000}


async def _stock_check(lines: list[dict]) -> httpx.Response:
    return await _call("POST", "/stock/check", None, json=lines)


async def test_override_prices_the_quote_and_the_order(ctx, db):
    await _variant(ctx, "p1", size="M", price_override=80_000)
    await _variant(ctx, "p1", size="L")  # no override → product price
    lines = [
        {"product_id": ctx["p1"], "size": "M", "color": "کرم", "quantity": 2},  # 160 000
        {"product_id": ctx["p1"], "size": "L", "color": "کرم", "quantity": 1},  # 100 000
        {"product_id": ctx["p1"], "size": "S", "color": "کرم", "quantity": 1},  # no row: 100 000
    ]
    quote = (await _stock_check(lines)).json()
    assert quote["ok"] and quote["subtotal"] == 360_000

    # a line cannot bring its own price: an extra field is ignored
    injected = [{**line, "price": 1} for line in lines]
    res = await _call("POST", "/checkout", ctx["customer"],
                      json={"lines": injected, "address": ADDRESS})
    assert res.status_code == 200, res.text
    order = res.json()
    assert order["subtotal"] == 360_000 == quote["subtotal"]
    assert order["total"] == 360_000 + 89_000  # below the free-shipping threshold
    await db.commit()
    prices = (await db.execute(text(
        "SELECT size, price FROM public.order_items WHERE order_id = :o ORDER BY size"),
        {"o": order["order_id"]})).all()
    assert dict(prices) == {"L": 100_000, "M": 80_000, "S": 100_000}


async def test_null_override_behaves_exactly_as_before(ctx):
    await _variant(ctx, "p2", size="M")
    quote = (await _stock_check(
        [{"product_id": ctx["p2"], "size": "M", "color": "کرم", "quantity": 3}])).json()
    assert quote["subtotal"] == 750_000


async def test_coupon_discount_uses_the_overridden_subtotal(ctx, db):
    await _variant(ctx, "p2", size="M", price_override=200_000)
    code = f"ABBE02{ctx['tag'].upper()}"
    created = await _call("POST", "/coupons", ctx["admin"], json={"code": code, "percent_off": 10})
    assert created.status_code == 201, created.text
    try:
        res = await _call("POST", "/checkout", ctx["customer"], json={
            "lines": [{"product_id": ctx["p2"], "size": "M", "color": "کرم", "quantity": 1}],
            "address": ADDRESS, "coupon_code": code,
        })
        assert res.status_code == 200, res.text
        assert (res.json()["subtotal"], res.json()["discount"]) == (200_000, 20_000)
    finally:
        await db.rollback()
        await db.execute(text("DELETE FROM public.orders WHERE id IN (SELECT order_id FROM "
                              "public.coupon_redemptions WHERE coupon_id IN (SELECT id FROM "
                              "public.coupons WHERE code = :c))"), {"c": code})
        await db.execute(text("DELETE FROM public.coupons WHERE code = :c"), {"c": code})
        await db.commit()


async def test_old_blank_and_duplicate_skus_cannot_block_the_index(ctx, db):
    """The migration path: rows written before the index existed. Replays the real
    CATALOG_DDL statements inside a transaction that is rolled back.

    Dropping and rebuilding the index is DDL, so it runs on the migrator connection
    (B5.1e) — the API's own role could not replay its own migration.
    """
    from app import db as dbmod

    stmts = [s for s in dbmod.CATALOG_DDL if "product_variants" in s and (
        s.startswith("UPDATE") or "product_variants_sku_key" in s)]
    assert len(stmts) == 3
    tag = ctx["tag"]
    async with MigratorSessionLocal() as mig:
        try:
            await mig.execute(text("DROP INDEX public.product_variants_sku_key"))
            for size, sku in (("S", f"OLD-{tag}"), ("M", f"OLD-{tag}"), ("L", "  ")):
                await mig.execute(text(
                    "INSERT INTO public.product_variants "
                    "(product_id, size, color, sku, created_at) "
                    "VALUES (:p, :s, 'کرم', :k, now() + make_interval(secs => :o))"),
                    {"p": ctx["p1"], "s": size, "k": sku, "o": {"S": 0, "M": 1, "L": 2}[size]})
            for stmt in stmts:
                await mig.execute(text(stmt))
            rows = dict((await mig.execute(text(
                "SELECT size, sku FROM public.product_variants WHERE product_id = :p"),
                {"p": ctx["p1"]})).all())
            assert rows == {"S": f"OLD-{tag}", "M": None, "L": None}  # earliest keeps it
        finally:
            await mig.rollback()


async def test_stock_check_returns_each_lines_server_unit_price(ctx):
    """F5.18: the storefront shows these instead of pricing lines itself."""
    await _variant(ctx, "p1", size="M", price_override=80_000)
    await _variant(ctx, "p1", size="L", stock=0)  # sold-out variant: an issue, still priced
    lines = [
        {"product_id": ctx["p1"], "size": "M", "color": "کرم", "quantity": 2},
        {"product_id": ctx["p1"], "size": "S", "color": "کرم", "quantity": 1},
        {"product_id": ctx["p1"], "size": "L", "color": "کرم", "quantity": 1},
        {"product_id": "abbe02-missing", "size": "M", "color": "کرم", "quantity": 1},
        {"product_id": ctx["p2"], "size": "M", "color": "کرم", "quantity": 1},
    ]
    quote = (await _stock_check(lines)).json()
    assert quote["unit_prices"] == [80_000, 100_000, 100_000, None, 250_000]
    # the subtotal still counts only the lines that can be bought
    assert quote["subtotal"] == 80_000 * 2 + 100_000 + 250_000
    assert {i["reason"] for i in quote["issues"]} == {"insufficient_stock", "not_found"}
