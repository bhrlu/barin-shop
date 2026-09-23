"""An audited mutation and its audit entry land together or not at all (B5.1d).

`record_audit` used to swallow an insert failure with `session.rollback()`: the
mutation vanished while the router committed an empty transaction and answered
200. It now re-raises, so the request fails (500) and nothing is persisted.

The failure is real, not mocked: a temporary trigger rejects the `audit_logs`
insert for one specific entity id, so nothing else sharing the database is
affected. Live-DB tests; they skip when no database is reachable.
"""

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text

from app.db import MigratorSessionLocal, SessionLocal, engine, startup_ddl
from app.main import app
from app.security import create_access_token
from app.services import notifications

ADDRESS = {
    "full_name": "آزمون ممیزی",
    "phone": "09120000000",
    "city": "تهران",
    "line": "خیابان آزمون، پلاک ۳",
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
    await notifications.drain()
    await engine.dispose()


@pytest.fixture
async def world(db):
    """A product (stock 10), a customer, an order_manager, and one pending order."""
    pid = f"test-b51d-{uuid4().hex[:8]}"
    await db.execute(
        text(
            "INSERT INTO public.products (id, name, category, price, sizes, stock, active) "
            "VALUES (:pid, 'B5.1d test', 'test', 100000, ARRAY['M'], 10, true)"
        ),
        {"pid": pid},
    )
    people = {}
    for label, role in (("customer", None), ("manager", "order_manager")):
        email = f"b51d-{label}-{uuid4().hex[:6]}@test.local"
        uid = (
            await db.execute(
                text(
                    "INSERT INTO public.users (email, password_hash) "
                    "VALUES (:e, 'x') RETURNING id"
                ),
                {"e": email},
            )
        ).scalar()
        await db.execute(text("INSERT INTO public.profiles (id) VALUES (:u)"), {"u": str(uid)})
        if role:
            await db.execute(
                text("INSERT INTO public.user_roles (user_id, role) VALUES (:u, :r)"),
                {"u": str(uid), "r": role},
            )
        people[label] = {"id": uid, "token": create_access_token(uid, email, "customer")}
    await db.commit()
    res = await _call(
        "POST",
        "/checkout",
        people["customer"]["token"],
        json={
            "lines": [{"product_id": pid, "size": "M", "color": "مشکی", "quantity": 2}],
            "address": ADDRESS,
        },
    )
    assert res.status_code == 200, res.text
    try:
        yield {"product": pid, "order": res.json()["order_id"], **people}
    finally:
        await notifications.drain()
        ids = [str(p["id"]) for p in people.values()]
        # # audit_logs is append-only (B5.1b): deleting the users only nulls admin_id
        await db.execute(
            text("DELETE FROM public.users WHERE id = ANY(CAST(:ids AS uuid[]))"), {"ids": ids}
        )
        await db.execute(text("DELETE FROM public.products WHERE id = :p"), {"p": pid})
        await db.commit()


@pytest.fixture
async def break_audit(db):
    """Make every audit insert for the given entity id fail (DB-level trigger).

    The trigger is created on the migrator connection (B5.1e): the API's own role
    cannot create or drop one, which is the point of the split.
    """
    names: list[str] = []

    async def _break(entity_id: str) -> None:
        name = f"b51d_{uuid4().hex[:10]}"
        names.append(name)
        async with MigratorSessionLocal() as mig:
            await mig.execute(
                text(
                    f"CREATE FUNCTION public.{name}() RETURNS trigger LANGUAGE plpgsql AS "
                    "$$ BEGIN RAISE EXCEPTION 'forced audit failure (B5.1d test)'; END $$"
                )
            )
            await mig.execute(
                text(
                    f"CREATE TRIGGER {name} BEFORE INSERT ON public.audit_logs FOR EACH ROW "
                    f"WHEN (NEW.entity_id = '{entity_id}') EXECUTE FUNCTION public.{name}()"
                )
            )
            await mig.commit()

    yield _break
    async with MigratorSessionLocal() as mig:
        for name in names:
            await mig.execute(text(f"DROP TRIGGER IF EXISTS {name} ON public.audit_logs"))
            await mig.execute(text(f"DROP FUNCTION IF EXISTS public.{name}()"))
        await mig.commit()


async def _call(method: str, path: str, token: str, **kw) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        return await client.request(
            method, path, headers={"Authorization": f"Bearer {token}"}, **kw
        )


async def _one(db, sql: str, **params):
    await db.commit()  # fresh snapshot
    return (await db.execute(text(sql), params)).first()


async def _order_state(db, order_id):
    return await _one(
        db,
        "SELECT status, payment_status FROM public.orders WHERE id = CAST(:o AS uuid)",
        o=order_id,
    )


async def _stock(db, pid) -> int:
    return (await _one(db, "SELECT stock FROM public.products WHERE id = :p", p=pid))[0]


async def _notes(db, user_id, type_) -> int:
    row = await _one(
        db,
        "SELECT COUNT(*) FROM public.notifications WHERE user_id = :u AND type = :t",
        u=str(user_id),
        t=type_,
    )
    return row[0]


async def test_status_change_and_its_audit_fail_together(db, world, break_audit):
    await break_audit(world["order"])
    res = await _call(
        "PATCH",
        f"/orders/{world['order']}",
        world["manager"]["token"],
        json={"status": "processing"},
    )
    assert res.status_code == 500
    assert tuple(await _order_state(db, world["order"])) == ("pending", "unpaid")


async def test_staff_cancel_rolls_back_stock_and_notification_too(db, world, break_audit):
    assert await _stock(db, world["product"]) == 8
    await break_audit(world["order"])
    res = await _call(
        "PATCH",
        f"/orders/{world['order']}",
        world["manager"]["token"],
        json={"status": "cancelled"},
    )
    assert res.status_code == 500
    assert (await _order_state(db, world["order"]))[0] == "pending"
    assert await _stock(db, world["product"]) == 8  # the restore was rolled back with it
    assert await _notes(db, world["customer"]["id"], "order_cancelled") == 0


async def test_customer_cancel_is_atomic_too(db, world, break_audit):
    await break_audit(world["order"])
    res = await _call("POST", f"/orders/{world['order']}/cancel", world["customer"]["token"])
    assert res.status_code == 500
    assert (await _order_state(db, world["order"]))[0] == "pending"
    assert await _stock(db, world["product"]) == 8


async def test_refund_settlement_is_atomic(db, world, break_audit):
    order, customer = world["order"], world["customer"]["token"]
    await _call("POST", f"/orders/{order}/payment-complete", customer, json={"outcome": "success"})
    await _call("POST", f"/orders/{order}/cancel", customer)
    refund = await _call("POST", f"/orders/{order}/refunds", customer, json={"reason": "سایز"})
    assert refund.status_code == 201, refund.text
    refund_id = refund.json()["id"]

    await break_audit(order)  # resolve_refund audits against the order id
    res = await _call(
        "PATCH",
        f"/refunds/{refund_id}",
        world["manager"]["token"],
        json={"status": "refunded", "bank_tracking_code": "PAYA-1"},
    )
    assert res.status_code == 500
    status = await _one(
        db, "SELECT status FROM public.refund_requests WHERE id = CAST(:r AS uuid)", r=refund_id
    )
    assert status[0] == "pending"
    assert (await _order_state(db, order))[1] == "paid"
    refunds = await _one(
        db,
        "SELECT COUNT(*) FROM public.payments WHERE order_id = CAST(:o AS uuid) "
        "AND method = 'refund'",
        o=order,
    )
    assert refunds[0] == 0  # no money moved on paper
    assert await _notes(db, world["customer"]["id"], "refund_settled") == 0


async def test_coupon_edit_is_atomic(db, world, break_audit):
    code = f"B51D{uuid4().hex[:6].upper()}"
    token = world["manager"]["token"]  # order_manager holds the coupons capability
    created = await _call("POST", "/coupons", token, json={"code": code, "percent_off": 10})
    assert created.status_code == 201, created.text
    coupon_id = (await _one(db, "SELECT id FROM public.coupons WHERE code = :c", c=code))[0]
    try:
        await break_audit(str(coupon_id))
        res = await _call("PATCH", f"/coupons/{coupon_id}", token, json={"percent_off": 50})
        assert res.status_code == 500
        pct = await _one(db, "SELECT percent_off FROM public.coupons WHERE id = :c", c=coupon_id)
        assert pct[0] == 10
    finally:
        await db.execute(text("DELETE FROM public.coupons WHERE id = :c"), {"c": coupon_id})
        await db.commit()


async def test_the_normal_path_still_commits_with_its_entry(db, world):
    res = await _call(
        "PATCH",
        f"/orders/{world['order']}",
        world["manager"]["token"],
        json={"status": "processing"},
    )
    assert res.status_code == 200
    assert (await _order_state(db, world["order"]))[0] == "processing"
    entry = await _one(
        db,
        "SELECT COUNT(*) FROM public.audit_logs WHERE entity_id = :e "
        "AND action = 'update_order_status'",
        e=world["order"],
    )
    assert entry[0] == 1
