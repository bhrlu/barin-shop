"""The complete customer profile (F5.20).

Pinned here:

* the new `profiles` columns (`first_name`, `last_name`, `birth_date`, `gender`,
  `national_id`, `email_verified_at`, `phone_verified_at`) with the F5.20 clear
  semantics — omitted = unchanged, `null`/`""` = cleared;
* the Iranian national code: optional, checksum-validated, leading zeros
  preserved, and returned **only** through `/auth/me` to its owner (never in
  `/admin/users`, never in the JWT);
* verification timestamps are never set by a profile write — no verification
  flow exists, so entering a phone/email must not fake one;
* the one-to-one `user_size_profiles` with its ranges, clear semantics and
  ownership;
* the existing `full_name` compatibility (signup → checkout → admin lists).

Live-DB tests; they skip when no database is reachable.
"""

from datetime import date
from uuid import uuid4

import httpx
import pytest
import sqlalchemy
from sqlalchemy import text

from app.db import SessionLocal, engine, startup_ddl
from app.main import app
from app.security import create_access_token, hash_password
from app.services.profile import (
    GENDERS,
    normalize_birth_date,
    normalize_national_id,
)

# --- pure: national ID ----------------------------------------------------------


def test_valid_national_ids_pass():
    # checksum-valid codes (the last digit follows the mod-11 rule)
    assert normalize_national_id("0493721827") == "0493721827"  # leading zero kept
    assert normalize_national_id("7919966701") == "7919966701"
    assert normalize_national_id("1532532482") == "1532532482"


def test_persian_digits_and_separators_are_normalized():
    assert normalize_national_id("۰۴۹۳۷۲۱۸۲۷") == "0493721827"
    assert normalize_national_id("0493-7218-27") == "0493721827"
    assert normalize_national_id(" 0493721827 ") == "0493721827"


@pytest.mark.parametrize(
    "bad",
    [
        "049372182",  # 9 digits
        "04937218234",  # 11 digits
        "049372182a",  # not a digit
        "0493721827"[:-1] + "0",  # checksum fails
        "0000000000",  # degenerate all-equal codes
        "1111111111",
        "۱۲۳۴۵",  # 5 Persian digits
    ],
)
def test_invalid_national_ids_are_rejected(bad):
    with pytest.raises(ValueError):
        normalize_national_id(bad)


def test_empty_national_id_normalizes_to_none():
    assert normalize_national_id(None) is None
    assert normalize_national_id("") is None
    assert normalize_national_id("   ") is None


# --- pure: birth date / gender sets -------------------------------------------------


def test_birth_date_bounds():
    assert normalize_birth_date(date(1995, 5, 10)) == date(1995, 5, 10)
    with pytest.raises(ValueError):
        normalize_birth_date(date.today().replace(year=date.today().year + 1))
    with pytest.raises(ValueError):
        normalize_birth_date(date(1899, 12, 31))


def test_gender_vocabulary_is_the_documented_closed_set():
    assert GENDERS == ("male", "female", "other")


# --- fixtures -----------------------------------------------------------------------


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
async def users(db):
    """A customer, a second customer and an admin; raw tokens, no login needed."""
    tag = uuid4().hex[:8]
    out = {}
    for who, role in (("customer", None), ("other", None), ("admin", "admin")):
        email = f"f520-{who}-{tag}@test.local"
        uid = (
            await db.execute(
                text(
                    "INSERT INTO public.users (email, password_hash) VALUES (:e, :h) "
                    "RETURNING id"
                ),
                {"e": email, "h": hash_password("secret123")},
            )
        ).scalar()
        await db.execute(
            text("INSERT INTO public.profiles (id, full_name) VALUES (:u, :n)"),
            {"u": str(uid), "n": f"مشتری {who}"},
        )
        if role:
            await db.execute(
                text("INSERT INTO public.user_roles (user_id, role) VALUES (:u, :r)"),
                {"u": str(uid), "r": role},
            )
        out[who] = {"id": uid, "email": email, "token": create_access_token(uid, email, "customer")}
    await db.commit()
    yield out
    await db.execute(
        text("DELETE FROM public.users WHERE id = ANY(CAST(:ids AS uuid[]))"),
        {"ids": [str(u["id"]) for u in out.values()]},
    )
    await db.commit()


