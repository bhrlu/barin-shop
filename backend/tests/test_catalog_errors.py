"""Catalog and storage handlers translate only the failure they expect (B6.9a).

`routers/products.py` turned *any* failure of four CRUD handlers into a 409
"duplicate" / 400, and `routers/storage.py` turned any exception into a 502 or a
silent `url: null`. Now only SQLSTATE 23505 keeps the handler's duplicate answer and
only MinIO / network errors keep the storage answer; everything else is a fault that
surfaces as a 500. Faults are injected with a temporary trigger that raises a chosen
SQLSTATE for marker rows only, and with a fake MinIO client.
"""

from uuid import uuid4

import httpx
import pytest
from minio.error import MinioException
from sqlalchemy import text

from app.db import SessionLocal, engine, startup_ddl
from app.main import app
from app.routers import storage
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
    email = f"b69a-{uuid4().hex[:8]}@test.local"
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
    await db.execute(text("DELETE FROM public.users WHERE id = :u"), {"u": str(uid)})
    await db.execute(text("DELETE FROM public.products WHERE name LIKE 'B69A-%'"))
    await db.commit()


@pytest.fixture
async def faults(db):
    """Triggers: marker names / sizes raise the named SQLSTATE."""
    fn = f"b69a_{uuid4().hex[:8]}"
    await db.execute(
        text(
            f"CREATE FUNCTION public.{fn}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            "IF TG_TABLE_NAME = 'products' THEN "
            "  IF NEW.name LIKE 'B69A-UNIQUE%' THEN RAISE EXCEPTION 'x' USING ERRCODE = "
            "'unique_violation'; END IF; "
            "  IF NEW.name LIKE 'B69A-CHECK%' THEN RAISE EXCEPTION 'x' USING ERRCODE = "
            "'check_violation'; END IF; "
            "  IF NEW.name LIKE 'B69A-OTHER%' THEN RAISE EXCEPTION 'x'; END IF; "
            "ELSE "
            "  IF NEW.size = 'B69A-CHECK' THEN RAISE EXCEPTION 'x' USING ERRCODE = "
            "'check_violation'; END IF; "
            "END IF; RETURN NEW; END $$"
        )
    )
    for table in ("products", "product_variants"):
        await db.execute(
            text(
                f"CREATE TRIGGER {fn}_{table} BEFORE INSERT OR UPDATE ON public.{table} "
                f"FOR EACH ROW EXECUTE FUNCTION public.{fn}()"
            )
        )
    await db.commit()
    yield
    for table in ("products", "product_variants"):
        await db.execute(text(f"DROP TRIGGER IF EXISTS {fn}_{table} ON public.{table}"))
    await db.execute(text(f"DROP FUNCTION IF EXISTS public.{fn}()"))
    await db.commit()


async def _call(method: str, path: str, token: str, **kw) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        return await client.request(
            method, path, headers={"Authorization": f"Bearer {token}"}, **kw
        )


def _product(name: str) -> dict:
    return {"name": name, "category": "test", "price": 1000, "sizes": ["M"], "stock": 1}


async def test_product_create_keeps_the_duplicate_answer_only(db, admin, faults):
    dup = await _call("POST", "/products", admin, json=_product("B69A-UNIQUE"))
    assert dup.status_code == 400
    for fault in ("B69A-CHECK", "B69A-OTHER"):
        res = await _call("POST", "/products", admin, json=_product(fault))
        assert res.status_code == 500, (fault, res.status_code, res.text)
    ok = await _call("POST", "/products", admin, json=_product("B69A-FINE"))
    assert ok.status_code == 201


async def test_product_update_keeps_the_duplicate_answer_only(db, admin, faults):
    pid = (await _call("POST", "/products", admin, json=_product("B69A-FINE"))).json()["id"]
    dup = await _call("PATCH", f"/products/{pid}", admin, json={"name": "B69A-UNIQUE"})
    assert dup.status_code == 400
    bug = await _call("PATCH", f"/products/{pid}", admin, json={"name": "B69A-CHECK"})
    assert bug.status_code == 500


async def test_variant_duplicate_is_409_and_other_faults_are_500(db, admin, faults):
    pid = (await _call("POST", "/products", admin, json=_product("B69A-FINE"))).json()["id"]
    body = {"size": "M", "color": "مشکی", "stock": 1}
    first = await _call("POST", f"/products/{pid}/variants", admin, json=body)
    assert first.status_code == 201, first.text
    dup = await _call("POST", f"/products/{pid}/variants", admin, json=body)
    assert dup.status_code == 409 and "قبلاً ثبت شده" in dup.json()["detail"]
    bug = await _call(
        "POST", f"/products/{pid}/variants", admin, json={**body, "size": "B69A-CHECK"}
    )
    assert bug.status_code == 500  # used to be reported as a duplicate

    other = await _call("POST", f"/products/{pid}/variants", admin, json={**body, "size": "L"})
    vid = other.json()["id"]
    clash = await _call("PATCH", f"/variants/{vid}", admin, json={"size": "M"})
    assert clash.status_code == 409  # moving onto an existing size×colour
    bad = await _call("PATCH", f"/variants/{vid}", admin, json={"size": "B69A-CHECK"})
    assert bad.status_code == 500


class _FakeMinio:
    def __init__(self, error: Exception | None) -> None:
        self.error = error

    def presigned_post_policy(self, *args, **kwargs):
        if self.error:
            raise self.error
        return {"policy": "policy", "x-amz-signature": "sig"}

    def presigned_get_object(self, *args, **kwargs):
        if self.error:
            raise self.error
        return "http://minio.test/get"


@pytest.mark.parametrize(
    ("error", "upload_status", "signed"),
    [
        (None, 200, "http://minio.test/get"),
        (MinioException("storage down"), 502, None),
        (OSError("connection refused"), 502, None),
    ],
)
async def test_storage_errors_keep_their_answer(
    db, admin, monkeypatch, error, upload_status, signed
):
    monkeypatch.setattr(storage, "_client", lambda: _FakeMinio(error))
    up = await _call("POST", "/storage/upload-url", admin, json={"filename": "a.jpg"})
    assert up.status_code == upload_status
    sign = await _call("POST", "/storage/sign", admin, json={"paths": ["uploads/a.jpg"]})
    assert sign.status_code == 200 and sign.json()[0]["url"] == signed


async def test_a_bug_in_storage_code_is_not_masked(db, admin, monkeypatch):
    monkeypatch.setattr(storage, "_client", lambda: _FakeMinio(AttributeError("bug")))
    up = await _call("POST", "/storage/upload-url", admin, json={"filename": "a.jpg"})
    assert up.status_code == 500  # was a 502 «خطا در ساخت لینک آپلود»
    sign = await _call("POST", "/storage/sign", admin, json={"paths": ["uploads/a.jpg"]})
    assert sign.status_code == 500  # was a silent `url: null`
