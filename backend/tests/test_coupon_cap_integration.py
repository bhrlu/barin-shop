"""End-to-end tests for the coupon discount ceiling (AB-BE-03).

The unit tests in `test_pricing_and_coupons.py` pin `compute_discount`; these
prove the two *callers* agree — `POST /coupons/validate` (what the cart shows)
and checkout (what the order records) must never disagree about the discount,
and the capped amount must be what actually lands in `orders.discount` and in
the redemption row.

Runs against the local docker-compose Postgres; skips when none is reachable.
"""

import os
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://sande:sande@localhost:5432/postgres"
)
os.environ.setdefault("JWT_SECRET", "test-secret")

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal, engine, startup_ddl  # noqa: E402
from app.main import app  # noqa: E402
from app.security import create_access_token  # noqa: E402
from app.services.checkout import create_order  # noqa: E402

ADDRESS = {
    "full_name": "تست",
    "phone": "09120000000",
    "province": "تهران",
    "city": "تهران",
    "line": "خیابان تست",
    "postal_code": "1234567890",
}
UNIT_PRICE = 1_000_000
QUANTITY = 4  # subtotal 4,000,000 — a 50% coupon would give 2,000,000 uncapped
CAP = 300_000


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
async def fixtures(db):
    """A big-ticket product, a fresh customer, and a capped 50% coupon."""
    pid = f"test-abbe03-{uuid4().hex[:8]}"
    email = f"abbe03-{uuid4().hex[:8]}@test.local"
    code = f"CAP{uuid4().hex[:6].upper()}"
    await db.execute(
        text(
            "INSERT INTO public.products (id, name, category, price, sizes, stock, active) "
            "VALUES (:pid, 'AB-BE-03 test', 'test', :price, ARRAY['M'], 50, true)"
        ),
        {"pid": pid, "price": UNIT_PRICE},
    )
    user_id = (
        await db.execute(
            text(
                "INSERT INTO public.users (email, password_hash) "
                "VALUES (:email, 'x') RETURNING id"
            ),
            {"email": email},
        )
    ).scalar()
    coupon_id = (
        await db.execute(
            text(
                "INSERT INTO public.coupons (code, percent_off, max_discount_cap) "
                "VALUES (:code, 50, :cap) RETURNING id"
            ),
            {"code": code, "cap": CAP},
        )
    ).scalar()
    await db.commit()
    try:
        yield {
            "product_id": pid,
            "user_id": user_id,
            "code": code,
            "coupon_id": coupon_id,
            "token": create_access_token(user_id, email, "customer"),
        }
    finally:
        await db.execute(
            text("DELETE FROM public.users WHERE id = :uid"), {"uid": str(user_id)}
        )
        await db.execute(
            text("DELETE FROM public.coupons WHERE id = :cid"), {"cid": str(coupon_id)}
        )
        await db.execute(text("DELETE FROM public.products WHERE id = :pid"), {"pid": pid})
        await db.commit()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _validate(code: str, subtotal: int, token: str) -> httpx.Response:
    async with _client() as client:
        return await client.post(
            "/coupons/validate",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": code, "subtotal": subtotal},
        )


async def _checkout(db, fx) -> dict:
    order = await create_order(
        db,
        fx["user_id"],
        [
            {
                "product_id": fx["product_id"],
                "size": "M",
                "color": "مشکی",
                "quantity": QUANTITY,
            }
        ],
        ADDRESS,
        fx["code"],
    )
    await db.commit()
    return order