async def _call(method: str, path: str, token: str | None = None, **kw) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return await client.request(method, path, headers=headers, **kw)


async def _me(token: str) -> dict:
    res = await _call("GET", "/auth/me", token)
    assert res.status_code == 200, res.text
    return res.json()


# --- DDL -----------------------------------------------------------------------------


async def test_ddl_is_in_place_and_idempotent(db):
    cols = (
        await db.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'profiles' "
                "AND column_name IN ('first_name', 'last_name', 'birth_date', 'gender', "
                "'national_id', 'email_verified_at', 'phone_verified_at')"
            )
        )
    ).all()
    assert dict(cols) == {
        "first_name": "text",
        "last_name": "text",
        "birth_date": "date",
        "gender": "text",
        "national_id": "text",
        "email_verified_at": "timestamp with time zone",
        "phone_verified_at": "timestamp with time zone",
    }
    table = (await db.execute(text(
        "SELECT to_regclass('public.user_size_profiles')"
    ))).scalar()
    assert table is not None
    pk = (await db.execute(text(
        "SELECT COUNT(*) FROM information_schema.table_constraints "
        "WHERE table_name = 'user_size_profiles' AND constraint_type = 'PRIMARY KEY'"
    ))).scalar_one()
    assert pk == 1  # user_id is the primary key → strictly one-to-one
    await startup_ddl()  # a second boot changes nothing and does not fail


# --- existing compatibility ------------------------------------------------------------


async def test_existing_full_name_and_phone_still_work(users):
    body = await _me(users["customer"]["token"])
    assert body["full_name"] == "مشتری customer"
    assert body["email"] == users["customer"]["email"]
    assert body["avatar_url"] is None
    # the new fields default to null on pre-F5.20 rows
    assert body["first_name"] is None and body["national_id"] is None


