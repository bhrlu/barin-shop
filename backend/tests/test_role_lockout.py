"""Role changes can never lock the store out of role management (B5.4a).

`PUT /admin/users/{id}/roles` used to accept a caller removing their own
users-capable role and the removal of the last such holder. The decision is the
pure `role_lockout_reason`; the endpoint runs it under an advisory lock so two
admins demoting each other at once cannot both pass. The dev database always keeps
the seeded legacy `admin`, so "no holder left" is pinned by the pure tests; the HTTP
tests cover self-demotion and the allowed changes against the live database.
"""

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text

from app.db import SessionLocal, engine, startup_ddl
from app.main import app
from app.security import create_access_token
from app.services.roles import role_lockout_reason

SELF_MSG = "نمی‌توانید دسترسی مدیریت کاربران را از حساب خودتان بردارید"
LAST_MSG = "دست‌کم یک حساب باید دسترسی مدیریت کاربران را نگه دارد"


class TestDecision:
    def test_self_losing_users_capability_is_refused(self):
        assert role_lockout_reason(
            is_self=True, target_roles_after={"support"}, other_users_holders=5
        ) == SELF_MSG

    def test_self_keeping_it_is_fine(self):
        assert role_lockout_reason(
            is_self=True, target_roles_after={"super_admin", "support"}, other_users_holders=0
        ) is None
        # a legacy `admin` row keeps the capability even without super_admin
        assert role_lockout_reason(
            is_self=True, target_roles_after={"admin"}, other_users_holders=0
        ) is None

    def test_removing_the_last_holder_is_refused(self):
        assert role_lockout_reason(
            is_self=False, target_roles_after={"order_manager"}, other_users_holders=0
        ) == LAST_MSG

    def test_removing_one_of_several_holders_is_fine(self):
        assert role_lockout_reason(
            is_self=False, target_roles_after=set(), other_users_holders=1
        ) is None


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
async def make(db):
    ids: list[str] = []

    async def _make(*roles: str) -> dict:
        email = f"b54a-{uuid4().hex[:8]}@test.local"
        uid = (
            await db.execute(
                text(
                    "INSERT INTO public.users (email, password_hash) "
                    "VALUES (:e, 'x') RETURNING id"
                ),
                {"e": email},
            )
        ).scalar()
        for role in roles:
            await db.execute(
                text("INSERT INTO public.user_roles (user_id, role) VALUES (:u, :r)"),
                {"u": str(uid), "r": role},
            )
        await db.commit()
        ids.append(str(uid))
        return {"id": str(uid), "token": create_access_token(uid, email, "customer")}

    yield _make
    # # audit_logs is append-only (B5.1b): deleting the users only nulls admin_id
    await db.execute(
        text("DELETE FROM public.users WHERE id = ANY(CAST(:ids AS uuid[]))"), {"ids": ids}
    )
    await db.commit()


async def _put(token: str, target: str, roles: list[str]) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        return await client.put(
            f"/admin/users/{target}/roles",
            headers={"Authorization": f"Bearer {token}"},
            json={"roles": roles},
        )


async def _roles(db, uid: str) -> set[str]:
    await db.commit()
    rows = await db.execute(
        text("SELECT role::text FROM public.user_roles WHERE user_id = CAST(:u AS uuid)"),
        {"u": uid},
    )
    return {r[0] for r in rows.all()}


async def test_super_admin_cannot_demote_themselves(db, make):
    me = await make("super_admin")
    res = await _put(me["token"], me["id"], [])
    assert res.status_code == 409 and res.json()["detail"] == SELF_MSG
    assert await _roles(db, me["id"]) == {"super_admin"}
    res = await _put(me["token"], me["id"], ["support"])
    assert res.status_code == 409
    assert await _roles(db, me["id"]) == {"super_admin"}


async def test_self_change_that_keeps_the_capability_is_allowed(db, make):
    me = await make("super_admin")
    res = await _put(me["token"], me["id"], ["super_admin", "support"])
    assert res.status_code == 200
    assert await _roles(db, me["id"]) == {"super_admin", "support"}


async def test_legacy_admin_may_drop_their_super_admin(db, make):
    me = await make("admin", "super_admin")
    res = await _put(me["token"], me["id"], [])
    assert res.status_code == 200  # the legacy `admin` row keeps role management
    assert await _roles(db, me["id"]) == {"admin"}


async def test_demoting_another_holder_is_allowed(db, make):
    me = await make("super_admin")
    other = await make("super_admin")
    res = await _put(me["token"], other["id"], ["order_manager"])
    assert res.status_code == 200
    assert await _roles(db, other["id"]) == {"order_manager"}


async def test_a_demoted_caller_is_refused(db, make):
    me = await make("super_admin")
    other = await make("super_admin")
    assert (await _put(me["token"], other["id"], [])).status_code == 200
    # `other` still holds a token issued while they were super_admin
    res = await _put(other["token"], me["id"], [])
    assert res.status_code == 403
    assert await _roles(db, me["id"]) == {"super_admin"}
