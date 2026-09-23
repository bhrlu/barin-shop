"""Integration tests for per-variant stock restoration on cancellation (B6.8).

These run against a live Postgres (the local docker-compose stack) because the
invariant under test — checkout decrements variant *and* aggregate stock, and
cancellation gives both back exactly once — only exists in SQL. When no
database is reachable the module skips instead of failing, so the pure-unit
suite still runs anywhere.

Every test creates its own throwaway product/user and rolls the data back out
in a fixture teardown, so the running store's data is never touched.
"""

import os
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://sande:sande@localhost:5432/postgres"
)
os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal, engine, startup_ddl  # noqa: E402
from app.services.checkout import create_order  # noqa: E402
from app.services.order_lifecycle import CancelError, cancel_order_tx  # noqa: E402

ADDRESS = {
    "full_name": "تست",
    "phone": "09120000000",
    "province": "تهران",
    "city": "تهران",
    "line": "خیابان تست",
    "postal_code": "1234567890",
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
    # each test runs in its own event loop; pooled connections belong to the
    # previous one, so the shared engine is emptied before every test.
    await engine.dispose()
    if not await _db_available():
        pytest.skip("no database reachable — integration test skipped")
    await startup_ddl()
    async with SessionLocal() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def fixtures(db):
    """A product with two size×color variants and a throwaway customer."""
    pid = f"test-b68-{uuid4().hex[:8]}"
    email = f"b68-{uuid4().hex[:8]}@test.local"
    await db.execute(
        text(
            "INSERT INTO public.products (id, name, category, price, sizes, stock, active) "
            "VALUES (:pid, 'B6.8 test', 'test', 100000, ARRAY['M','L'], 10, true)"
        ),
        {"pid": pid},
    )
    variant_id = (
        await db.execute(
            text(
                "INSERT INTO public.product_variants (product_id, size, color, stock) "
                "VALUES (:pid, 'M', 'مشکی', 4) RETURNING id"
            ),
            {"pid": pid},
        )
    ).scalar()
    user_id = (
        await db.execute(
            text(
                "INSERT INTO public.users (email, password_hash) "
                "VALUES (:email, 'x') RETURNING id"
            ),
            {"email": email},
        )
    ).scalar()
    await db.commit()
    try:
        yield {"product_id": pid, "variant_id": variant_id, "user_id": user_id}
    finally:
        # orders/items/variants cascade from the user and product rows
        await db.execute(
            text("DELETE FROM public.users WHERE id = :uid"), {"uid": str(user_id)}
        )
        await db.execute(
            text("DELETE FROM public.products WHERE id = :pid"), {"pid": pid}
        )
        await db.commit()


async def _stocks(db, fx) -> tuple[int, int]:
    product = (
        await db.execute(
            text("SELECT stock FROM public.products WHERE id = :pid"),
            {"pid": fx["product_id"]},
        )
    ).scalar()
    variant = (
        await db.execute(
            text("SELECT stock FROM public.product_variants WHERE id = :vid"),
            {"vid": str(fx["variant_id"])},
        )
    ).scalar()
    return int(product), int(variant)


async def _checkout(db, fx, size: str, color: str, qty: int = 2) -> dict:
    order = await create_order(
        db,
        fx["user_id"],
        [{"product_id": fx["product_id"], "size": size, "color": color, "quantity": qty}],
        ADDRESS,
        None,
    )
    await db.commit()
    return order


class TestVariantStockRestoration:
    async def test_checkout_decrements_both_aggregate_and_variant(self, db, fixtures):
        before = await _stocks(db, fixtures)
        await _checkout(db, fixtures, "M", "مشکی", qty=2)
        assert await _stocks(db, fixtures) == (before[0] - 2, before[1] - 2)

    async def test_checkout_persists_variant_id_on_the_order_item(self, db, fixtures):
        order = await _checkout(db, fixtures, "M", "مشکی", qty=1)
        stored = (
            await db.execute(
                text(
                    "SELECT variant_id FROM public.order_items "
                    "WHERE order_id = CAST(:oid AS uuid)"
                ),
                {"oid": order["order_id"]},
            )
        ).scalar()
        assert str(stored) == str(fixtures["variant_id"])

    async def test_cancellation_restores_both_stocks(self, db, fixtures):
        before = await _stocks(db, fixtures)
        order = await _checkout(db, fixtures, "M", "مشکی", qty=2)
        await cancel_order_tx(db, order["order_id"], "pending")
        await db.commit()
        assert await _stocks(db, fixtures) == before

    async def test_second_cancellation_does_not_inflate_stock(self, db, fixtures):
        before = await _stocks(db, fixtures)
        order = await _checkout(db, fixtures, "M", "مشکی", qty=2)
        await cancel_order_tx(db, order["order_id"], "pending")
        await db.commit()
        # the order is `cancelled` now — a repeat is refused, so nothing moves
        with pytest.raises(CancelError):
            await cancel_order_tx(db, order["order_id"], "cancelled")
        await db.rollback()
        assert await _stocks(db, fixtures) == before

    async def test_line_without_a_variant_row_restores_aggregate_only(self, db, fixtures):
        """Legacy / matrix-less lines: variant_id stays NULL and is safe to cancel."""
        before = await _stocks(db, fixtures)
        order = await _checkout(db, fixtures, "L", "سفید", qty=3)  # no variant row for L
        stored = (
            await db.execute(
                text(
                    "SELECT variant_id FROM public.order_items "
                    "WHERE order_id = CAST(:oid AS uuid)"
                ),
                {"oid": order["order_id"]},
            )
        ).scalar()
        assert stored is None
        assert await _stocks(db, fixtures) == (before[0] - 3, before[1])
        await cancel_order_tx(db, order["order_id"], "pending")
        await db.commit()
        assert await _stocks(db, fixtures) == before


class TestConcurrentCancellation:
    """B6.19: `cancel_order_tx` used to trust the status its caller had read without a
    lock, so two cancels racing (customer POST /cancel + staff PATCH, or a double
    click) both restored the stock — reproduced 5 of 6 times against the live stack
    (+2 units each). The status flip is now a compare-and-set."""

    async def test_a_stale_second_cancel_restores_nothing(self, db, fixtures):
        before = await _stocks(db, fixtures)
        order = await _checkout(db, fixtures, "M", "مشکی", qty=2)
        await cancel_order_tx(db, order["order_id"], "pending")
        await db.commit()
        # the caller read `pending` before the first cancel committed
        with pytest.raises(CancelError) as exc:
            await cancel_order_tx(db, order["order_id"], "pending")
        await db.rollback()
        assert exc.value.already_cancelled
        assert await _stocks(db, fixtures) == before

    async def test_two_sessions_racing_restore_once(self, db, fixtures):
        import asyncio

        before = await _stocks(db, fixtures)
        order = await _checkout(db, fixtures, "M", "مشکی", qty=2)

        async def cancel() -> str:
            async with SessionLocal() as session:
                try:
                    await cancel_order_tx(session, order["order_id"], "pending")
                    await asyncio.sleep(0.2)  # hold the row lock across the other attempt
                    await session.commit()
                    return "cancelled"
                except CancelError as error:
                    await session.rollback()
                    return "already" if error.already_cancelled else "refused"

        outcomes = sorted(await asyncio.gather(cancel(), cancel()))
        assert outcomes == ["already", "cancelled"]
        await db.commit()
        assert await _stocks(db, fixtures) == before

    async def test_a_move_between_read_and_cancel_is_refused(self, db, fixtures):
        before = await _stocks(db, fixtures)
        order = await _checkout(db, fixtures, "M", "مشکی", qty=2)
        await db.execute(
            text("UPDATE public.orders SET status = 'shipped' WHERE id = CAST(:o AS uuid)"),
            {"o": order["order_id"]},
        )
        await db.commit()
        with pytest.raises(CancelError) as exc:  # the caller still thinks `pending`
            await cancel_order_tx(db, order["order_id"], "pending")
        await db.rollback()
        assert not exc.value.already_cancelled
        assert await _stocks(db, fixtures) == (before[0] - 2, before[1] - 2)


async def test_http_customer_and_staff_cancelling_at_once(db, fixtures):
    """The reported race through the real endpoints: one restore, both callers answered."""
    import asyncio

    import httpx

    from app.main import app
    from app.security import create_access_token

    admin_id = (
        await db.execute(
            text("INSERT INTO public.users (email, password_hash) VALUES (:e, 'x') RETURNING id"),
            {"e": f"b619-{uuid4().hex[:8]}@test.local"},
        )
    ).scalar()
    await db.execute(
        text("INSERT INTO public.user_roles (user_id, role) VALUES (:u, 'admin')"),
        {"u": str(admin_id)},
    )
    await db.commit()
    try:
        cust = create_access_token(fixtures["user_id"], "c@test.local", "customer")
        staff = create_access_token(admin_id, "a@test.local", "customer")
        for _ in range(3):
            before = await _stocks(db, fixtures)
            order = await _checkout(db, fixtures, "M", "مشکی", qty=1)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                r1, r2 = await asyncio.gather(
                    client.post(
                        f"/orders/{order['order_id']}/cancel",
                        headers={"Authorization": f"Bearer {cust}"},
                    ),
                    client.patch(
                        f"/orders/{order['order_id']}",
                        headers={"Authorization": f"Bearer {staff}"},
                        json={"status": "cancelled"},
                    ),
                )
            assert r1.status_code == 200, r1.text
            assert r2.status_code in (200, 409), r2.text
            await db.commit()
            assert await _stocks(db, fixtures) == before
    finally:
        await db.execute(text("DELETE FROM public.users WHERE id = :u"), {"u": str(admin_id)})
        await db.commit()
