"""Integration tests for the preorder fulfilment flag (B4.13, decision D4).

These run against a live Postgres (the local docker-compose stack) because the
invariant under test — a preorder order takes money but never stock, and the
ledger stays a true mirror — only exists in SQL. When no database is reachable
the module skips instead of failing, so the pure-unit suite still runs anywhere.

D4 rules exercised here:
* `availability=preorder` is orderable (`availability_issue()` no longer blocks it);
* checkout decrements **nothing** — product aggregate, variant row, or ledger;
* the order item carries the explicit `is_preorder` marker;
* cancellation restores nothing for a preorder line (its `purchase` never happened);
* a mixed order (normal + preorder lines) splits the behaviour per line;
* the checkout notification is the preorder variant of "order created".

Every test creates its own throwaway product/user and rolls the data back out
in a fixture teardown, so the running store's data is never touched.
"""

import os
from uuid import uuid4

os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal, startup_ddl  # noqa: E402
from app.services.checkout import create_order  # noqa: E402
from app.services.notifications import notify_order_event  # noqa: E402
from app.services.order_lifecycle import cancel_order_tx  # noqa: E402
from tests.test_order_lifecycle_stock import ADDRESS  # noqa: E402


@pytest.fixture
async def db():
    from app.db import engine

    # each test runs its own event loop; pooled connections belong to the
    # previous one, so the shared engine is emptied before every test.
    await engine.dispose()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("no database reachable — integration test skipped")
    await startup_ddl()
    async with SessionLocal() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def fx(db):
    """An in-stock product with a variant row + a preorder product with one."""
    email = f"b413-{uuid4().hex[:8]}@test.local"
    normal_pid = f"test-b413-normal-{uuid4().hex[:8]}"
    pre_pid = f"test-b413-pre-{uuid4().hex[:8]}"
    user_id = (
        await db.execute(
            text(
                "INSERT INTO public.users (email, password_hash) "
                "VALUES (:email, 'x') RETURNING id"
            ),
            {"email": email},
        )
    ).scalar()
    await db.execute(
        text(
            "INSERT INTO public.products (id, name, category, price, sizes, stock, active) "
            "VALUES (:pid, 'B4.13 normal', 'test', 100000, ARRAY['M'], 10, true)"
        ),
        {"pid": normal_pid},
    )
    await db.execute(
        text(
            "INSERT INTO public.products (id, name, category, price, sizes, stock, active, "
            "availability) VALUES (:pid, 'B4.13 preorder', 'test', 100000, ARRAY['M'], 10, "
            "true, 'preorder')"
        ),
        {"pid": pre_pid},
    )
    await db.commit()
    try:
        yield {"user_id": user_id, "normal": normal_pid, "preorder": pre_pid}
    finally:
        await db.execute(
            text("DELETE FROM public.users WHERE id = :uid"), {"uid": str(user_id)}
        )
        await db.execute(
            text("DELETE FROM public.products WHERE id IN (:a, :b)"),
            {"a": normal_pid, "b": pre_pid},
        )
        await db.commit()


async def _product_stock(db, pid: str) -> int:
    return int(
        (
            await db.execute(
                text("SELECT stock FROM public.products WHERE id = :pid"), {"pid": pid}
            )
        ).scalar()
    )


async def _item(db, order_id: str) -> dict:
    row = (
        await db.execute(
            text(
                "SELECT product_id, quantity, is_preorder FROM public.order_items "
                "WHERE order_id = CAST(:oid AS uuid)"
            ),
            {"oid": order_id},
        )
    ).mappings().first()
    return dict(row) if row else {}


