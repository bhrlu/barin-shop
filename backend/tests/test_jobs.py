"""Background jobs (B2.5): the worker's passes, their locks, retries and idempotency.

* `remind_unpaid_orders` — one «یادآوری پرداخت» per order still pending + unpaid after
  the delay (and not older than the max age); running it again, or twice at once, adds
  nothing (the duplicate-event case);
* `sweep_deliveries` — the outbox: a `pending` row a crash left behind is sent, a fresh
  one is left to its after-commit sender, `failed` rows are retried after
  attempts × backoff up to the cap, `sent` rows are never touched;
* a job whose advisory lock another worker holds is skipped; one failing job does not
  stop the others; `python -m app.worker --once` runs a pass and exits.

Providers are faked; nothing leaves the machine. Live-DB tests (skip without a DB).
"""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import text

from app import worker
from app.db import SessionLocal, engine, startup_ddl
from app.services import jobs
from app.services import notifications as notif
from app.services.notification_providers import ProviderError


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
    await notif.drain()
    await engine.dispose()


@pytest.fixture
async def customer(db):
    uid = (
        await db.execute(
            text("INSERT INTO public.users (email, password_hash) VALUES (:e, 'x') RETURNING id"),
            {"e": f"b25-{uuid4().hex[:8]}@test.local"},
        )
    ).scalar()
    await db.commit()
    yield uid
    await db.execute(text("DELETE FROM public.users WHERE id = :u"), {"u": str(uid)})
    await db.commit()


async def _order(db, user_id, *, minutes_ago: int, status="pending", payment="unpaid") -> str:
    oid = (
        await db.execute(
            text(
                "INSERT INTO public.orders (user_id, status, payment_status, payment_method, "
                " subtotal, discount, shipping, total, shipping_address, created_at) "
                "VALUES (:u, :s, :p, 'online', 250000, 0, 89000, 339000, "
                "        '{\"phone\": \"09120000000\"}', now() - make_interval(mins => :m)) "
                "RETURNING id"
            ),
            {"u": str(user_id), "s": status, "p": payment, "m": minutes_ago},
        )
    ).scalar()
    await db.commit()
    return str(oid)


async def _reminders(db, user_id) -> list[dict]:
    await db.commit()
    return [
        dict(r)
        for r in (
            await db.execute(
                text(
                    "SELECT event_key, data, title, message FROM public.notifications "
                    "WHERE user_id = :u AND type = 'payment_reminder'"
                ),
                {"u": str(user_id)},
            )
        ).mappings().all()
    ]


async def test_a_due_unpaid_order_gets_one_reminder(db, customer):
    oid = await _order(db, customer, minutes_ago=120)
    assert await jobs.run_job("remind_unpaid_orders") >= 1
    rows = await _reminders(db, customer)
    assert len(rows) == 1
    assert rows[0]["event_key"] == f"order:{oid}:payment_reminder"
    assert rows[0]["data"]["order_id"] == oid
    assert rows[0]["title"] == "یادآوری پرداخت سفارش"
    assert "هنوز پرداخت نشده است" in rows[0]["message"]


@pytest.mark.parametrize(
    ("minutes_ago", "status", "payment"),
    [
        (10, "pending", "unpaid"),  # too young
        (60 * 24 * 4, "pending", "unpaid"),  # older than the 72 h window
        (120, "pending", "paid"),
        (120, "cancelled", "unpaid"),
        (120, "processing", "paid"),
    ],
)
async def test_orders_that_are_not_due_get_nothing(db, customer, minutes_ago, status, payment):
    await _order(db, customer, minutes_ago=minutes_ago, status=status, payment=payment)
    await jobs.run_job("remind_unpaid_orders")
    assert await _reminders(db, customer) == []


async def test_running_again_or_concurrently_adds_no_duplicate(db, customer):
    await _order(db, customer, minutes_ago=120)
    await jobs.run_job("remind_unpaid_orders")
    await jobs.run_job("remind_unpaid_orders")  # a restarted worker's next pass
    await asyncio.gather(*(jobs.run_job("remind_unpaid_orders") for _ in range(3)))
    assert len(await _reminders(db, customer)) == 1


async def test_a_job_held_by_another_worker_is_skipped(db, customer):
    await _order(db, customer, minutes_ago=120)
    holder = await engine.connect()
    tx = await holder.begin()
    try:
        await holder.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended('job:remind_unpaid_orders', 0))")
        )
        assert await jobs.run_job("remind_unpaid_orders") is None
        assert await _reminders(db, customer) == []
    finally:
        await tx.rollback()
        await holder.close()
    assert await jobs.run_job("remind_unpaid_orders") >= 1  # free again: it runs