class TestCappedCouponEndToEnd:
    async def test_validate_returns_the_capped_discount_and_the_cap(self, db, fixtures):
        r = await _validate(fixtures["code"], UNIT_PRICE * QUANTITY, fixtures["token"])
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["discount"] == CAP  # not 2,000,000
        assert body["max_discount_cap"] == CAP

    async def test_checkout_records_the_same_capped_discount(self, db, fixtures):
        validated = (
            await _validate(fixtures["code"], UNIT_PRICE * QUANTITY, fixtures["token"])
        ).json()["discount"]
        order = await _checkout(db, fixtures)

        assert order["discount"] == validated == CAP
        assert order["subtotal"] == UNIT_PRICE * QUANTITY
        assert order["total"] == order["subtotal"] - CAP + order["shipping"]

        stored = (
            await db.execute(
                text(
                    "SELECT subtotal, discount, total FROM public.orders "
                    "WHERE id = CAST(:oid AS uuid)"
                ),
                {"oid": order["order_id"]},
            )
        ).mappings().first()
        assert int(stored["discount"]) == CAP
        assert int(stored["total"]) == int(stored["subtotal"]) - CAP + order["shipping"]

        redeemed = (
            await db.execute(
                text(
                    "SELECT amount FROM public.coupon_redemptions "
                    "WHERE order_id = CAST(:oid AS uuid)"
                ),
                {"oid": order["order_id"]},
            )
        ).scalar()
        assert int(redeemed) == CAP

    async def test_uncapped_coupon_keeps_the_full_percentage(self, db, fixtures):
        """NULL cap = today's behaviour, so seeded coupons are unaffected."""
        await db.execute(
            text("UPDATE public.coupons SET max_discount_cap = NULL WHERE id = :cid"),
            {"cid": str(fixtures["coupon_id"])},
        )
        await db.commit()
        r = await _validate(fixtures["code"], UNIT_PRICE * QUANTITY, fixtures["token"])
        assert r.json()["discount"] == UNIT_PRICE * QUANTITY // 2
        assert r.json()["max_discount_cap"] is None
        order = await _checkout(db, fixtures)
        assert order["discount"] == UNIT_PRICE * QUANTITY // 2

    async def test_small_cart_under_the_cap_is_not_clamped(self, db, fixtures):
        subtotal = 400_000  # 50% = 200,000, below the 300,000 ceiling
        r = await _validate(fixtures["code"], subtotal, fixtures["token"])
        assert r.json()["discount"] == 200_000


class TestCouponAdminCrud:
    """The cap is settable and clearable through the admin CRUD (AB-BE-03)."""

    @pytest.fixture
    async def admin_token(self, db):
        email = f"abbe03-admin-{uuid4().hex[:8]}@test.local"
        user_id = (
            await db.execute(
                text(
                    "INSERT INTO public.users (email, password_hash) "
                    "VALUES (:email, 'x') RETURNING id"
                ),
                {"email": email},
            )
        ).scalar()
        await db.execute(
            text("INSERT INTO public.user_roles (user_id, role) VALUES (:uid, 'admin')"),
            {"uid": str(user_id)},
        )
        await db.commit()
        try:
            yield create_access_token(user_id, email, "admin")
        finally:
            await db.execute(
                text("DELETE FROM public.users WHERE id = :uid"), {"uid": str(user_id)}
            )
            await db.commit()

    async def test_create_list_update_and_clear_the_cap(self, db, admin_token):
        code = f"CRUD{uuid4().hex[:6].upper()}"
        headers = {"Authorization": f"Bearer {admin_token}"}
        try:
            async with _client() as client:
                created = await client.post(
                    "/coupons",
                    headers=headers,
                    json={"code": code, "percent_off": 30, "max_discount_cap": 250_000},
                )
                assert created.status_code == 201, created.text
                assert created.json()["max_discount_cap"] == 250_000

                listed = await client.get("/coupons", headers=headers)
                row = next(c for c in listed.json()["coupons"] if c["code"] == code)
                assert row["max_discount_cap"] == 250_000

                patched = await client.patch(
                    f"/coupons/{row['id']}", headers=headers, json={"max_discount_cap": 90_000}
                )
                assert patched.status_code == 200
                listed = await client.get("/coupons", headers=headers)
                row = next(c for c in listed.json()["coupons"] if c["code"] == code)
                assert row["max_discount_cap"] == 90_000

                # 0 clears the ceiling back to uncapped
                await client.patch(
                    f"/coupons/{row['id']}", headers=headers, json={"max_discount_cap": 0}
                )
                listed = await client.get("/coupons", headers=headers)
                row = next(c for c in listed.json()["coupons"] if c["code"] == code)
                assert row["max_discount_cap"] is None
        finally:
            await db.execute(text("DELETE FROM public.coupons WHERE code = :c"), {"c": code})
            await db.commit()

    async def test_a_negative_cap_is_rejected(self, db, admin_token):
        async with _client() as client:
            r = await client.post(
                "/coupons",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"code": f"BAD{uuid4().hex[:5].upper()}", "percent_off": 10,
                      "max_discount_cap": -5},
            )
        assert r.status_code == 422

    async def test_a_customer_cannot_set_a_cap(self, db, fixtures):
        async with _client() as client:
            r = await client.post(
                "/coupons",
                headers={"Authorization": f"Bearer {fixtures['token']}"},
                json={"code": f"NOPE{uuid4().hex[:5].upper()}", "percent_off": 10,
                      "max_discount_cap": 1000},
            )
        assert r.status_code == 403
