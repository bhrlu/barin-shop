"""CSV product import (B2.2a, decision D3).

The canonical key is a valid `product_id` when the file supplies one, otherwise
the normalized `name + category`; only supplied columns update; in-file
duplicates are rejected before anything is written; the whole file is one
transaction, so a retried import is idempotent; the ledger rows follow the
manual-edit rules (opening stock `restock`, changed stock `manual_adjustment`).

Live-DB tests (they skip when no database is reachable). Negative controls:
parsing/validation failures must not write anything.
"""

import csv
import io
import json
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text

from app.db import SessionLocal, engine, startup_ddl
from app.main import app
from app.security import create_access_token
from app.services.csv_import import parse_csv

# --- the parser (pure, no DB) -----------------------------------------------------


def _csv_body(rows: list[dict[str, str]], headers: list[str] | None = None) -> bytes:
    buffer = io.StringIO()
    if headers is None:
        keys: dict[str, None] = {}
        for row in rows:
            keys.update({k: None for k in row})
        headers = list(keys)
    writer = csv.DictWriter(buffer, fieldnames=headers, restval="")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def test_parse_accepts_a_bom_and_rejects_unknown_headers():
    body = b"\xef\xbb\xbf" + _csv_body(
        [{"name": "شومیز", "category": "top"}]
    )
    rows = parse_csv(body)
    assert len(rows) == 1 and rows[0].key_name == "شومیز"

    bad = _csv_body([{"nmae": "typo", "category": "top"}])
    with pytest.raises(Exception) as exc:
        parse_csv(bad)
    assert "ستون‌های ناشناس" in getattr(exc.value, "detail", str(exc.value))


def test_parse_normalizes_the_key_and_rejects_in_file_duplicates():
    # each row parsed alone: the normalized keys collapse to the same pair
    a = parse_csv(_csv_body([{"name": "  شومیز   ابریشم ", "category": "Top"}]))
    b = parse_csv(_csv_body([{"name": "شومیز ابریشم", "category": "top "}]))
    assert a[0].canonical_key() == b[0].canonical_key()

    # …but two of them in ONE file are exactly the D3 ambiguity: rejected
    duplicate = _csv_body(
        [
            {"name": "شومیز", "category": "top", "price": "100"},
            {"name": "شومیز", "category": "top", "price": "200"},
        ]
    )
    with pytest.raises(Exception) as exc:
        parse_csv(duplicate)
    assert "کلید تکراری" in getattr(exc.value, "detail", str(exc.value))


def test_id_keyed_rows_do_not_collide_with_name_keys():
    pid = str(uuid4())
    rows = parse_csv(
        _csv_body(
            [
                {"product_id": pid, "name": "A", "category": "c"},
                {"name": "A", "category": "c"},
            ]
        )
    )
    assert rows[0].canonical_key()[0] == "id"
    assert rows[1].canonical_key()[0] == "name+category"


def test_a_bad_uuid_or_missing_key_is_a_clear_422():
    with pytest.raises(Exception) as exc:
        parse_csv(_csv_body([{"product_id": "not-a-uuid", "name": "A", "category": "c"}]))
    assert "UUID" in getattr(exc.value, "detail", str(exc.value))
    with pytest.raises(Exception) as exc:
        parse_csv(_csv_body([{"price": "10"}]))
    assert "name و category" in getattr(exc.value, "detail", str(exc.value))


# --- over HTTP (live DB) ----------------------------------------------------------


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
            {"e": f"b22a-{tag}@test.local"},
        )
    ).scalar()
    await db.execute(
        text("INSERT INTO public.user_roles (user_id, role) VALUES (:u, 'admin')"),
        {"u": str(uid)},
    )
    support_uid = (
        await db.execute(
            text("INSERT INTO public.users (email, password_hash) VALUES (:e, 'x') RETURNING id"),
            {"e": f"b22a-support-{tag}@test.local"},
        )
    ).scalar()
    await db.execute(
        text("INSERT INTO public.user_roles (user_id, role) VALUES (:u, 'support')"),
        {"u": str(support_uid)},
    )
    await db.commit()
    yield {
        "admin": create_access_token(uid, f"b22a-{tag}@test.local", "admin"),
        "support": create_access_token(support_uid, f"b22a-support-{tag}@test.local", "support"),
        "tag": tag,
        "user_id": str(uid),
    }
    await db.execute(text("DELETE FROM public.users WHERE id = :u"), {"u": str(uid)})
    await db.execute(
        text("DELETE FROM public.users WHERE id = :u"), {"u": str(support_uid)}
    )
    await db.commit()