async def test_signup_and_login_still_work(db, users):
    email = f"f520-signup-{uuid4().hex[:6]}@example.com"
    res = await _call(
        "POST", "/auth/signup",
        json={"email": email, "password": "secret123", "full_name": "کاربر تازه"},
    )
    assert res.status_code == 201, res.text
    token = res.json()["access_token"]
    body = await _me(token)
    assert body["full_name"] == "کاربر تازه" and body["national_id"] is None
    login = await _call("POST", "/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200
    await db.execute(
        text("DELETE FROM public.users WHERE lower(email) = :e"), {"e": email}
    )
    await db.commit()


# --- personal information + clear semantics ----------------------------------------------


async def test_personal_fields_save_and_persist(users):
    token = users["customer"]["token"]
    res = await _call("PATCH", "/auth/me", token, json={
        "first_name": "سارا", "last_name": "محمدی", "birth_date": "1995-05-10",
        "gender": "female",
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["first_name"], body["last_name"]) == ("سارا", "محمدی")
    assert body["birth_date"] == "1995-05-10" and body["gender"] == "female"
    # persisted beyond the response
    again = await _me(token)
    assert again["birth_date"] == "1995-05-10" and again["first_name"] == "سارا"


async def test_omitted_fields_are_unchanged(users):
    token = users["customer"]["token"]
    await _call("PATCH", "/auth/me", token, json={"first_name": "سارا", "gender": "female"})
    body = (await _call("PATCH", "/auth/me", token, json={"last_name": "محمدی"})).json()
    assert body["first_name"] == "سارا" and body["gender"] == "female"
    assert body["last_name"] == "محمدی"


async def test_empty_patch_changes_nothing(users):
    token = users["customer"]["token"]
    await _call("PATCH", "/auth/me", token, json={"first_name": "سارا"})
    body = (await _call("PATCH", "/auth/me", token, json={})).json()
    assert body["first_name"] == "سارا"


async def test_null_clears_optional_fields(users):
    token = users["customer"]["token"]
    await _call("PATCH", "/auth/me", token, json={
        "first_name": "سارا", "last_name": "محمدی", "birth_date": "1995-05-10",
        "gender": "female",
    })
    body = (await _call("PATCH", "/auth/me", token, json={
        "first_name": None, "last_name": None, "birth_date": None, "gender": None,
    })).json()
    assert body["first_name"] is None and body["last_name"] is None
    assert body["birth_date"] is None and body["gender"] is None


async def test_future_birth_date_is_422(users):
    res = await _call("PATCH", "/auth/me", users["customer"]["token"], json={
        "birth_date": "2999-01-01",
    })
    assert res.status_code == 422
    assert "آینده" in res.json()["detail"]


async def test_full_name_is_derived_from_both_names(users):
    token = users["customer"]["token"]
    body = (await _call("PATCH", "/auth/me", token, json={
        "first_name": "سارا", "last_name": "محمدی",
    })).json()
    assert body["full_name"] == "سارا محمدی"


async def test_full_name_merges_with_stored_counterpart(users):
    """Only first sent → derived from the new first + the stored last (and vice versa)."""
    token = users["customer"]["token"]
    await _call("PATCH", "/auth/me", token, json={"first_name": "سارا", "last_name": "محمدی"})
    body = (await _call("PATCH", "/auth/me", token, json={"first_name": "زهرا"})).json()
    assert body["full_name"] == "زهرا محمدی"
    body = (await _call("PATCH", "/auth/me", token, json={"last_name": "رضایی"})).json()
    assert body["full_name"] == "زهرا رضایی"


async def test_clearing_names_yields_empty_full_name(users):
    token = users["customer"]["token"]
    await _call("PATCH", "/auth/me", token, json={"first_name": "سارا", "last_name": "محمدی"})
    body = (await _call("PATCH", "/auth/me", token, json={
        "first_name": None, "last_name": None,
    })).json()
    assert body["full_name"] == ""


async def test_explicit_full_name_wins_over_derivation(users):
    token = users["customer"]["token"]
    body = (await _call("PATCH", "/auth/me", token, json={
        "first_name": "سارا", "last_name": "محمدی", "full_name": "نام سفارشی",
    })).json()
    assert body["full_name"] == "نام سفارشی"


async def test_first_name_only_with_no_stored_last(users):
    """A first name alone must not produce a stray leading/trailing space."""
    token = users["customer"]["token"]
    body = (await _call("PATCH", "/auth/me", token, json={"first_name": "سارا"})).json()
    assert body["full_name"] == "سارا"


# --- national ID --------------------------------------------------------------------------


async def test_valid_national_id_is_stored_with_leading_zero(users):
    token = users["customer"]["token"]
    res = await _call("PATCH", "/auth/me", token, json={"national_id": "۰۴۹۳۷۲۱۸۲۷"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["national_id"] == "0493721827"  # normalised, leading zero kept
    assert (await _me(token))["national_id"] == "0493721827"  # persisted


@pytest.mark.parametrize(
    "bad",
    ["049372182", "04937218234", "049372182a", "0493721824", "1111111111"],
)
async def test_invalid_national_ids_are_422(users, bad):
    res = await _call("PATCH", "/auth/me", users["customer"]["token"], json={"national_id": bad})
    assert res.status_code == 422


async def test_national_id_can_be_cleared_with_empty_string(users):
    token = users["customer"]["token"]
    await _call("PATCH", "/auth/me", token, json={"national_id": "0493721827"})
    body = (await _call("PATCH", "/auth/me", token, json={"national_id": ""})).json()
    assert body["national_id"] is None


async def test_national_id_only_reaches_its_owner(users):
    token = users["customer"]["token"]
    await _call("PATCH", "/auth/me", token, json={"national_id": "0493721827"})
    # the owner sees it on /auth/me
    assert (await _me(token))["national_id"] == "0493721827"
    # /admin/users (staff) does not carry it — the list SELECT is untouched
    admin_list = (await _call("GET", "/admin/users", users["admin"]["token"])).json()
    items = admin_list["items"] if isinstance(admin_list, dict) else admin_list
    row = next(u for u in items if u["email"] == users["customer"]["email"])
    assert "national_id" not in row
    # the JWT never carries it
    from app.security import decode_access_token

    payload = decode_access_token(token)
    assert "national_id" not in payload
    # another user's token cannot read or mutate it: /auth/me is self-scoped
    other = await _me(users["other"]["token"])
    assert other["national_id"] is None


# --- verification state --------------------------------------------------------------------


async def test_entering_phone_or_email_never_fakes_verification(db, users):
    token = users["customer"]["token"]
    body = (await _call("PATCH", "/auth/me", token, json={"phone": "09121110000"})).json()
    assert body["phone"] == "09121110000"
    assert body["phone_verified_at"] is None and body["email_verified_at"] is None
    # no code path in this task may set the timestamps: assert directly on the row
    await db.rollback()  # the PATCH committed on the API's own session
    row = (await db.execute(text(
        "SELECT email_verified_at, phone_verified_at FROM public.profiles WHERE id = :u"
    ), {"u": str(users["customer"]["id"])})).mappings().first()
    assert row["email_verified_at"] is None and row["phone_verified_at"] is None


async def test_unverified_state_is_represented_as_null_timestamps(users):
    body = await _me(users["customer"]["token"])
    assert body["phone_verified_at"] is None and body["email_verified_at"] is None


# --- size profile -----------------------------------------------------------------------------


async def test_size_profile_starts_empty_and_creates_on_first_patch(users):
    token = users["customer"]["token"]
    empty = (await _call("GET", "/auth/me/size-profile", token)).json()
    assert empty["height_cm"] is None and empty["updated_at"] is None
    body = (await _call("PATCH", "/auth/me/size-profile", token, json={
        "height_cm": 170, "weight_kg": 60, "chest_cm": 90, "waist_cm": 70, "hip_cm": 98,
        "preferred_top_size": "M", "fit_preference": "regular",
    })).json()
    assert body["height_cm"] == 170 and body["preferred_top_size"] == "M"
    # persisted and retrievable
    again = (await _call("GET", "/auth/me/size-profile", token)).json()
    assert again["height_cm"] == 170 and again["fit_preference"] == "regular"


async def test_size_profile_patch_omitted_null_and_clear(users):
    token = users["customer"]["token"]
    await _call("PATCH", "/auth/me/size-profile", token, json={
        "height_cm": 170, "weight_kg": 60, "chest_cm": 90,
    })
    # omitted → unchanged
    body = (await _call("PATCH", "/auth/me/size-profile", token, json={"waist_cm": 70})).json()
    assert (body["height_cm"], body["weight_kg"]) == (170, 60)
    assert body["waist_cm"] == 70
    # explicit null → cleared
    body = (await _call("PATCH", "/auth/me/size-profile", token, json={"weight_kg": None})).json()
    assert body["weight_kg"] is None and body["height_cm"] == 170
    # clearing everything it has
    body = (await _call("PATCH", "/auth/me/size-profile", token, json={
        "height_cm": None, "chest_cm": None, "waist_cm": None,
    })).json()
    assert body["height_cm"] is None and body["waist_cm"] is None


async def test_size_profile_empty_patch_changes_nothing(users):
    token = users["customer"]["token"]
    await _call("PATCH", "/auth/me/size-profile", token, json={"height_cm": 170})
    body = (await _call("PATCH", "/auth/me/size-profile", token, json={})).json()
    assert body["height_cm"] == 170


@pytest.mark.parametrize(
    "bad",
    [
        {"height_cm": 99}, {"height_cm": 231}, {"height_cm": -170},
        {"weight_kg": 29}, {"weight_kg": 251},
        {"chest_cm": 59}, {"chest_cm": 161},
        {"waist_cm": 49}, {"waist_cm": 161},
        {"hip_cm": 59}, {"hip_cm": 181},
        {"fit_preference": "oversized"},
        {"preferred_top_size": "x" * 21},
    ],
)
async def test_size_profile_invalid_values_are_422(users, bad):
    res = await _call("PATCH", "/auth/me/size-profile", users["customer"]["token"], json=bad)
    assert res.status_code == 422


async def test_size_profile_db_checks_reject_out_of_range(db, users):
    # a value the schema accepts but the DB would not must never be stored —
    # here the ranges match, so this guards the DDL/schema agreement directly
    await _call(
        "PATCH", "/auth/me/size-profile", users["customer"]["token"], json={"height_cm": 150}
    )
    row = (await db.execute(text(
        "SELECT height_cm FROM public.user_size_profiles WHERE user_id = :u"
    ), {"u": str(users["customer"]["id"])})).scalar()
    assert row == 150
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await db.execute(text(
            "UPDATE public.user_size_profiles SET height_cm = 300 WHERE user_id = :u"
        ), {"u": str(users["customer"]["id"])})
        await db.commit()
    await db.rollback()  # the transaction above aborted on purpose; reset it


async def test_size_profile_is_ownership_scoped(users):
    token = users["customer"]["token"]
    await _call("PATCH", "/auth/me/size-profile", token, json={"height_cm": 170})
    # another user sees their own (empty) profile, not the customer's
    other = (await _call("GET", "/auth/me/size-profile", users["other"]["token"])).json()
    assert other["height_cm"] is None
    # PATCH is self-scoped: the other user's write cannot touch the customer's row
    await _call("PATCH", "/auth/me/size-profile", users["other"]["token"], json={"height_cm": 200})
    mine = (await _call("GET", "/auth/me/size-profile", token)).json()
    assert mine["height_cm"] == 170


async def test_size_profile_requires_authentication(db):
    assert (await _call("GET", "/auth/me/size-profile")).status_code == 401
    assert (
        await _call("PATCH", "/auth/me/size-profile", json={"height_cm": 170})
    ).status_code == 401


async def test_profile_endpoints_require_authentication(db):
    assert (await _call("GET", "/auth/me")).status_code == 401
    assert (await _call("PATCH", "/auth/me", json={"first_name": "x"})).status_code == 401


async def test_profile_patch_cannot_touch_another_user(users):
    # /auth/me carries no user id in the body: a forged one is ignored
    res = await _call("PATCH", "/auth/me", users["customer"]["token"], json={
        "first_name": "هک", "user_id": str(users["other"]["id"]),
    })
    assert res.status_code == 200
    other = await _me(users["other"]["token"])
    assert other["first_name"] is None


# --- regression: checkout + admin list compatibility ------------------------------


async def test_profile_name_still_feeds_checkout_and_admin_list(db, users):
    customer, admin = users["customer"], users["admin"]
    await _call("PATCH", "/auth/me", customer["token"], json={
        "first_name": "سارا", "last_name": "محمدی", "full_name": "سارا محمدی",
    })
    products = (await _call("GET", "/products")).json()
    assert products, "seeded products expected"
    pid = products[0]["id"]
    res = await _call("POST", "/checkout", customer["token"], json={
        "lines": [{"product_id": pid, "size": "M", "color": "کرم", "quantity": 1}],
        "address": {
            "full_name": "سارا محمدی", "phone": "09121110000", "province": "تهران",
            "city": "تهران", "line": "خیابان آزمون، پلاک ۱",
        },
    })
    assert res.status_code in (200, 201, 409), res.text  # 409 = stock, still a valid contract
    if res.status_code in (200, 201):
        await db.execute(
            text("DELETE FROM public.orders WHERE user_id = :u"), {"u": str(customer["id"])}
        )
        await db.commit()
    # the admin list still shows the profile name it always showed
    admin_list = (await _call("GET", "/admin/users", admin["token"])).json()
    items = admin_list["items"] if isinstance(admin_list, dict) else admin_list
    row = next(u for u in items if u["email"] == customer["email"])
    assert row["full_name"] == "سارا محمدی"
