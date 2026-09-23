"""`GET /admin/audit-logs` filters (B5.1c).

A malformed `admin_id` used to reach `CAST(:admin_id AS uuid)` and fail in Postgres
(500); it is now typed, so FastAPI answers 422. A valid id still filters, and the other
filters and the response shape are unchanged. Live-DB tests (skip without a DB); the
audit rows they write stay (append-only, B5.1b).
"""

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text

from app.db import SessionLocal, engine, startup_ddl
from app.main import app
from app.security import create_access_token
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
async def admin(db):
    email = f"b51c-{uuid4().hex[:8]}@test.local"
    uid = (
        await db.execute(
            text("INSERT INTO public.users (email, password_hash) VALUES (:e, 'x') RETURNING id"),
            {"e": email},
        )
    ).scalar()
    await db.execute(
        text("INSERT INTO public.user_roles (user_id, role) VALUES (:u, 'admin')"), {"u": str(uid)}
    )
    marker = f"b51c-{uuid4().hex[:8]}"
    await record_audit(
        db, admin_id=uid, action="update_coupon", entity_type="coupon", entity_id=marker,
        old_values={"active": True}, new_values={"active": False},
    )
    await db.commit()
    yield {"id": str(uid), "token": create_access_token(uid, email, "customer"), "marker": marker}
    await db.execute(text("DELETE FROM public.users WHERE id = :u"), {"u": str(uid)})
    await db.commit()


async def _get(token: str, **params) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        return await client.get(
            "/admin/audit-logs", params=params, headers={"Authorization": f"Bearer {token}"}
        )


@pytest.mark.parametrize("bad", ["foo", "123", "not-a-uuid-at-all"])
async def test_a_malformed_admin_id_is_422_not_500(admin, bad):
    assert (await _get(admin["token"], admin_id=bad)).status_code == 422


async def test_a_valid_admin_id_filters(admin):
    res = await _get(admin["token"], admin_id=admin["id"])
    assert res.status_code == 200
    rows = res.json()
    assert rows and all(r["admin_id"] == admin["id"] for r in rows)
    assert any(r["entity_id"] == admin["marker"] for r in rows)


async def test_an_unknown_admin_id_is_an_empty_list(admin):
    res = await _get(admin["token"], admin_id=str(uuid4()))
    assert res.status_code == 200 and res.json() == []


async def test_the_other_filters_are_unchanged(admin):
    res = await _get(admin["token"], entity_id=admin["marker"], action="update_coupon")
    assert res.status_code == 200
    [row] = res.json()
    assert set(row) >= {"id", "admin_id", "admin_email", "action", "entity_type", "entity_id",
                        "old_values", "new_values", "created_at"}
    assert row["new_values"] == {"active": False}