async def _post(token: str, content: bytes, filename: str = "products.csv") -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post(
            "/products/import",
            files={"file": (filename, content, "text/csv")},
            headers={"Authorization": f"Bearer {token}"},
        )


async def _rows(db, where: str, params: dict) -> list[dict]:
    result = await db.execute(
        text(f"SELECT * FROM public.products WHERE {where}"), params
    )
    return [dict(r) for r in result.mappings().all()]


async def _ledger(db, pid: str) -> list[dict]:
    result = await db.execute(
        text(
            "SELECT change_amount, reason FROM public.inventory_logs "
            "WHERE product_id = :p ORDER BY created_at, id"
        ),
        {"p": pid},
    )
    return [dict(r) for r in result.mappings().all()]


async def test_insert_update_by_id_update_by_name_omitted_fields(db, world):
    existing_id = str(uuid4())
    await db.execute(
        text(
            "INSERT INTO public.products (id, name, category, price, stock) "
            "VALUES (:i, 'B22A موجود', 'top', 500000, 7)"
        ),
        {"i": existing_id},
    )
    # a second pre-existing product whose update uses the normalized name key
    name_target = f"B22A سایز {world['tag']}"
    await db.execute(
        text(
            "INSERT INTO public.products (id, name, category, price, stock) "
            "VALUES (:i, :n, 'top', 400000, 2)"
        ),
        {"i": str(uuid4()), "n": name_target},
    )
    await db.commit()

    name_keyed = f"B22A-new-{world['tag']}"
    body = _csv_body(
        [
            # a new product, id absent → created with the supplied columns
            {"name": name_keyed, "category": "top", "price": "900000", "stock": "4"},
            # an update by product_id: only price supplied, nothing else erased
            {"product_id": existing_id, "price": "650000"},
            # an update by normalized name+category (case/whitespace differ)
            {"name": f"  b22a سایز {world['tag']}  ", "category": "TOP",
             "old_price": "800000", "active": "false"},
        ]
    )
    res = await _post(world["admin"], body)
    assert res.status_code == 200, res.text
    assert res.json() == {"created": 1, "updated": 2, "total": 3}

    created = await _rows(db, "name = :n", {"n": name_keyed})
    assert len(created) == 1 and created[0]["price"] == 900000
    assert created[0]["stock"] == 4 and created[0]["is_new"] is True

    by_id = await _rows(db, "id = :i", {"i": existing_id})
    assert by_id[0]["price"] == 650000
    assert by_id[0]["stock"] == 7 and by_id[0]["name"] == "B22A موجود"

    # the name+category row matched; its `name` cell is a supplied column, so
    # D3's "only supplied columns update" legitimately stores the CSV's spelling
    updated = await _rows(db, "name = :n", {"n": f"b22a سایز {world['tag']}"})
    assert updated[0]["old_price"] == 800000 and updated[0]["active"] is False
    assert updated[0]["price"] == 400000  # omitted columns stay

    # the update by id logged only the price change — no stock row was touched
    ledger = await _ledger(db, existing_id)
    assert ledger == []


async def test_a_repeated_import_is_idempotent_and_updates_price(db, world):
    name = f"B22A-idem-{world['tag']}"
    first = _csv_body(
        [{"name": name, "category": "top", "price": "100000", "stock": "3"}]
    )
    assert (await _post(world["admin"], first)).status_code == 200

    rows = await _rows(db, "name = :n", {"n": name})
    pid = str(rows[0]["id"])
    assert len(await _ledger(db, pid)) == 1  # one restock

    second = _csv_body(
        [{"name": name, "category": "top", "price": "120000"}]  # stock omitted
    )
    assert (await _post(world["admin"], second)).status_code == 200

    rows = await _rows(db, "name = :n", {"n": name})
    assert rows[0]["price"] == 120000 and rows[0]["stock"] == 3
    assert len(await _ledger(db, pid)) == 1  # no second movement: idempotent

    # D3 idempotency: re-importing the exact SAME file again is a no-op on the
    # ledger (the matched stock equals the stored one) and rewrites the same
    # values. (Re-importing an OLDER file would legitimately restore its own
    # values — an upsert, not an append-only log.)
    assert (await _post(world["admin"], second)).status_code == 200
    assert len(await _ledger(db, pid)) == 1
    rows = await _rows(db, "name = :n", {"n": name})
    assert rows[0]["price"] == 120000 and rows[0]["stock"] == 3


