"""`GET /products/facets` — the `/shop` filter options without the whole catalogue (F5.8).

`/shop` used to download every product (and sign every image) only to list the sizes,
colours, tags and price range of its filters. The endpoint returns exactly what the
page derived: values of **active** products, first-seen over the newest-first list,
colours deduped by name. Live-DB tests; they skip when no database is reachable.
"""

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text

from app.db import SessionLocal, engine, startup_ddl
from app.main import app
from app.routers.products import product_facets
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
async def admin(db):
    email = f"f58-{uuid4().hex[:8]}@test.local"
    uid = (
        await db.execute(
            text("INSERT INTO public.users (email, password_hash) VALUES (:e, 'x') RETURNING id"),
            {"e": email},
        )
    ).scalar()
    await db.execute(
        text("INSERT INTO public.user_roles (user_id, role) VALUES (:u, 'admin')"), {"u": str(uid)}
    )
    await db.commit()
    yield create_access_token(uid, email, "customer")
    await db.execute(text("DELETE FROM public.products WHERE name LIKE 'F58-%'"))
    await db.execute(text("DELETE FROM public.users WHERE id = :u"), {"u": str(uid)})
    await db.commit()


async def _get(path: str, token: str | None = None) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return await client.get(path, headers=headers)


async def _create(admin: str, **fields) -> None:
    body = {"name": f"F58-{uuid4().hex[:6]}", "category": "test", "price": 1000, **fields}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.post(
            "/products", json=body, headers={"Authorization": f"Bearer {admin}"}
        )
    assert res.status_code == 201, res.text


def _derive(products: list[dict]) -> dict:
    """What `useCatalog()` computed in the browser from the active product list."""
    sizes = list(dict.fromkeys(s for p in products for s in p["sizes"] or []))
    colors: dict[str, str] = {}
    for p in products:
        for c in p["colors"] or []:
            colors[c["name"]] = c["hex"]
    tags = {t for p in products for t in p["tags"] or []}
    prices = [p["price"] for p in products]
    return {"sizes": set(sizes), "colors": colors, "tags": tags,
            "price_min": min(prices, default=None), "price_max": max(prices, default=None)}


async def test_facets_equal_what_the_shop_derived_from_the_catalogue(db, admin):
    await _create(
        admin, sizes=["F58-EQ"], tags=["f58-eq"],
        colors=[{"name": "F58-EQ", "hex": "#0e0e0e"}],
    )
    facets = (await _get("/products/facets")).json()
    derived = _derive((await _get("/products")).json())  # anonymous → active only
    assert set(facets["sizes"]) == derived["sizes"]
    assert len(facets["sizes"]) == len(derived["sizes"])  # no duplicates
    assert {c["name"]: c["hex"] for c in facets["colors"]} == derived["colors"]
    assert len(facets["colors"]) == len(derived["colors"])
    assert set(facets["tags"]) == derived["tags"]
    assert (facets["price_min"], facets["price_max"]) == (
        derived["price_min"], derived["price_max"]
    )


async def test_inactive_products_never_contribute(db, admin):
    await _create(
        admin, sizes=["F58-ON"], tags=["f58-on"],
        colors=[{"name": "F58-ON", "hex": "#010101"}],
    )
    await _create(
        admin, active=False, price=99_999_999, sizes=["F58-OFF"], tags=["f58-off"],
        colors=[{"name": "F58-OFF", "hex": "#020202"}],
    )
    for token in (None, admin):  # the same answer for a shopper and for staff
        res = await _get("/products/facets", token)
        assert res.status_code == 200
        facets = res.json()
        assert "F58-ON" in facets["sizes"] and "F58-OFF" not in facets["sizes"]
        assert "f58-on" in facets["tags"] and "f58-off" not in facets["tags"]
        names = [c["name"] for c in facets["colors"]]
        assert "F58-ON" in names and "F58-OFF" not in names
        assert facets["price_max"] != 99_999_999


async def test_first_seen_order_and_colour_dedupe(db, admin):
    await _create(admin, sizes=["F58-2", "F58-1"], colors=[{"name": "F58-C", "hex": "#000001"}])
    await _create(admin, sizes=["F58-1", "F58-3"], colors=[{"name": "F58-C", "hex": "#000002"}])
    facets = (await _get("/products/facets")).json()
    mine = [s for s in facets["sizes"] if s.startswith("F58-")]
    assert mine == ["F58-1", "F58-3", "F58-2"]  # newest product first, then its order
    colors = [c for c in facets["colors"] if c["name"] == "F58-C"]
    # one entry; like the browser's Map, the later-listed (older) product's hex wins
    assert colors == [{"name": "F58-C", "hex": "#000001"}]


async def test_cheapest_active_product_sets_the_floor(db, admin):
    await _create(admin, price=1)
    assert (await _get("/products/facets")).json()["price_min"] == 1


async def test_no_active_product_means_no_price_range(db):
    await db.execute(text("UPDATE public.products SET active = false WHERE active"))
    try:
        facets = await product_facets(db)  # same transaction: sees the uncommitted update
        assert facets.sizes == [] and facets.colors == [] and facets.tags == []
        assert (facets.price_min, facets.price_max) == (None, None)
    finally:
        await db.rollback()
