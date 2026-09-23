"""The inventory ledger (AB-BE-01, spec [BE-01] `inventory_logs`).

Every stock movement writes exactly one ledger row in the same transaction:
checkout → `purchase` (−qty per line), cancellation → `return` (+qty, so an order
nets to zero), a new product / variant → `restock` (its opening stock), a staff stock
edit → `manual_adjustment` (the delta). The ledger is append-only and has no foreign
keys: deleting a referenced order / variant / user leaves its rows exactly as written.
Live-DB tests (they skip when no database is reachable); the ledger rows they write
stay — that is the point.
"""

from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db import SessionLocal, engine, startup_ddl
from app.main import app
from app.security import create_access_token

ADDRESS = {
    "full_name": "آزمون دفتر انبار", "phone": "09120000000", "province": "تهران",
    "city": "تهران", "line": "خیابان آزمون", "postal_code": "1234567890",
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


async def _call(method: str, path: str, token: str | None, **kw) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return await client.request(method, path, headers=headers, **kw)


@pytest.fixture
async def world(db):
    """Admin, support and customer accounts; a product (stock 10, sizes M/L) created
    through the API with one variant M/مشکی (stock 4)."""
    tag = uuid4().hex[:6]
    ids, tokens = {}, {}
    for who, role in (("admin", "admin"), ("support", "support"), ("customer", None)):
        email = f"abbe01-{who}-{tag}@test.local"
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
        ids[who], tokens[who] = uid, create_access_token(uid, email, "customer")
    await db.commit()
    created = await _call("POST", "/products", tokens["admin"], json={
        "name": f"ABBE01-{tag}", "category": "tshirt", "price": 100_000,
        "sizes": ["M", "L"], "colors": [{"name": "مشکی", "hex": "#111111"}], "stock": 10,
    })
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    variant = await _call("POST", f"/products/{pid}/variants", tokens["admin"],
                          json={"size": "M", "color": "مشکی", "stock": 4})
    assert variant.status_code == 201, variant.text
    yield {"ids": ids, "tokens": tokens, "pid": pid, "vid": variant.json()["id"], "tag": tag}
    await db.rollback()
    await db.execute(text("DELETE FROM public.products WHERE id = :p"), {"p": pid})
    await db.execute(
        text("DELETE FROM public.users WHERE id = ANY(CAST(:ids AS uuid[]))"),
        {"ids": [str(u) for u in ids.values()]},
    )
    await db.commit()


async def _rows(db, **where) -> list[dict]:
    await db.commit()
    clause = " AND ".join(f"{k} = :{k}" for k in where)
    return [
        dict(r)
        for r in (
            await db.execute(
                text(
                    "SELECT product_id, variant_id, order_id, change_amount, reason, created_by "
                    f"FROM public.inventory_logs WHERE {clause} ORDER BY created_at, id"
                ),
                {k: str(v) for k, v in where.items()},
            )
        ).mappings().all()
    ]


async def _checkout(world, lines: list[tuple[str, int]]) -> httpx.Response:
    return await _call("POST", "/checkout", world["tokens"]["customer"], json={
        "lines": [
            {"product_id": world["pid"], "size": size, "color": "مشکی", "quantity": qty}
            for size, qty in lines
        ],
        "address": ADDRESS,
    })


async def _stocks(db, world) -> tuple[int, int]:
    await db.commit()
    product = (await db.execute(text("SELECT stock FROM public.products WHERE id = :p"),
                                {"p": world["pid"]})).scalar()
    variant = (await db.execute(text("SELECT stock FROM public.product_variants WHERE id = :v"),
                                {"v": world["vid"]})).scalar()
    return int(product), int(variant)


async def test_opening_stock_is_a_restock(db, world):
    rows = await _rows(db, product_id=world["pid"])
    admin = world["ids"]["admin"]
    seen = [(r["reason"], r["change_amount"], r["variant_id"], r["created_by"]) for r in rows]
    assert seen == [("restock", 10, None, admin), ("restock", 4, UUID(world["vid"]), admin)]


async def test_checkout_and_cancel_net_to_zero(db, world):
    before = await _stocks(db, world)
    res = await _checkout(world, [("M", 2), ("L", 1)])  # M has a variant row, L does not
    assert res.status_code == 200, res.text
    oid = res.json()["order_id"]
    purchase = await _rows(db, order_id=oid)
    cust = world["ids"]["customer"]
    assert sorted((r["change_amount"], r["variant_id"] is not None) for r in purchase) == [
        (-2, True), (-1, False)]
    assert {r["reason"] for r in purchase} == {"purchase"}
    assert {r["created_by"] for r in purchase} == {cust}

    cancel = await _call("POST", f"/orders/{oid}/cancel", world["tokens"]["customer"])
    assert cancel.status_code == 200
    rows = await _rows(db, order_id=oid)
    returns = [r for r in rows if r["reason"] == "return"]
    assert sorted(r["change_amount"] for r in returns) == [1, 2]
    assert {str(r["variant_id"]) for r in returns if r["change_amount"] == 2} == {world["vid"]}
    assert sum(r["change_amount"] for r in rows) == 0
    assert await _stocks(db, world) == before


async def test_a_staff_cancellation_is_attributed_to_staff(db, world):
    oid = (await _checkout(world, [("M", 1)])).json()["order_id"]
    res = await _call("PATCH", f"/orders/{oid}", world["tokens"]["admin"],
                      json={"status": "cancelled"})
    assert res.status_code == 200, res.text
    returns = [r for r in await _rows(db, order_id=oid) if r["reason"] == "return"]
    assert [(r["change_amount"], r["created_by"]) for r in returns] == [
        (1, world["ids"]["admin"])]


async def test_a_stale_second_cancel_logs_no_second_return(db, world):
    from app.services.order_lifecycle import CancelError, cancel_order_tx

    oid = (await _checkout(world, [("M", 1)])).json()["order_id"]
    cancel = await _call("POST", f"/orders/{oid}/cancel", world["tokens"]["customer"])
    assert cancel.status_code == 200
    with pytest.raises(CancelError):  # B6.19: a caller that read `pending` earlier
        await cancel_order_tx(db, oid, "pending")
    await db.rollback()
    assert [r["reason"] for r in await _rows(db, order_id=oid)] == ["purchase", "return"]


async def test_manual_adjustments_log_the_delta(db, world):
    admin = world["tokens"]["admin"]
    product, variant = f"/products/{world['pid']}", f"/variants/{world['vid']}"
    for path, body in (
        (product, {"stock": 7}),  # 10 → 7
        (variant, {"stock": 9}),  # 4 → 9
        (product, {"name": "x"}),  # no stock in the patch: no movement
        (product, {"stock": 7}),  # the current value: no movement
    ):
        assert (await _call("PATCH", path, admin, json=body)).status_code == 200
    rows = await _rows(db, product_id=world["pid"])
    manual = [r for r in rows if r["reason"] == "manual_adjustment"]
    assert [(r["change_amount"], r["variant_id"] is not None) for r in manual] == [
        (-3, False), (5, True)]


async def test_a_failed_checkout_logs_nothing(db, world):
    res = await _checkout(world, [("M", 5)])  # the variant holds 4
    assert res.status_code == 409
    assert [r for r in await _rows(db, product_id=world["pid"]) if r["reason"] == "purchase"] == []


async def _refused(db, sql: str, **params) -> str:
    with pytest.raises(DBAPIError) as exc:
        await db.execute(text(sql), params)
    await db.rollback()
    return str(exc.value)


async def test_the_ledger_is_append_only(db, world):
    pid = world["pid"]
    assert "append-only" in await _refused(
        db, "UPDATE public.inventory_logs SET change_amount = 99 WHERE product_id = :p", p=pid)
    assert "append-only" in await _refused(
        db, "DELETE FROM public.inventory_logs WHERE product_id = :p", p=pid)
    assert "append-only" in await _refused(db, "TRUNCATE public.inventory_logs")
    assert "check" in (await _refused(
        db, "INSERT INTO public.inventory_logs (product_id, change_amount, reason) "
            "VALUES (:p, 1, 'theft')", p=pid)).lower()
    assert len(await _rows(db, product_id=pid)) == 2  # the two restocks, untouched


async def test_deleting_what_a_row_refers_to_leaves_the_row_as_written(db, world):
    oid = (await _checkout(world, [("M", 1)])).json()["order_id"]
    before = await _rows(db, order_id=oid)
    # one statement deleting the customer cascades to the order: the case FK
    # `SET NULL` links could not survive
    await db.execute(text("DELETE FROM public.users WHERE id = :u"),
                     {"u": str(world["ids"]["customer"])})
    await db.execute(text("DELETE FROM public.product_variants WHERE id = CAST(:v AS uuid)"),
                     {"v": world["vid"]})
    await db.commit()
    after = await _rows(db, order_id=oid)
    assert after == before and len(after) == 1
    assert str(after[0]["variant_id"]) == world["vid"]


async def test_the_read_endpoint(db, world):
    oid = (await _checkout(world, [("M", 1)])).json()["order_id"]
    admin = world["tokens"]["admin"]
    res = await _call("GET", "/admin/inventory/logs", admin, params={"product_id": world["pid"]})
    assert res.status_code == 200
    env = res.json()
    assert {"items", "total", "page", "page_size", "pages"} <= set(env)
    assert env["total"] == 3  # two restocks + one purchase
    assert env["items"][0]["reason"] == "purchase"  # newest first
    assert env["items"][0]["product_name"] == f"ABBE01-{world['tag']}"
    assert env["items"][0]["size"] == "M"
    by_order = (await _call("GET", "/admin/inventory/logs", admin, params={"order_id": oid})).json()
    assert [i["order_number"] is not None for i in by_order["items"]] == [True]
    restocks = (await _call("GET", "/admin/inventory/logs", admin,
                            params={"product_id": world["pid"], "reason": "restock"})).json()
    assert restocks["total"] == 2
    assert (await _call("GET", "/admin/inventory/logs", admin,
                        params={"reason": "theft"})).status_code == 422
    for who in ("support", "customer"):
        res = await _call("GET", "/admin/inventory/logs", world["tokens"][who])
        assert res.status_code == 403
    assert (await _call("GET", "/admin/inventory/logs", None)).status_code == 401
