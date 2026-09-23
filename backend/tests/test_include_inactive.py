"""`GET /products?include_inactive=true` follows the `catalog` capability (B5.4b).

It used to follow `AuthUser.is_admin` (admin/super_admin only), so an
order_manager — who may edit products — never saw inactive ones and could not
re-activate them. Anonymous callers, customers and support must still get active
rows only. Live-DB tests; they skip when no database is reachable.
"""

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text

from app.db import SessionLocal, engine, startup_ddl
from app.main import app
from app.security import create_access_token


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
async def world(db):
    """One active and one inactive product under a unique tag, plus one user per role."""
    tag = f"b54b-{uuid4().hex[:8]}"
    for pid, active in ((f"{tag}-on", True), (f"{tag}-off", False)):
        await db.execute(
            text(
                "INSERT INTO public.products (id, name, category, price, stock, active, tags) "
                "VALUES (:pid, 'B5.4b test', 'test', 1000, 1, :a, ARRAY[:tag])"
            ),
            {"pid": pid, "a": active, "tag": tag},
        )
    tokens: dict[str, str | None] = {"anonymous": None}
    ids = []
    for role in ("customer", "support", "order_manager", "admin", "super_admin"):
        email = f"b54b-{role}-{uuid4().hex[:6]}@test.local"
        uid = (
            await db.execute(
                text(
                    "INSERT INTO public.users (email, password_hash) "
                    "VALUES (:e, 'x') RETURNING id"
                ),
                {"e": email},
            )
        ).scalar()
        ids.append(str(uid))
        if role != "customer":
            await db.execute(
                text("INSERT INTO public.user_roles (user_id, role) VALUES (:u, :r)"),
                {"u": str(uid), "r": role},
            )
        tokens[role] = create_access_token(uid, email, "customer")
    await db.commit()
    try:
        yield tag, tokens
    finally:
        await db.execute(
            text("DELETE FROM public.users WHERE id = ANY(CAST(:ids AS uuid[]))"), {"ids": ids}
        )
        await db.execute(text("DELETE FROM public.products WHERE :t = ANY(tags)"), {"t": tag})
        await db.commit()


async def _ids(tag: str, token: str | None, **extra) -> set[str]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        res = await client.get(
            "/products", params={"tag": tag, "include_inactive": "true", **extra}, headers=headers
        )
    assert res.status_code == 200, res.text
    body = res.json()
    items = body["items"] if isinstance(body, dict) else body
    return {p["id"] for p in items}


@pytest.mark.parametrize("who", ["anonymous", "customer", "support"])
async def test_without_catalog_capability_only_active_rows(db, world, who):
    tag, tokens = world
    assert await _ids(tag, tokens[who]) == {f"{tag}-on"}


@pytest.mark.parametrize("who", ["order_manager", "admin", "super_admin"])
async def test_catalog_capability_sees_inactive_rows(db, world, who):
    tag, tokens = world
    assert await _ids(tag, tokens[who]) == {f"{tag}-on", f"{tag}-off"}
    # the paginated envelope used by /admin/products agrees
    assert await _ids(tag, tokens[who], page=1, page_size=20) == {f"{tag}-on", f"{tag}-off"}


async def test_the_flag_is_still_opt_in(db, world):
    tag, tokens = world
    headers = {"Authorization": f"Bearer {tokens['order_manager']}"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        res = await client.get("/products", params={"tag": tag}, headers=headers)
    assert {p["id"] for p in res.json()} == {f"{tag}-on"}
