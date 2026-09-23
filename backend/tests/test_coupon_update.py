"""`PATCH /coupons/{id}` clear semantics and single discount kind (F5.16).

The edit dialog could not clear a field: it sent `null`, which PATCH treats as
"unchanged". Worse, switching a percent coupon to a fixed amount kept
`percent_off`, and `compute_discount` prefers percent — the customer kept the old
discount. Pinned here, through the same `/coupons/validate` path checkout uses:

* `expires_at: ""` clears the expiry, `max_uses: 0` clears the total cap;
* setting one kind clears the other (exactly one kind); both at once → 422;
* omitted / null still means unchanged (existing callers keep working).

Live-DB tests; they skip when no database is reachable.
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
async def admin(db):
    email = f"f516-{uuid4().hex[:8]}@test.local"
    uid = (
        await db.execute(
            text("INSERT INTO public.users (email, password_hash) VALUES (:e, 'x') RETURNING id"),
            {"e": email},
        )
    ).scalar()
    await db.execute(
        text("INSERT INTO public.user_roles (user_id, role) VALUES (:u, 'admin')"),
        {"u": str(uid)},
    )
    await db.commit()
    codes: list[str] = []
    try:
        yield {"token": create_access_token(uid, email, "customer"), "codes": codes}
    finally:
        await db.execute(text("DELETE FROM public.coupons WHERE code = ANY(:c)"), {"c": codes})
        await db.execute(text("DELETE FROM public.users WHERE id = :u"), {"u": str(uid)})
        await db.commit()


async def _call(method: str, path: str, token: str, **kw) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        return await client.request(
            method, path, headers={"Authorization": f"Bearer {token}"}, **kw
        )


async def _create(admin: dict, **fields) -> tuple[str, str]:
    code = f"F516{uuid4().hex[:6].upper()}"
    admin["codes"].append(code)
    res = await _call("POST", "/coupons", admin["token"], json={"code": code, **fields})
    assert res.status_code == 201, res.text
    listed = (await _call("GET", "/coupons", admin["token"])).json()["coupons"]
    return code, next(c["id"] for c in listed if c["code"] == code)


async def _row(db, code: str) -> dict:
    await db.commit()
    return dict(
        (
            await db.execute(text("SELECT * FROM public.coupons WHERE code = :c"), {"c": code})
        ).mappings().first()
    )


async def _discount(admin: dict, code: str, subtotal: int) -> int:
    res = await _call(
        "POST", "/coupons/validate", admin["token"], json={"code": code, "subtotal": subtotal}
    )
    assert res.status_code == 200, res.text
    return res.json()["discount"]


async def test_empty_expiry_clears_it(db, admin):
    code, cid = await _create(admin, percent_off=10, expires_at="2030-01-31T23:59:59Z")
    assert (await _row(db, code))["expires_at"] is not None
    res = await _call("PATCH", f"/coupons/{cid}", admin["token"], json={"expires_at": ""})
    assert res.status_code == 200
    assert (await _row(db, code))["expires_at"] is None


async def test_zero_total_cap_means_unlimited(db, admin):
    code, cid = await _create(admin, percent_off=10, max_uses=5)
    res = await _call("PATCH", f"/coupons/{cid}", admin["token"], json={"max_uses": 0})
    assert res.status_code == 200
    assert (await _row(db, code))["max_uses"] is None
    bad = await _call("PATCH", f"/coupons/{cid}", admin["token"], json={"max_uses": -1})
    assert bad.status_code == 422


async def test_switching_percent_to_amount_changes_the_real_discount(db, admin):
    code, cid = await _create(admin, percent_off=10)
    assert await _discount(admin, code, 1_000_000) == 100_000
    res = await _call("PATCH", f"/coupons/{cid}", admin["token"], json={"amount_off": 50_000})
    assert res.status_code == 200
    row = await _row(db, code)
    assert (row["percent_off"], row["amount_off"]) == (None, 50_000)
    assert await _discount(admin, code, 1_000_000) == 50_000  # used to stay 100 000


async def test_switching_amount_to_percent_clears_the_amount(db, admin):
    code, cid = await _create(admin, amount_off=50_000)
    res = await _call("PATCH", f"/coupons/{cid}", admin["token"], json={"percent_off": 20})
    assert res.status_code == 200
    row = await _row(db, code)
    assert (row["percent_off"], row["amount_off"]) == (20, None)
    assert await _discount(admin, code, 1_000_000) == 200_000


async def test_both_kinds_at_once_is_rejected_and_changes_nothing(db, admin):
    code, cid = await _create(admin, percent_off=10)
    res = await _call(
        "PATCH", f"/coupons/{cid}", admin["token"], json={"percent_off": 15, "amount_off": 1_000}
    )
    assert res.status_code == 422
    row = await _row(db, code)
    assert (row["percent_off"], row["amount_off"]) == (10, None)


async def test_null_and_omitted_fields_stay_unchanged(db, admin):
    code, cid = await _create(
        admin, percent_off=10, max_uses=5, expires_at="2030-01-31T23:59:59Z", min_subtotal=100
    )
    res = await _call(
        "PATCH",
        f"/coupons/{cid}",
        admin["token"],
        json={"percent_off": None, "amount_off": None, "max_uses": None, "expires_at": None,
              "min_subtotal": 200},
    )
    assert res.status_code == 200
    row = await _row(db, code)
    assert row["percent_off"] == 10 and row["amount_off"] is None
    assert row["max_uses"] == 5 and row["expires_at"] is not None
    assert row["min_subtotal"] == 200


async def test_the_switch_is_audited_with_old_and_new_values(db, admin):
    code, cid = await _create(admin, percent_off=10)
    await _call("PATCH", f"/coupons/{cid}", admin["token"], json={"amount_off": 50_000})
    await db.commit()
    entry = (
        await db.execute(
            text(
                "SELECT old_values, new_values FROM public.audit_logs "
                "WHERE action = 'update_coupon' AND entity_id = :e"
            ),
            {"e": str(cid)},
        )
    ).mappings().first()
    assert entry["old_values"] == {"percent_off": 10, "amount_off": None}
    assert entry["new_values"] == {"percent_off": None, "amount_off": 50_000}
