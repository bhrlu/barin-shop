"""A password reset ends every session issued before it (B6.14).

Tokens are stateless 7-day JWTs; `users.password_changed_at` (stamped by a reset)
is the cutoff `app/auth.py` checks against the token's `iat`. Old tokens are
crafted with an `iat` in the past so the tests never depend on wall-clock seconds.
Live-DB tests; they skip when no database is reachable.
"""

import hashlib
import secrets
import time
from uuid import uuid4

import httpx
import pytest
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from sqlalchemy import text

from app.auth import get_optional_user
from app.config import settings
from app.db import SessionLocal, engine, startup_ddl
from app.main import app
from app.security import hash_password
from app.services import notifications

OLD, NEW = "old-secret-1", "new-secret-2"


def _token(user_id, email: str, *, iat: int | None, role: str = "customer") -> str:
    """Same claims as `create_access_token`, with a chosen (or missing) `iat`."""
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": now + 3600,
        "aud": "authenticated",
        "iss": "sandeh-backend",
    }
    if iat is not None:
        payload["iat"] = iat
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


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
async def make_user(db):
    ids: list = []

    async def _make(role: str | None = None) -> dict:
        email = f"b614-{uuid4().hex[:8]}@test.local"
        uid = (
            await db.execute(
                text(
                    "INSERT INTO public.users (email, password_hash) "
                    "VALUES (:e, :h) RETURNING id"
                ),
                {"e": email, "h": hash_password(OLD)},
            )
        ).scalar()
        await db.execute(text("INSERT INTO public.profiles (id) VALUES (:u)"), {"u": str(uid)})
        if role:
            await db.execute(
                text("INSERT INTO public.user_roles (user_id, role) VALUES (:u, :r)"),
                {"u": str(uid), "r": role},
            )
        await db.commit()
        ids.append(str(uid))
        return {"id": uid, "email": email}

    yield _make
    await db.execute(
        text("DELETE FROM public.users WHERE id = ANY(CAST(:ids AS uuid[]))"), {"ids": ids}
    )
    await db.commit()


async def _call(method: str, path: str, token: str | None = None, **kw) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        return await client.request(method, path, headers=headers, **kw)


async def _reset(db, user: dict, password: str = NEW) -> None:
    """Reset through the real endpoint with a fixture link (hash-only, like the app)."""
    raw = secrets.token_urlsafe(32)
    await db.execute(
        text(
            "INSERT INTO public.password_reset_tokens (user_id, token_hash, expires_at) "
            "VALUES (:u, :h, now() + interval '30 minutes')"
        ),
        {"u": str(user["id"]), "h": hashlib.sha256(raw.encode()).hexdigest()},
    )
    await db.commit()
    res = await _call("POST", "/auth/password/reset", json={"token": raw, "password": password})
    assert res.status_code == 200, res.text


def _an_hour_ago() -> int:
    return int(time.time()) - 3600


async def test_reset_ends_sessions_issued_before_it(db, make_user):
    user = await make_user()
    old = _token(user["id"], user["email"], iat=_an_hour_ago())
    assert (await _call("GET", "/auth/me", old)).status_code == 200

    await _reset(db, user)
    me = await _call("GET", "/auth/me", old)
    assert me.status_code == 401
    assert "دوباره وارد شوید" in me.json()["detail"]
    assert (await _call("GET", "/orders", old)).status_code == 401
    assert (await _call("GET", "/notifications", old)).status_code == 401


async def test_login_right_after_the_reset_works(db, make_user):
    user = await make_user()
    await _reset(db, user)
    login = await _call("POST", "/auth/login", json={"email": user["email"], "password": NEW})
    assert login.status_code == 200
    # issued in the same second as the reset: must not be caught by the cutoff
    assert (await _call("GET", "/auth/me", login.json()["access_token"])).status_code == 200


async def test_users_who_never_reset_keep_their_sessions(db, make_user):
    user = await make_user()
    six_days_old = _token(user["id"], user["email"], iat=int(time.time()) - 6 * 86400)
    assert (await _call("GET", "/auth/me", six_days_old)).status_code == 200


async def test_a_token_without_iat_cannot_outlive_a_reset(db, make_user):
    user = await make_user()
    no_iat = _token(user["id"], user["email"], iat=None)
    assert (await _call("GET", "/auth/me", no_iat)).status_code == 200  # no cutoff yet
    await _reset(db, user)
    assert (await _call("GET", "/auth/me", no_iat)).status_code == 401


async def test_ended_session_is_anonymous_where_auth_is_optional(db, make_user):
    user = await make_user()
    old = _token(user["id"], user["email"], iat=_an_hour_ago())
    await _reset(db, user)
    # optional-auth endpoints keep working, as for a guest
    assert (await _call("GET", "/products", old)).status_code == 200
    async with SessionLocal() as session:
        stale = HTTPAuthorizationCredentials(scheme="Bearer", credentials=old)
        assert await get_optional_user(stale, session) is None
        fresh = (
            await _call("POST", "/auth/login", json={"email": user["email"], "password": NEW})
        ).json()["access_token"]
        current = await get_optional_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=fresh), session
        )
        assert current is not None and current.id == user["id"]


async def test_staff_sessions_end_too(db, make_user):
    staff = await make_user(role="order_manager")
    old = _token(staff["id"], staff["email"], iat=_an_hour_ago())
    assert (await _call("GET", "/admin/orders", old)).status_code == 200
    await _reset(db, staff)
    assert (await _call("GET", "/admin/orders", old)).status_code == 401
