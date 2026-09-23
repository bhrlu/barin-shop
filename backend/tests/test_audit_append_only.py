"""`audit_logs` is append-only at the database level (B5.1b).

When the table was created the app's DB role owned it (and was a superuser in the
compose stack), so REVOKE could not enforce anything; triggers refuse UPDATE, DELETE
and TRUNCATE. Since B5.1e the app connects with a DML-only role that owns nothing and
cannot disable or drop those triggers — TRUNCATE is refused by the missing privilege
before the trigger is even reached. The one change allowed is the FK's
`ON DELETE SET NULL` when a user is deleted — `admin_id` becomes NULL and nothing else
may move. Rows written here stay (that is the point).
"""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db import SessionLocal, engine, startup_ddl
from app.services.audit import record_audit


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
async def entry(db):
    """A fresh user and one audit row written by them through `record_audit`."""
    uid = (
        await db.execute(
            text("INSERT INTO public.users (email, password_hash) VALUES (:e, 'x') RETURNING id"),
            {"e": f"b51b-{uuid4().hex[:8]}@test.local"},
        )
    ).scalar()
    marker = f"b51b-{uuid4().hex[:10]}"
    await record_audit(
        db, admin_id=uid, action="cancel_order", entity_type="order", entity_id=marker,
        old_values={"status": "pending"}, new_values={"status": "cancelled"},
    )
    await db.commit()
    yield {"uid": uid, "marker": marker}
    await db.rollback()
    await db.execute(text("DELETE FROM public.users WHERE id = :u"), {"u": str(uid)})
    await db.commit()


async def _row(db, marker: str) -> dict | None:
    await db.commit()
    row = (
        await db.execute(
            text("SELECT * FROM public.audit_logs WHERE entity_id = :m"), {"m": marker}
        )
    ).mappings().first()
    return dict(row) if row else None


async def _refused(db, sql: str, **params) -> str:
    with pytest.raises(DBAPIError) as exc:
        await db.execute(text(sql), params)
    await db.rollback()
    return str(exc.value)


async def test_insert_still_works(db, entry):
    row = await _row(db, entry["marker"])
    assert row is not None and row["admin_id"] == entry["uid"]
    assert row["new_values"] == {"status": "cancelled"}


async def test_update_is_refused(db, entry):
    msg = await _refused(
        db, "UPDATE public.audit_logs SET action = 'tampered' WHERE entity_id = :m",
        m=entry["marker"],
    )
    assert "append-only" in msg
    assert (await _row(db, entry["marker"]))["action"] == "cancel_order"


async def test_delete_is_refused(db, entry):
    msg = await _refused(
        db, "DELETE FROM public.audit_logs WHERE entity_id = :m", m=entry["marker"]
    )
    assert "append-only" in msg
    assert await _row(db, entry["marker"]) is not None


async def test_truncate_is_refused(db, entry):
    msg = await _refused(db, "TRUNCATE public.audit_logs")
    # B5.1e: the app role has no TRUNCATE privilege at all, so the ACL refuses
    # before the trigger is reached; a superuser would see the trigger's message
    assert "append-only" in msg or "permission denied" in msg
    assert await _row(db, entry["marker"]) is not None


async def test_reattributing_a_row_is_refused(db, entry):
    other = (
        await db.execute(
            text("INSERT INTO public.users (email, password_hash) VALUES (:e, 'x') RETURNING id"),
            {"e": f"b51b-other-{uuid4().hex[:8]}@test.local"},
        )
    ).scalar()
    await db.commit()
    try:
        await _refused(
            db, "UPDATE public.audit_logs SET admin_id = :o WHERE entity_id = :m",
            o=str(other), m=entry["marker"],
        )
        # nulling admin_id while also editing the row is not the FK cascade either
        await _refused(
            db,
            "UPDATE public.audit_logs SET admin_id = NULL, new_values = '{}' "
            "WHERE entity_id = :m",
            m=entry["marker"],
        )
        assert (await _row(db, entry["marker"]))["admin_id"] == entry["uid"]
    finally:
        await db.execute(text("DELETE FROM public.users WHERE id = :u"), {"u": str(other)})
        await db.commit()


async def test_deleting_the_user_only_nulls_the_attribution(db, entry):
    before = await _row(db, entry["marker"])
    await db.execute(text("DELETE FROM public.users WHERE id = :u"), {"u": str(entry["uid"])})
    await db.commit()
    after = await _row(db, entry["marker"])
    assert after["admin_id"] is None
    assert {k: v for k, v in after.items() if k != "admin_id"} == {
        k: v for k, v in before.items() if k != "admin_id"
    }