class _FakeProvider:
    name = "fake"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[tuple] = []

    def configured(self) -> bool:
        return True

    async def send(self, *args) -> None:
        if self.fail:
            raise ProviderError("provider down")
        self.sent.append(args)


@pytest.fixture
def providers(monkeypatch):
    fake = _FakeProvider()
    monkeypatch.setattr(notif.providers, "sms_provider", lambda: fake)
    monkeypatch.setattr(notif.providers, "email_provider", lambda: fake)

    async def switches_on(_session):
        return {"sms": True, "email": True}

    monkeypatch.setattr(notif, "load_switches", switches_on)
    return fake


async def _delivery(db, user_id, *, status: str, attempts: int, minutes_ago: int) -> str:
    nid = (
        await db.execute(
            text(
                "INSERT INTO public.notifications (user_id, type, title, message, event_key) "
                "VALUES (:u, 'order_created', 'عنوان', 'پیام', :k) RETURNING id"
            ),
            {"u": str(user_id), "k": f"b25:{uuid4().hex}"},
        )
    ).scalar()
    did = (
        await db.execute(
            text(
                "INSERT INTO public.notification_deliveries "
                "(notification_id, channel, recipient, status, attempts, created_at, updated_at) "
                "VALUES (:n, 'sms', '09120000000', :s, :a, "
                "        now() - make_interval(mins => :m), now() - make_interval(mins => :m)) "
                "RETURNING id"
            ),
            {"n": str(nid), "s": status, "a": attempts, "m": minutes_ago},
        )
    ).scalar()
    await db.commit()
    return str(did)


async def _state(db, did: str) -> tuple[str, int]:
    await db.commit()
    row = (
        await db.execute(
            text("SELECT status, attempts FROM public.notification_deliveries WHERE id = :d"),
            {"d": did},
        )
    ).first()
    return row[0], row[1]


async def test_the_sweeper_sends_what_a_crash_left_pending(db, customer, providers):
    stale = await _delivery(db, customer, status="pending", attempts=0, minutes_ago=10)
    fresh = await _delivery(db, customer, status="pending", attempts=0, minutes_ago=0)
    sent = await _delivery(db, customer, status="sent", attempts=1, minutes_ago=10)
    await jobs.run_job("sweep_deliveries")
    assert await _state(db, stale) == ("sent", 1)
    assert await _state(db, fresh) == ("pending", 0)  # its after-commit sender owns it
    assert await _state(db, sent) == ("sent", 1)
    assert len(providers.sent) == 1


async def test_failed_deliveries_retry_with_backoff_up_to_the_cap(db, customer, providers):
    providers.fail = True
    due = await _delivery(db, customer, status="failed", attempts=1, minutes_ago=10)
    backing_off = await _delivery(db, customer, status="failed", attempts=4, minutes_ago=5)
    capped = await _delivery(db, customer, status="failed", attempts=5, minutes_ago=60)
    await jobs.run_job("sweep_deliveries")
    assert await _state(db, due) == ("failed", 2)  # tried again, failed again
    assert await _state(db, backing_off) == ("failed", 4)  # 4 × 2 min not yet passed
    assert await _state(db, capped) == ("failed", 5)  # never again
    providers.fail = False
    await db.execute(  # the backoff has passed
        text("UPDATE public.notification_deliveries SET updated_at = now() - interval '1 hour' "
             "WHERE id = :d"),
        {"d": due},
    )
    await db.commit()
    await jobs.run_job("sweep_deliveries")
    assert await _state(db, due) == ("sent", 3)


async def test_one_failing_job_does_not_stop_the_others(db, monkeypatch):
    ran = []

    async def broken(_session):
        raise RuntimeError("boom")

    async def healthy(_session):
        ran.append(True)
        return 0

    monkeypatch.setattr(jobs, "JOBS", {"broken": broken, "healthy": healthy})
    assert await jobs.run_all() == {"broken": None, "healthy": 0}
    assert ran == [True]


async def test_the_worker_runs_a_pass_and_exits(db, customer):
    await _order(db, customer, minutes_ago=120)
    await asyncio.wait_for(worker.main(once=True), timeout=30)
    assert len(await _reminders(db, customer)) == 1