class TestPreorderCheckout:
    async def test_preorder_orderable_with_zero_stock(self, db, fx):
        """D4: preorder sells even at stock 0 — stock is not the gate."""
        await db.execute(
            text("UPDATE public.products SET stock = 0 WHERE id = :pid"),
            {"pid": fx["preorder"]},
        )
        await db.commit()
        await create_order(
            db,
            fx["user_id"],
            [{"product_id": fx["preorder"], "size": "M", "color": "x", "quantity": 2}],
            ADDRESS,
            None,
        )
        await db.commit()
        assert (await _product_stock(db, fx["preorder"])) == 0

    async def test_stock_and_ledger_untouched(self, db, fx):
        from app.services.inventory_log import log_stock_change

        # a restock row so the query proves the filter, not an empty table
        await log_stock_change(
            db, product_id=fx["preorder"], change=10, reason="restock"
        )
        await db.commit()

        before = await _product_stock(db, fx["preorder"])
        order = await create_order(
            db,
            fx["user_id"],
            [{"product_id": fx["preorder"], "size": "M", "color": "x", "quantity": 3}],
            ADDRESS,
            None,
        )
        await db.commit()

        assert (await _product_stock(db, fx["preorder"])) == before
        rows = (
            await db.execute(
                text(
                    "SELECT change_amount, reason FROM public.inventory_logs "
                    "WHERE order_id = CAST(:oid AS uuid)"
                ),
                {"oid": order["order_id"]},
            )
        ).all()
        assert rows == []  # no purchase row — the unit never left the warehouse

    async def test_item_carries_the_preorder_flag(self, db, fx):
        order = await create_order(
            db,
            fx["user_id"],
            [{"product_id": fx["preorder"], "size": "M", "color": "x", "quantity": 1}],
            ADDRESS,
            None,
        )
        await db.commit()
        item = await _item(db, order["order_id"])
        assert item["is_preorder"] is True

    async def test_mixed_order_splits_behaviour_per_line(self, db, fx):
        normal_before = await _product_stock(db, fx["normal"])
        pre_before = await _product_stock(db, fx["preorder"])
        order = await create_order(
            db,
            fx["user_id"],
            [
                {"product_id": fx["normal"], "size": "M", "color": "x", "quantity": 2},
                {"product_id": fx["preorder"], "size": "M", "color": "x", "quantity": 1},
            ],
            ADDRESS,
            None,
        )
        await db.commit()
        # the normal line decremented; the preorder line did not
        assert (await _product_stock(db, fx["normal"])) == normal_before - 2
        assert (await _product_stock(db, fx["preorder"])) == pre_before
        rows = (
            await db.execute(
                text(
                    "SELECT i.product_id, i.is_preorder, l.change_amount, l.reason "
                    "FROM public.order_items i "
                    "LEFT JOIN public.inventory_logs l ON l.order_id = i.order_id "
                    "   AND l.product_id = i.product_id "
                    "WHERE i.order_id = CAST(:oid AS uuid) "
                    "ORDER BY i.is_preorder"
                ),
                {"oid": order["order_id"]},
            )
        ).all()
        # false sorts before true → normal row first, preorder row second
        normal_row, pre_row = rows[0], rows[1]
        assert pre_row.is_preorder is True and pre_row.change_amount is None
        assert normal_row.is_preorder is False and normal_row.change_amount == -2
        assert normal_row.reason == "purchase"

    async def test_checkout_notifies_preorder_variant_once(self, db, fx):
        """B2.1 hand-off: the preorder message type fires inside checkout, deduped."""
        order = await create_order(
            db,
            fx["user_id"],
            [{"product_id": fx["preorder"], "size": "M", "color": "x", "quantity": 1}],
            ADDRESS,
            None,
        )
        await db.commit()
        rows = (
            await db.execute(
                text(
                    "SELECT type FROM public.notifications "
                    "WHERE event_key = :key"
                ),
                {"key": f"order:{order['order_id']}:created_preorder"},
            )
        ).scalars().all()
        assert rows == ["order_created_preorder"]

    async def test_preorder_notification_is_idempotent(self, db, fx):
        """Replaying the same order event writes one notification (D2 dedup)."""
        order = await create_order(
            db,
            fx["user_id"],
            [{"product_id": fx["preorder"], "size": "M", "color": "x", "quantity": 1}],
            ADDRESS,
            None,
        )
        await db.commit()
        await notify_order_event(db, order["order_id"], "created_preorder")
        await db.commit()
        rows = (
            await db.execute(
                text("SELECT COUNT(*) FROM public.notifications WHERE event_key = :key"),
                {"key": f"order:{order['order_id']}:created_preorder"},
            )
        ).scalar()
        assert rows == 1


class TestPreorderCancellation:
    async def test_cancelling_a_preorder_restores_nothing(self, db, fx):
        before = await _product_stock(db, fx["preorder"])
        order = await create_order(
            db,
            fx["user_id"],
            [{"product_id": fx["preorder"], "size": "M", "color": "x", "quantity": 2}],
            ADDRESS,
            None,
        )
        await db.commit()
        await cancel_order_tx(db, order["order_id"], "pending")
        await db.commit()
        assert (await _product_stock(db, fx["preorder"])) == before
        rows = (
            await db.execute(
                text(
                    "SELECT reason FROM public.inventory_logs "
                    "WHERE order_id = CAST(:oid AS uuid)"
                ),
                {"oid": order["order_id"]},
            )
        ).scalars().all()
        assert rows == []  # no `return` row either — purchase and return net to zero

    async def test_mixed_order_cancellation_restores_only_the_normal_line(self, db, fx):
        normal_before = await _product_stock(db, fx["normal"])
        pre_before = await _product_stock(db, fx["preorder"])
        order = await create_order(
            db,
            fx["user_id"],
            [
                {"product_id": fx["normal"], "size": "M", "color": "x", "quantity": 2},
                {"product_id": fx["preorder"], "size": "M", "color": "x", "quantity": 3},
            ],
            ADDRESS,
            None,
        )
        await db.commit()
        await cancel_order_tx(db, order["order_id"], "pending")
        await db.commit()
        assert (await _product_stock(db, fx["normal"])) == normal_before
        assert (await _product_stock(db, fx["preorder"])) == pre_before
