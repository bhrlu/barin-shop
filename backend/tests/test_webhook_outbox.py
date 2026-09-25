"""Integration tests for outbound order webhooks (B2.5a, decision D11).

These run against a live Postgres (the local docker-compose stack) because the
invariants under test — outbox rows written on the caller's transaction, the
`(event, order_id)` dedup, and the delivery UPDATE path — only exist in SQL.
When no database is reachable the module skips instead of failing, like the
other DB-backed modules.

D11 rules exercised here:
* an unconfigured store writes **no** outbox row (webhooks off = no trail);
* a configured store writes one row per lifecycle event at the business point
  (`cancel_order_tx` used as the representative path);
* a replayed event is a no-op (`UNIQUE (event, order_id)`);
* unknown event names are refused (closed set);
* `redeliver` re-queues only `failed` rows (a `sent` row answers empty);
* the sweeper's eligibility SQL matches the backoff policy.

Every test creates its own throwaway user/order and removes them in the
fixture teardown, so the running store's data is never touched.
"""

import json
import os
from uuid import uuid4

os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import SessionLocal, startup_ddl  # noqa: E402
from app.services.order_lifecycle import cancel_order_tx  # noqa: E402
from app.services.webhooks import enqueue_order_event, redeliver, sweep_webhooks  # noqa: E402
from tests.test_order_lifecycle_stock import ADDRESS  # noqa: E402


@pytest.fixture
async def db():
    from app.db import engine

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


async def _mk_order(db, status: str = "pending", payment_status: str = "unpaid") -> dict:
    """One throwaway user + order (a stored checkout row is not needed)."""
    email = f"b25a-{uuid4().hex[:8]}@test.local"
    user_id = (
        await db.execute(
            text(
                "INSERT INTO public.users (email, password_hash) VALUES (:email, 'x') "
                "RETURNING id"
            ),
            {"email": email},
        )
    ).scalar()
    order_id = (
        await db.execute(
            text(
                "INSERT INTO public.orders (order_number, user_id, status, payment_status, "
                "payment_method, subtotal, discount, shipping, total, shipping_address) "
                "VALUES (:onum, CAST(:uid AS uuid), :status, :pstatus, 'online', 100000, 0, "
                "        89000, 189000, CAST(:addr AS jsonb)) RETURNING id"
            ),
            {
                "onum": f"SND-T{uuid4().hex[:8].upper()}",
                "uid": str(user_id),
                "status": status,
                "pstatus": payment_status,
                "addr": json.dumps(ADDRESS, ensure_ascii=False),
            },
        )
    ).scalar()
    return {"user_id": user_id, "order_id": order_id, "email": email}


async def _rows(db, order_id, event: str | None = None):
    sql = "SELECT id, event, order_id, status, attempts FROM public.webhook_deliveries "
    params: dict = {"oid": str(order_id)}
    if event:
        sql += "WHERE order_id = CAST(:oid AS uuid) AND event = :event"
        params["event"] = event
    return (await db.execute(text(sql), params)).mappings().all()


@pytest.fixture
def webhooks_on(monkeypatch):
    monkeypatch.setattr(settings, "webhook_order_url", "https://consumer.test/hook")
    monkeypatch.setattr(settings, "webhook_hmac_secret", "s3cret")
    return True


@pytest.fixture
def webhooks_off(monkeypatch):
    monkeypatch.setattr(settings, "webhook_order_url", "")
    monkeypatch.setattr(settings, "webhook_hmac_secret", "")
    return False


async def _cleanup(db, user_id):
    await db.execute(
        text("DELETE FROM public.users WHERE id = :uid"), {"uid": str(user_id)}
    )
    await db.commit()


async def test_unconfigured_store_writes_no_row(db, webhooks_off):
    world = await _mk_order(db)
    try:
        await enqueue_order_event(db, world["order_id"], "paid")
        assert await _rows(db, world["order_id"]) == []
    finally:
        await _cleanup(db, world["user_id"])


async def test_cancel_lifecycle_enqueues_one_row(db, webhooks_on):
    world = await _mk_order(db)
    try:
        await cancel_order_tx(db, str(world["order_id"]), "pending")
        rows = await _rows(db, world["order_id"], "order.cancelled")
        assert len(rows) == 1
        assert rows[0]["status"] == "pending"  # dispatch happens after commit
        assert rows[0]["attempts"] == 0
    finally:
        await _cleanup(db, world["user_id"])


async def test_replayed_event_is_a_noop(db, webhooks_on):
    world = await _mk_order(db)
    try:
        await enqueue_order_event(db, world["order_id"], "paid")
        await enqueue_order_event(db, world["order_id"], "paid")  # same (event, order)
        rows = await _rows(db, world["order_id"], "order.paid")
        assert len(rows) == 1
    finally:
        await _cleanup(db, world["user_id"])


async def test_unknown_event_name_is_refused(db, webhooks_on):
    world = await _mk_order(db)
    try:
        await enqueue_order_event(db, world["order_id"], "order.exploded")
        assert await _rows(db, world["order_id"]) == []
    finally:
        await _cleanup(db, world["user_id"])


async def test_redeliver_only_requeues_failed(db, webhooks_on):
    world = await _mk_order(db)
    try:
        await enqueue_order_event(db, world["order_id"], "shipped")
        row = (await _rows(db, world["order_id"], "order.shipped"))[0]
        # a pending row is not redeliverable — the consumer has not been answered
        assert await redeliver(db, row["id"]) == {}
        await db.execute(
            text(
                "UPDATE public.webhook_deliveries SET status = 'failed', "
                "last_error = 'HTTP 500' WHERE id = CAST(:id AS uuid)"
            ),
            {"id": str(row["id"])},
        )
        await db.commit()
        result = await redeliver(db, row["id"])
        assert result["event"] == "order.shipped"
        rows = await _rows(db, world["order_id"], "order.shipped")
        assert rows[0]["status"] == "pending"
        assert rows[0]["attempts"] == 0  # attempts reset happens on the next attempt
    finally:
        await _cleanup(db, world["user_id"])


async def test_sweeper_picks_pending_and_failed_backoff(db, webhooks_on, monkeypatch):
    world = await _mk_order(db)
    try:
        await enqueue_order_event(db, world["order_id"], "paid")
        row = (await _rows(db, world["order_id"], "order.paid"))[0]
        # a fresh pending row inside the stale window is NOT picked
        picked = await sweep_webhooks(db)
        assert picked == 0
        # a failed row inside its backoff window is NOT picked either…
        await db.execute(
            text(
                "UPDATE public.webhook_deliveries SET status = 'failed', attempts = 2 "
                "WHERE id = CAST(:id AS uuid)"
            ),
            {"id": str(row["id"])},
        )
        await db.commit()
        picked = await sweep_webhooks(db)
        assert picked == 0
        # …but becomes eligible once the backoff window has passed
        await db.execute(
            text(
                "UPDATE public.webhook_deliveries SET updated_at = "
                "now() - make_interval(secs => 60 * 2 + 1) WHERE id = CAST(:id AS uuid)"
            ),
            {"id": str(row["id"])},
        )
        await db.commit()
        picked = await sweep_webhooks(db)
        assert picked == 1
    finally:
        await _cleanup(db, world["user_id"])


async def test_outbox_row_cascades_with_its_order(db, webhooks_on):
    world = await _mk_order(db)
    try:
        await enqueue_order_event(db, world["order_id"], "created")
        assert len(await _rows(db, world["order_id"])) == 1
    finally:
        # deleting the user cascades the order, the outbox row, and the trail
        await _cleanup(db, world["user_id"])
        assert await _rows(db, world["order_id"]) == []
