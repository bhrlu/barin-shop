"""Server-side search / filter / sort for the admin lists (F4.3, admin data table).

`GET /admin/orders` gains `status` (repeatable / comma-separated), `payment_status`,
`q` (order number, customer name, phone, email, tracking code) and `sort`;
`GET /admin/users` gains `q` (email, name, phone), `role` (staff / customer) and
`sort`. Every parameter is optional and the old answer is unchanged without them.
Each test works on its own tagged rows, so the assertions are exact on a shared DB.
"""

import json
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


async def _user(db, email: str, name: str, phone: str, *roles: str):
    uid = (
        await db.execute(
            text("INSERT INTO public.users (email, password_hash) VALUES (:e, 'x') RETURNING id"),
            {"e": email},
        )
    ).scalar()
    await db.execute(
        text(
            "INSERT INTO public.profiles (id, full_name, phone) VALUES (:u, :n, :p) "
            "ON CONFLICT (id) DO UPDATE SET full_name = :n, phone = :p"
        ),
        {"u": str(uid), "n": name, "p": phone},
    )
    for role in roles:
        await db.execute(
            text("INSERT INTO public.user_roles (user_id, role) VALUES (:u, :r)"),
            {"u": str(uid), "r": role},
        )
    return uid


@pytest.fixture
async def world(db):
    tag = uuid4().hex[:6]
    digits = str(int(tag, 16))[-6:].rjust(6, "0")
    admin = await _user(db, f"f43-admin-{tag}@test.local", f"F43 مدیر {tag}", "", "admin")
    cust = await _user(
        db, f"f43-cust-{tag}@test.local", f"F43 مشتری {tag}", f"0999{digits}"
    )
    other = await _user(db, f"f43-other-{tag}@test.local", f"F43 دیگری {tag}", "")
    orders = []
    for i, (st, pay, total, track) in enumerate(
        [
            ("pending", "unpaid", 300_000, None),
            ("shipped", "paid", 100_000, f"F43TRK{tag}"),
            ("cancelled", "unpaid", 200_000, None),
        ]
    ):
        row = (
            await db.execute(
                text(
                    "INSERT INTO public.orders (user_id, status, payment_status, payment_method, "
                    " subtotal, discount, shipping, total, shipping_address, tracking_code, "
                    " created_at) "
                    "VALUES (:u, :s, :p, 'online', :t, 0, 0, :t, CAST(:a AS jsonb), :k, "
                    "        now() + make_interval(secs => :i)) RETURNING id, order_number"
                ),
                {
                    "u": str(cust), "s": st, "p": pay, "t": total, "k": track, "i": i,
                    "a": json.dumps({
                        "full_name": f"F43 گیرنده {tag}", "phone": f"0999{digits}",
                        "city": "تهران", "line": "خیابان آزمون",
                    }),
                },
            )
        ).mappings().first()
        orders.append({"id": str(row["id"]), "number": row["order_number"], "total": total})
    # `other` spent more (for the users sort)
    await db.execute(
        text(
            "INSERT INTO public.orders (user_id, status, payment_status, payment_method, "
            " subtotal, discount, shipping, total, shipping_address) "
            "VALUES (:u, 'delivered', 'paid', 'online', 900000, 0, 0, 900000, '{}')"
        ),
        {"u": str(other)},
    )
    await db.commit()
    yield {
        "tag": tag, "digits": digits, "orders": orders,
        "token": create_access_token(admin, f"f43-admin-{tag}@test.local", "customer"),
    }
    await db.execute(
        text("DELETE FROM public.orders WHERE user_id IN (:c, :o)"),
        {"c": str(cust), "o": str(other)},
    )
    await db.execute(
        text("DELETE FROM public.users WHERE id IN (:a, :c, :o)"),
        {"a": str(admin), "c": str(cust), "o": str(other)},
    )
    await db.commit()


async def _get(path: str, token: str, **params) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(
            path, params=params, headers={"Authorization": f"Bearer {token}"}
        )


async def _orders(world, **params) -> dict:
    res = await _get("/admin/orders", world["token"], page=1, page_size=50, **params)
    assert res.status_code == 200, res.text
    return res.json()


