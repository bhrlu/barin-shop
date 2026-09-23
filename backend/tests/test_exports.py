"""Export date handling and CSV encoding (B2.2b).

* `parse_range` converts an explicit offset to UTC (it used to drop it:
  `from=2026-09-22T00:00:00+03:30` was read as UTC midnight) and keeps naive input as
  UTC — the admin UI's format; `to` stays exclusive;
* bad or inverted dates are a Persian 422;
* CSV bodies start with a UTF-8 BOM so Excel reads the Persian text.
"""

from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text

from app.db import SessionLocal, engine, startup_ddl
from app.main import app
from app.security import create_access_token
from app.services.exports import parse_range

# --- the parser -------------------------------------------------------------------


def test_naive_input_is_utc():
    start, end = parse_range("2026-09-22T00:00:00", "2026-09-23T00:00:00")
    assert start == datetime(2026, 9, 22, tzinfo=UTC)
    assert end == datetime(2026, 9, 23, tzinfo=UTC)


def test_an_explicit_offset_is_converted_not_dropped():
    start, end = parse_range("2026-09-22T00:00:00+03:30", "2026-09-23T00:00:00+03:30")
    assert start == datetime(2026, 9, 21, 20, 30, tzinfo=UTC)
    assert end == datetime(2026, 9, 22, 20, 30, tzinfo=UTC)
    zulu, _ = parse_range("2026-09-22T00:00:00Z", "2026-09-23")
    assert zulu == datetime(2026, 9, 22, tzinfo=UTC)


def test_inverted_or_empty_range_is_a_persian_error():
    with pytest.raises(ValueError, match="تاریخ شروع باید پیش از تاریخ پایان باشد"):
        parse_range("2026-09-23", "2026-09-22")
    with pytest.raises(ValueError, match="تاریخ شروع باید پیش از تاریخ پایان باشد"):
        parse_range("2026-09-22T03:30:00+03:30", "2026-09-22T00:00:00Z")  # same instant


def test_a_bad_date_is_a_persian_error():
    with pytest.raises(ValueError, match="تاریخ شروع نامعتبر است"):
        parse_range("22/09/2026", None)
    with pytest.raises(ValueError, match="تاریخ پایان نامعتبر است"):
        parse_range(None, "yesterday")


def test_the_default_window_is_thirty_days_to_now():
    start, end = parse_range(None, None)
    assert end.tzinfo is not None and 29 <= (end - start).days <= 31


# --- over HTTP --------------------------------------------------------------------


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
    tag = uuid4().hex[:6]
    uid = (
        await db.execute(
            text("INSERT INTO public.users (email, password_hash) VALUES (:e, 'x') RETURNING id"),
            {"e": f"b22b-{tag}@test.local"},
        )
    ).scalar()
    await db.execute(
        text("INSERT INTO public.user_roles (user_id, role) VALUES (:u, 'admin')"), {"u": str(uid)}
    )
    # an order at 2026-01-10 21:00 UTC = 2026-01-11 00:30 in Tehran (+03:30)
    number = (
        await db.execute(
            text(
                "INSERT INTO public.orders (user_id, status, payment_status, payment_method, "
                " subtotal, discount, shipping, total, shipping_address, created_at) "
                "VALUES (:u, 'pending', 'unpaid', 'online', 1000, 0, 0, 1000, '{}', "
                "        '2026-01-10T21:00:00Z') RETURNING order_number"
            ),
            {"u": str(uid)},
        )
    ).scalar()
    await db.commit()
    yield {"token": create_access_token(uid, f"b22b-{tag}@test.local", "customer"),
           "number": str(number)}
    await db.execute(text("DELETE FROM public.users WHERE id = :u"), {"u": str(uid)})
    await db.commit()


async def _get(token: str, path: str, **params) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(path, params=params,
                                headers={"Authorization": f"Bearer {token}"})


async def test_an_offset_window_finds_the_order_on_its_local_day(world):
    # Tehran's 2026-01-11 is [2026-01-10T20:30Z, 2026-01-11T20:30Z): the order is inside.
    res = await _get(world["token"], "/admin/export/orders.csv",
                     **{"from": "2026-01-11T00:00:00+03:30", "to": "2026-01-12T00:00:00+03:30"})
    assert res.status_code == 200
    assert world["number"] in res.text  # dropping the offset put it a day early: missing
    earlier = await _get(world["token"], "/admin/export/orders.csv",
                         **{"from": "2026-01-10T00:00:00+03:30", "to": "2026-01-11T00:00:00+03:30"})
    assert world["number"] not in earlier.text


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"from": "not-a-date"}, "تاریخ شروع نامعتبر است"),
        ({"from": "2026-02-01", "to": "2026-01-01"}, "تاریخ شروع باید پیش از تاریخ پایان باشد"),
    ],
)
async def test_bad_ranges_are_a_persian_422(world, params, message):
    for path in ("/admin/export/orders.csv", "/admin/export/report"):
        res = await _get(world["token"], path, **params)
        assert res.status_code == 422
        assert message in res.json()["detail"]


async def test_csv_starts_with_a_bom_and_xlsx_does_not(world):
    for path in ("/admin/export/orders.csv", "/admin/export/products.csv"):
        res = await _get(world["token"], path)
        assert res.status_code == 200
        assert res.content.startswith(b"\xef\xbb\xbf")
        assert res.content[3:].decode("utf-8").split("\n", 1)[0].count(",") > 2
    xlsx = await _get(world["token"], "/admin/export/orders.xlsx")
    assert xlsx.status_code == 200 and xlsx.content.startswith(b"PK")  # a zip, untouched
