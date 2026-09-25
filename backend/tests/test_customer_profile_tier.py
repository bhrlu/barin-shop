"""Customer 360° profile (AB-FE-06, spec [FE-08]) and customer tiers (D7b).

`GET /admin/users/{id}/profile` must return exactly what the customer's own
sources hold (orders with items, addresses, favorites, LTV, delivered count,
purchase cadence), the D7b tier (wholesale flag wins, else delivered ≥ 3 →
vip), and refuse anyone without the `users` capability. `PUT
/admin/users/{id}/tier` is the staff entry point for the explicit Wholesale
flag — audited, role != tier. Pure tier math is unit-tested without a DB.

Each test works on its own tagged rows and removes them in teardown, so the
running store's data is never touched.
"""

import os
from uuid import uuid4

os.environ.setdefault("JWT_SECRET", "test-secret")

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal, engine, startup_ddl  # noqa: E402
from app.main import app  # noqa: E402
from app.services.tiers import resolve_tier  # noqa: E402


class TestTierMath:
    """D7b rules, no DB needed — the thresholds live in services/tiers.py."""

    def test_new_below_three_delivered(self):
        assert resolve_tier(0, None) == "new"
        assert resolve_tier(2, None) == "new"

    def test_vip_at_three_delivered(self):
        assert resolve_tier(3, None) == "vip"
        assert resolve_tier(10, None) == "vip"

    def test_wholesale_wins(self):
        assert resolve_tier(0, "wholesale") == "wholesale"
        assert resolve_tier(99, "wholesale") == "wholesale"

    def test_unknown_explicit_tier_ignored(self):
        assert resolve_tier(1, "bogus") == "new"

    def test_role_is_not_tier(self):
        # a staff role never implies a tier and a tier never implies a role —
        # the resolver only sees delivered orders and the explicit flag
        assert resolve_tier(0, None) == "new"


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


async def _user(db, email: str, *roles: str):
    uid = (
        await db.execute(
            text("INSERT INTO public.users (email, password_hash) VALUES (:e, 'x') RETURNING id"),
            {"e": email},
        )
    ).scalar()
    await db.execute(
        text("INSERT INTO public.profiles (id, full_name, phone) VALUES (:u, :n, :p)"),
        {"u": str(uid), "n": "ABFE06 تست", "p": "09120000000"},
    )
    for role in roles:
        await db.execute(
            text("INSERT INTO public.user_roles (user_id, role) VALUES (:u, :r)"),
            {"u": str(uid), "r": role},
        )
    return uid


@pytest.fixture
async def world(db):
    tag = uuid4().hex[:8]
    admin = await _user(db, f"abfe06-admin-{tag}@test.local", "admin")
    cust = await _user(db, f"abfe06-cust-{tag}@test.local")
    await db.commit()  # roles must be visible to the app's own session
    yield {"tag": tag, "admin": admin, "cust": cust}
    await db.execute(
        text("DELETE FROM public.users WHERE id IN (:a, :c)"),
        {"a": str(admin), "c": str(cust)},
    )
    await db.commit()


def _order_sql(created_expr: str = "now()") -> str:
    return (
        "INSERT INTO public.orders (user_id, status, payment_status, payment_method, "
        " subtotal, discount, shipping, total, shipping_address, created_at) "
        "VALUES (:u, :s, 'paid', 'online', :t, 0, 0, :t, '{}', " + created_expr + ") "
        "RETURNING id"
    )


async def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _token(uid, email: str) -> str:
    from app.security import create_access_token

    return create_access_token(uid, email, "customer")