async def test_without_parameters_the_answer_is_unchanged(world):
    env = await _orders(world)
    assert {"items", "total", "page", "page_size", "pages"} <= set(env)
    bare = await _get("/admin/orders", world["token"])
    assert isinstance(bare.json(), list)
    stamps = [o["created_at"] for o in env["items"]]
    assert stamps == sorted(stamps, reverse=True)  # newest first, as before


@pytest.mark.parametrize("field", ["name", "phone", "email"])
async def test_search_finds_the_customers_orders(world, field):
    q = {"name": f"گیرنده {world['tag']}", "phone": world["digits"],
         "email": f"f43-cust-{world['tag']}"}[field]
    env = await _orders(world, q=q)
    assert env["total"] == 3
    assert {o["id"] for o in env["items"]} == {o["id"] for o in world["orders"]}


async def test_search_by_order_number_and_tracking_code(world):
    target = world["orders"][1]
    assert [o["id"] for o in (await _orders(world, q=target["number"]))["items"]] == [target["id"]]
    tracked = await _orders(world, q=f"F43TRK{world['tag']}")
    assert [o["id"] for o in tracked["items"]] == [target["id"]]


async def test_like_wildcards_are_literal(world):
    assert (await _orders(world, q=f"گیرنده%{world['tag']}"))["total"] == 0
    assert (await _orders(world, q=f"F43_TRK{world['tag']}"))["total"] == 0


async def test_status_filters_single_multi_and_repeated(world):
    mine = f"گیرنده {world['tag']}"
    assert (await _orders(world, q=mine, status="shipped"))["total"] == 1
    assert (await _orders(world, q=mine, status="pending,shipped"))["total"] == 2
    async with httpx.AsyncClient(  # repeated ?status= (a dict cannot hold both)
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get(
            "/admin/orders",
            params=[("page", 1), ("q", mine), ("status", "pending"), ("status", "cancelled")],
            headers={"Authorization": f"Bearer {world['token']}"},
        )
    assert res.json()["total"] == 2
    assert (await _orders(world, q=mine, payment_status="paid"))["total"] == 1


async def test_sorts(world):
    mine = f"گیرنده {world['tag']}"
    totals = lambda env: [o["total"] for o in env["items"]]  # noqa: E731
    assert totals(await _orders(world, q=mine, sort="total_asc")) == [100_000, 200_000, 300_000]
    assert totals(await _orders(world, q=mine, sort="total_desc")) == [300_000, 200_000, 100_000]
    created = [o["id"] for o in world["orders"]]
    assert [o["id"] for o in (await _orders(world, q=mine, sort="old"))["items"]] == created
    assert [o["id"] for o in (await _orders(world, q=mine))["items"]] == created[::-1]


@pytest.mark.parametrize(
    "params", [{"status": "lost"}, {"payment_status": "maybe"}, {"sort": "random"}]
)
async def test_invalid_values_are_422(world, params):
    res = await _get("/admin/orders", world["token"], page=1, **params)
    assert res.status_code == 422


async def _users(world, **params) -> dict:
    res = await _get("/admin/users", world["token"], page=1, page_size=50, **params)
    assert res.status_code == 200, res.text
    return res.json()


async def test_users_search_role_and_sort(world):
    tag = world["tag"]
    by_email = await _users(world, q=f"f43-cust-{tag}")
    assert [u["email"] for u in by_email["items"]] == [f"f43-cust-{tag}@test.local"]
    assert (await _users(world, q=world["digits"]))["total"] == 1  # phone
    assert (await _users(world, q=f"مشتری {tag}"))["total"] == 1  # name
    staff = await _users(world, q=tag, role="staff")
    assert [u["email"] for u in staff["items"]] == [f"f43-admin-{tag}@test.local"]
    customers = await _users(world, q=tag, role="customer")
    assert {u["email"] for u in customers["items"]} == {
        f"f43-cust-{tag}@test.local", f"f43-other-{tag}@test.local"}
    spent = await _users(world, q=tag, sort="spent")
    # other: 900 000 delivered; cust: 300 000 + 100 000 (cancelled excluded); admin: 0
    assert [u["email"].split("-")[1] for u in spent["items"]] == ["other", "cust", "admin"]
    orders = await _users(world, q=tag, sort="orders")
    assert orders["items"][0]["email"] == f"f43-cust-{tag}@test.local"  # 3 orders
    assert (await _get("/admin/users", world["token"], role="nobody")).status_code == 422
