"""The steady-state boot takes no table lock and cannot deadlock traffic (B6.16).

`startup_ddl()` used to run `ALTER TABLE … ADD COLUMN IF NOT EXISTS` (ACCESS EXCLUSIVE
even when the column exists) and `CREATE INDEX IF NOT EXISTS` (SHARE) on every boot, so
a restart under traffic blocked requests and could deadlock with them (reproduced:
`DeadlockDetectedError` → 500 on `GET /products`). Now each guarded statement is checked
against the catalog first, the DDL of concurrent processes is serialized, and a needed
migration waits at most `lock_timeout` for its lock.
"""

import asyncio

import pytest
from sqlalchemy import text

from app import db as dbmod
from app.db import SessionLocal, ddl_needed, engine, startup_ddl
from app.services.recommendations import co_purchase_ddl

_LISTS = (
    "ROLE_DDL", "COUPON_DDL", "CATALOG_DDL", "TRACKING_DDL", "REFUND_DDL", "AUDIT_DDL",
    "PAYMENT_DDL", "CONTACT_DDL", "NOTIFICATION_DDL", "PASSWORD_RESET_DDL",
)
_DDL_PREFIXES = ("CREATE TABLE", "CREATE INDEX", "CREATE UNIQUE INDEX", "ALTER TABLE", "ALTER TYPE")
# tables the guarded DDL touches — held with ROW EXCLUSIVE, which conflicts with both
# ACCESS EXCLUSIVE (ALTER TABLE) and SHARE (CREATE INDEX)
_HOT = ("products", "orders", "order_items", "payments", "coupons", "refund_requests", "users")


def _statements() -> list[str]:
    out = [" ".join(s.split()) for name in _LISTS for s in getattr(dbmod, name)]
    return out + [" ".join(co_purchase_ddl().split())]


def test_every_ddl_statement_is_guarded():
    unguarded = [
        s for s in _statements()
        if s.upper().startswith(_DDL_PREFIXES)
        and not any(p.match(s) for p, _ in dbmod._DDL_GUARDS)
    ]
    assert unguarded == []


async def _db_available() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture
async def live():
    await engine.dispose()
    if not await _db_available():
        pytest.skip("no database reachable — integration test skipped")
    await startup_ddl()
    yield
    await engine.dispose()


async def test_catalog_check_knows_what_exists(live):
    async with engine.connect() as conn:
        exists = [
            "ALTER TABLE public.products ADD COLUMN IF NOT EXISTS tags TEXT[]",
            "CREATE INDEX IF NOT EXISTS notifications_user_created_idx ON public.x(y)",
            "CREATE TABLE IF NOT EXISTS public.notifications (id int)",
            "ALTER TYPE public.app_role ADD VALUE IF NOT EXISTS 'super_admin'",
        ]
        missing = [
            "ALTER TABLE public.products ADD COLUMN IF NOT EXISTS b616_nope INTEGER",
            "CREATE INDEX IF NOT EXISTS b616_nope_idx ON public.products(id)",
            "CREATE TABLE IF NOT EXISTS public.b616_nope (id int)",
            "ALTER TYPE public.app_role ADD VALUE IF NOT EXISTS 'b616_nope'",
        ]
        assert [await ddl_needed(conn, s) for s in exists] == [False] * 4
        assert [await ddl_needed(conn, s) for s in missing] == [True] * 4
        # anything else (backfills, the settings-row insert) still runs
        assert await ddl_needed(conn, "UPDATE public.payments SET authority = NULL WHERE false")


async def test_steady_state_boot_does_not_wait_for_busy_tables(live):
    """A long transaction holding ROW EXCLUSIVE on every hot table must not stop a boot."""
    holder = await engine.connect()
    tx = await holder.begin()
    try:
        await holder.execute(
            text(f"LOCK TABLE {', '.join('public.' + t for t in _HOT)} IN ROW EXCLUSIVE MODE")
        )
        await asyncio.wait_for(startup_ddl(), timeout=15)
    finally:
        await tx.rollback()
        await holder.close()


async def test_concurrent_boots_and_traffic_do_not_deadlock(live):
    async def read_products() -> int:
        async with SessionLocal() as session:
            return (await session.execute(text("SELECT COUNT(*) FROM public.products"))).scalar()

    results = await asyncio.gather(
        startup_ddl(), startup_ddl(), startup_ddl(),
        *(read_products() for _ in range(6)),
        return_exceptions=True,
    )
    assert [r for r in results if isinstance(r, BaseException)] == []