class TestUserProfileEndpoint:
    async def test_overview_matches_customer_sources(self, db, world):
        # 3 orders: two delivered (money), one cancelled (history, not money)
        for st, t in [("delivered", 100_000), ("delivered", 250_000), ("cancelled", 50_000)]:
            await db.execute(text(_order_sql()), {"u": str(world["cust"]), "s": st, "t": t})
        await db.execute(
            text(
                "INSERT INTO public.addresses (user_id, title, receiver, phone, province, "
                " city, line) VALUES (:u, 'خانه', 'گیرنده', '09120000000', 'تهران', "
                " 'تهران', 'خیابان آزمون')"
            ),
            {"u": str(world["cust"])},
        )
        await db.execute(
            text("INSERT INTO public.favorites (user_id, product_id) VALUES (:u, 'tshirt-1')"),
            {"u": str(world["cust"])},
        )
        await db.commit()

        token = await _token(world["admin"], "a@test.local")
        async with await _client() as client:
            r = await client.get(
                f"/admin/users/{world['cust']}/profile",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200, r.text
        body = r.json()

        assert body["profile"]["email"] == f"abfe06-cust-{world['tag']}@test.local"
        assert body["tier"] == "new"  # 2 delivered < 3
        assert body["stats"]["ltv"] == 350_000  # cancelled excluded from money
        assert body["stats"]["order_count"] == 3  # cancelled still in the history
        assert body["stats"]["favorite_count"] == 1
        assert body["stats"]["address_count"] == 1
        assert len(body["orders"]) == 3
        assert all("items" in o for o in body["orders"])  # same shape as GET /orders
        assert body["addresses"][0]["receiver"] == "گیرنده"
        assert body["favorites"][0]["product_id"] == "tshirt-1"

    async def test_tier_is_new_below_threshold_and_vip_at_it(self, db, world):
        for st in ("delivered", "delivered"):
            await db.execute(text(_order_sql()), {"u": str(world["cust"]), "s": st, "t": 10_000})
        await db.commit()
        token = await _token(world["admin"], "a@test.local")
        async with await _client() as client:
            r = await client.get(
                f"/admin/users/{world['cust']}/profile",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.json()["tier"] == "new"

            await db.execute(
                text(_order_sql()), {"u": str(world["cust"]), "s": "delivered", "t": 10_000}
            )
            await db.commit()
            r = await client.get(
                f"/admin/users/{world['cust']}/profile",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.json()["tier"] == "vip"  # 3 delivered

    async def test_wholesale_flag_wins_over_vip(self, db, world):
        await db.execute(
            text(_order_sql()), {"u": str(world["cust"]), "s": "delivered", "t": 10_000}
        )
        await db.execute(
            text("INSERT INTO public.user_tiers (user_id, tier) VALUES (:u, 'wholesale')"),
            {"u": str(world["cust"])},
        )
        await db.commit()
        token = await _token(world["admin"], "a@test.local")
        async with await _client() as client:
            r = await client.get(
                f"/admin/users/{world['cust']}/profile",
                headers={"Authorization": f"Bearer {token}"},
            )
        body = r.json()
        assert body["tier"] == "wholesale"
        assert body["explicit_tier"] == "wholesale"
        assert body["stats"]["delivered_count"] == 1  # the flag, not the count, decided

    async def test_avg_days_between_purchases(self, db, world):
        await db.execute(
            text(_order_sql("now() - interval '10 days'")),
            {"u": str(world["cust"]), "s": "delivered", "t": 10_000},
        )
        await db.execute(
            text(_order_sql("now() - interval '4 days'")),
            {"u": str(world["cust"]), "s": "delivered", "t": 10_000},
        )
        await db.commit()
        token = await _token(world["admin"], "a@test.local")
        async with await _client() as client:
            r = await client.get(
                f"/admin/users/{world['cust']}/profile",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.json()["stats"]["avg_days_between_purchases"] == 6.0

    async def test_missing_user_is_404(self, db, world):
        token = await _token(world["admin"], "a@test.local")
        async with await _client() as client:
            r = await client.get(
                f"/admin/users/{uuid4()}/profile",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 404

    async def test_anonymous_is_401(self, db, world):
        async with await _client() as client:
            r = await client.get(f"/admin/users/{world['cust']}/profile")
        assert r.status_code == 401

    async def test_customer_cannot_read_someone_else_profile(self, db, world):
        token = await _token(world["cust"], "c@test.local")
        async with await _client() as client:
            r = await client.get(
                f"/admin/users/{world['cust']}/profile",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 403

    async def test_support_role_cannot_read_profiles(self, db, world):
        support = await _user(db, f"abfe06-support-{world['tag']}@test.local", "support")
        await db.commit()
        token = await _token(support, "s@test.local")
        async with await _client() as client:
            r = await client.get(
                f"/admin/users/{world['cust']}/profile",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 403  # `users` capability: admin/super_admin only


class TestTierEndpoint:
    async def test_set_and_clear_wholesale(self, db, world):
        token = await _token(world["admin"], "a@test.local")
        async with await _client() as client:
            r = await client.put(
                f"/admin/users/{world['cust']}/tier",
                json={"tier": "wholesale"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["tier"] == "wholesale"

            # audit trail written
            rows = (
                await db.execute(
                    text(
                        "SELECT action FROM public.audit_logs WHERE entity_id = :e "
                        "AND action = 'update_user_tier'"
                    ),
                    {"e": str(world["cust"])},
                )
            ).scalars().all()
            assert rows == ["update_user_tier"]

            # clear → back to automatic (0 delivered → new)
            r = await client.put(
                f"/admin/users/{world['cust']}/tier",
                json={"tier": None},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            assert r.json() == {
                "userId": str(world["cust"]), "explicit_tier": None, "tier": "new"
            }

    async def test_wholesale_does_not_grant_roles(self, db, world):
        """role != tier — the flag must not leak into authorization."""
        token = await _token(world["admin"], "a@test.local")
        async with await _client() as client:
            r = await client.put(
                f"/admin/users/{world['cust']}/tier",
                json={"tier": "wholesale"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            # the customer still has no staff roles and still cannot open staff routes
            r = await client.get(
                "/admin/orders?page=1",
                headers={"Authorization": f"Bearer {await _token(world['cust'], 'c@test.local')}"},
            )
            assert r.status_code == 403

    async def test_bogus_tier_is_422(self, db, world):
        token = await _token(world["admin"], "a@test.local")
        async with await _client() as client:
            r = await client.put(
                f"/admin/users/{world['cust']}/tier",
                json={"tier": "vip"},  # only wholesale is staff-assignable
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 422

    async def test_missing_user_is_404(self, db, world):
        token = await _token(world["admin"], "a@test.local")
        async with await _client() as client:
            r = await client.put(
                f"/admin/users/{uuid4()}/tier",
                json={"tier": "wholesale"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 404

    async def test_customer_cannot_assign_tiers(self, db, world):
        token = await _token(world["cust"], "c@test.local")
        async with await _client() as client:
            r = await client.put(
                f"/admin/users/{world['cust']}/tier",
                json={"tier": "wholesale"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 403


class TestUserListTier:
    async def test_list_rows_carry_the_tier(self, db, world):
        await db.execute(
            text("INSERT INTO public.user_tiers (user_id, tier) VALUES (:u, 'wholesale')"),
            {"u": str(world["cust"])},
        )
        await db.commit()
        token = await _token(world["admin"], "a@test.local")
        async with await _client() as client:
            r = await client.get(
                "/admin/users?q=abfe06-cust",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200, r.text
        rows = r.json()
        row = next(x for x in rows if x["email"] == f"abfe06-cust-{world['tag']}@test.local")
        assert row["tier"] == "wholesale"
        assert row["explicit_tier"] == "wholesale"
        assert row["delivered_count"] == 0