async def test_in_file_duplicate_is_a_422_and_writes_nothing(db, world):
    before = (
        await db.execute(text("SELECT count(*) FROM public.products"))
    ).scalar()
    body = _csv_body(
        [
            {"name": f"B22A-dup-{world['tag']}", "category": "top", "price": "1"},
            {"product_id": str(uuid4()), "name": "x", "category": "y", "price": "2"},
            {"name": f"B22A-dup-{world['tag']}", "category": "top", "price": "3"},
        ]
    )
    res = await _post(world["admin"], body)
    assert res.status_code == 422
    assert "کلید تکراری" in res.json()["detail"]
    after = (
        await db.execute(text("SELECT count(*) FROM public.products"))
    ).scalar()
    assert after == before  # nothing was written


async def test_a_bad_cell_rolls_the_whole_file_back(db, world):
    before = (
        await db.execute(text("SELECT count(*) FROM public.products"))
    ).scalar()
    body = _csv_body(
        [
            {"name": f"B22A-ok-{world['tag']}", "category": "top", "price": "1"},
            {"name": f"B22A-bad-{world['tag']}", "category": "top", "price": "expensive"},
        ]
    )
    res = await _post(world["admin"], body)
    assert res.status_code == 422
    after = (
        await db.execute(text("SELECT count(*) FROM public.products"))
    ).scalar()
    assert after == before  # the valid first row must NOT survive


async def test_stock_changes_move_the_ledger_like_manual_edits(db, world):
    pid = str(uuid4())
    await db.execute(
        text(
            "INSERT INTO public.products (id, name, category, price, stock) "
            "VALUES (:i, 'B22A stock', 'top', 100000, 5)"
        ),
        {"i": pid},
    )
    await db.commit()

    body = _csv_body(
        [{"product_id": pid, "stock": "8"}]  # 5 → 8: a +3 manual_adjustment
    )
    assert (await _post(world["admin"], body)).status_code == 200
    ledger = await _ledger(db, pid)
    assert ledger == [{"change_amount": 3, "reason": "manual_adjustment"}]

    rows = await _rows(db, "id = :i", {"i": pid})
    assert rows[0]["stock"] == 8


async def test_new_product_opening_stock_is_a_restock(db, world):
    name = f"B22A-restock-{world['tag']}"
    body = _csv_body(
        [
            {
                "name": name, "category": "top", "price": "300000", "stock": "6",
                "sizes": "S|M|L", "colors": "قرمز:#ff0000|آبی:#0000ff",
                "tags": "جدید|تابستان", "badge": "new", "availability": "in_stock",
            }
        ]
    )
    assert (await _post(world["admin"], body)).status_code == 200
    rows = await _rows(db, "name = :n", {"n": name})
    pid = str(rows[0]["id"])
    assert rows[0]["sizes"] == ["S", "M", "L"]
    assert rows[0]["colors"] == [
        {"name": "قرمز", "hex": "#ff0000"},
        {"name": "آبی", "hex": "#0000ff"},
    ]
    ledger = await _ledger(db, pid)
    assert ledger == [{"change_amount": 6, "reason": "restock"}]

    # the import itself is audited
    audit = (
        await db.execute(
            text(
                "SELECT action, new_values FROM public.audit_logs "
                "WHERE action = 'import_products' ORDER BY created_at DESC LIMIT 1"
            )
        )
    ).mappings().first()
    assert audit is not None
    values = audit["new_values"]
    if isinstance(values, str):
        values = json.loads(values)
    assert values["created"] == 1


async def test_support_cannot_import_and_empty_file_is_a_422(db, world):
    res = await _post(world["support"], _csv_body(
        [{"name": "B22A-x", "category": "top", "price": "1"}]
    ))
    assert res.status_code == 403

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        anon = await client.post(
            "/products/import",
            files={"file": ("products.csv", _csv_body(
                [{"name": "B22A-y", "category": "top", "price": "1"}]
            ), "text/csv")},
        )
        assert anon.status_code == 401

        empty = await client.post(
            "/products/import",
            files={"file": ("products.csv", b"", "text/csv")},
            headers={"Authorization": f"Bearer {world['admin']}"},
        )
        assert empty.status_code == 422
