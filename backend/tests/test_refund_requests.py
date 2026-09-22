"""Endpoint tests for POST /orders/{id}/refunds error handling (B6.9).

The route used to wrap its INSERT in a bare `except Exception` and report every
failure as "a refund was already requested", hiding real database errors. These
tests pin the three outcomes apart: a successful request, a true duplicate, and
an unrelated database failure that must surface instead of being disguised.

They talk to the live Postgres of the local docker-compose stack (the duplicate
case is enforced by `refund_requests`' UNIQUE(order_id) constraint, which only
exists in SQL) and skip when no database is reachable.
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
from sqlalchemy.exc import IntegrityError  # noqa: E402

from app.db import SessionLocal, engine, get_session, startup_ddl  # noqa: E402
from app.main import app  # noqa: E402
from app.routers.orders import _is_unique_violation  # noqa: E402
from app.security import create_access_token  # noqa: E402


async def _db_available() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture
async def db():
    # each test runs in its own event loop; pooled connections belong to the
    # previous one, so the shared engine is emptied before every test.
    await engine.dispose()
    if not await _db_available():
        pytest.skip("no database reachable — integration test skipped")
    await startup_ddl()
    async with SessionLocal() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def refundable_order(db):
    """A cancelled + paid order owned by a throwaway customer, and their token."""
    email = f"b69-{uuid4().hex[:8]}@test.local"
    user_id = (
        await db.execute(
            text(
                "INSERT INTO public.users (email, password_hash) "
                "VALUES (:email, 'x') RETURNING id"
            ),
            {"email": email},
        )
    ).scalar()
    order_id = (
        await db.execute(
            text(
                "INSERT INTO public.orders "
                "(user_id, status, payment_status, subtotal, shipping, total) "
                "VALUES (:uid, 'cancelled', 'paid', 100000, 89000, 189000) RETURNING id"
            ),
            {"uid": str(user_id)},
        )
    ).scalar()
    await db.commit()
    try:
        yield {
            "order_id": str(order_id),
            "user_id": user_id,
            "token": create_access_token(user_id, email, "customer"),
        }
    finally:
        await db.execute(
            text("DELETE FROM public.users WHERE id = :uid"), {"uid": str(user_id)}
        )
        await db.commit()


def _client() -> httpx.AsyncClient:
    # raise_app_exceptions=False so an unhandled error arrives as the 500 a real
    # client would see, instead of exploding inside the test.
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _post_refund(order_id: str, token: str) -> httpx.Response:
    async with _client() as client:
        return await client.post(
            f"/orders/{order_id}/refunds",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "تست"},
        )


class TestUniqueViolationPredicate:
    """SQLSTATE 23505 is the only duplicate; every other code is a real error."""

    class _Orig(Exception):
        def __init__(self, sqlstate: str) -> None:
            self.sqlstate = sqlstate

    def _err(self, sqlstate: str | None) -> IntegrityError:
        orig = self._Orig(sqlstate) if sqlstate else Exception("no sqlstate")
        return IntegrityError("INSERT …", {}, orig)

    def test_unique_violation_is_a_duplicate(self):
        assert _is_unique_violation(self._err("23505")) is True

    def test_foreign_key_violation_is_not_a_duplicate(self):
        assert _is_unique_violation(self._err("23503")) is False

    def test_check_violation_is_not_a_duplicate(self):
        assert _is_unique_violation(self._err("23514")) is False

    def test_driver_without_sqlstate_is_not_a_duplicate(self):
        assert _is_unique_violation(self._err(None)) is False


class TestRefundRequestEndpoint:
    async def test_first_request_is_created(self, db, refundable_order):
        r = await _post_refund(refundable_order["order_id"], refundable_order["token"])
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["status"] == "pending"
        assert body["amount"] == 189000

    async def test_true_duplicate_is_a_409(self, db, refundable_order):
        first = await _post_refund(
            refundable_order["order_id"], refundable_order["token"]
        )
        assert first.status_code == 201, first.text
        second = await _post_refund(
            refundable_order["order_id"], refundable_order["token"]
        )
        assert second.status_code == 409
        assert "قبلاً درخواست بازپرداخت ثبت شده" in second.json()["detail"]
        rows = (
            await db.execute(
                text(
                    "SELECT count(*) FROM public.refund_requests "
                    "WHERE order_id = CAST(:oid AS uuid)"
                ),
                {"oid": refundable_order["order_id"]},
            )
        ).scalar()
        assert rows == 1  # the duplicate wrote nothing

    async def test_unrelated_integrity_error_is_not_reported_as_a_duplicate(
        self, db, refundable_order
    ):
        """A foreign-key violation must surface as a 500, not a false 409."""

        class _ForeignKeyViolation(Exception):
            sqlstate = "23503"

        class _FailingSession:
            """Delegates to the real session but breaks the refund INSERT."""

            def __init__(self, inner):
                self._inner = inner

            def __getattr__(self, name):
                return getattr(self._inner, name)

            async def execute(self, statement, *args, **kwargs):
                if "refund_requests" in str(statement):
                    raise IntegrityError(
                        "INSERT INTO public.refund_requests …",
                        {},
                        _ForeignKeyViolation("fk"),
                    )
                return await self._inner.execute(statement, *args, **kwargs)

        async def _override():
            async with SessionLocal() as session:
                yield _FailingSession(session)

        app.dependency_overrides[get_session] = _override
        try:
            r = await _post_refund(
                refundable_order["order_id"], refundable_order["token"]
            )
        finally:
            app.dependency_overrides.pop(get_session, None)

        assert r.status_code == 500  # surfaced, not swallowed
        assert "بازپرداخت" not in r.text  # and not the duplicate message

    async def test_order_that_is_not_cancelled_and_paid_is_rejected(self, db, refundable_order):
        await db.execute(
            text(
                "UPDATE public.orders SET payment_status = 'unpaid' "
                "WHERE id = CAST(:oid AS uuid)"
            ),
            {"oid": refundable_order["order_id"]},
        )
        await db.commit()
        r = await _post_refund(refundable_order["order_id"], refundable_order["token"])
        assert r.status_code == 409
        assert "لغوشده و پرداخت‌شده" in r.json()["detail"]

    async def test_another_users_order_is_not_found(self, db, refundable_order):
        stranger = create_access_token(uuid4(), "stranger@test.local", "customer")
        r = await _post_refund(refundable_order["order_id"], stranger)
        assert r.status_code == 404

    async def test_anonymous_caller_is_rejected(self, db, refundable_order):
        async with _client() as client:
            r = await client.post(
                f"/orders/{refundable_order['order_id']}/refunds",
                json={"reason": "تست"},
            )
        assert r.status_code == 401
