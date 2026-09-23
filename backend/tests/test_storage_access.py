"""Who may presign a product-image upload (B6.17) and what the ticket limits (B6.18).

`POST /storage/upload-url` used `AdminUser` (admin / super_admin only), so
order_manager — who holds the `catalog` capability and edits products since B5.4b —
could edit a product but not add an image to it. It now follows the catalog
capability, like product create/update. `/storage/sign` (reading images) stays open to
any signed-in user. MinIO is replaced by a fake client: presigning is local signing.

B6.18: the ticket is a presigned **POST policy** whose signed conditions carry the
size ceiling and the image content type, so MinIO — not the browser — refuses an
oversized or non-image upload. The tests decode the policy the way MinIO does.
"""

import base64
import json
from uuid import uuid4

import httpx
import pytest
from minio.credentials import Credentials
from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal, engine, startup_ddl
from app.main import app
from app.routers import storage
from app.security import create_access_token

MAX_BYTES = 5 * 1024 * 1024


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
async def token_for(db):
    ids: list[str] = []

    async def _make(*roles: str) -> str:
        email = f"b617-{uuid4().hex[:8]}@test.local"
        uid = (
            await db.execute(
                text(
                    "INSERT INTO public.users (email, password_hash) VALUES (:e, 'x') RETURNING id"
                ),
                {"e": email},
            )
        ).scalar()
        for role in roles:
            await db.execute(
                text("INSERT INTO public.user_roles (user_id, role) VALUES (:u, :r)"),
                {"u": str(uid), "r": role},
            )
        await db.commit()
        ids.append(str(uid))
        return create_access_token(uid, email, "customer")

    yield _make
    await db.execute(
        text("DELETE FROM public.users WHERE id = ANY(CAST(:ids AS uuid[]))"), {"ids": ids}
    )
    await db.commit()


class _FakeMinio:
    """Presigning is local signing, so the fake signs the policy for real — the test
    can then decode `fields["policy"]` exactly as MinIO does."""

    def presigned_post_policy(self, policy):
        creds = Credentials(settings.minio_access_key, settings.minio_secret_key)
        return policy.form_data(creds, settings.minio_region)

    def presigned_get_object(self, *args, **kwargs):
        return "http://minio.test/get"


@pytest.fixture(autouse=True)
def fake_minio(monkeypatch):
    monkeypatch.setattr(storage, "_client", lambda: _FakeMinio())


async def _post(path: str, token: str | None, body: dict) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return await client.post(path, headers=headers, json=body)


UPLOAD = {"filename": "a.png", "content_type": "image/png"}


@pytest.mark.parametrize(
    ("roles", "expected"),
    [
        ((), 403),  # customer
        (("support",), 403),  # no catalog capability
        (("order_manager",), 200),  # was 403 — edits products, could not add images
        (("admin",), 200),
        (("super_admin",), 200),
    ],
)
async def test_upload_url_follows_the_catalog_capability(token_for, roles, expected):
    res = await _post("/storage/upload-url", await token_for(*roles), UPLOAD)
    assert res.status_code == expected, res.text
    if expected == 200:
        assert res.json()["path"].startswith("uploads/") and res.json()["path"].endswith(".png")
    else:
        assert res.json()["detail"] == "دسترسی لازم برای این بخش را ندارید"


async def test_anonymous_upload_is_401(db):
    assert (await _post("/storage/upload-url", None, UPLOAD)).status_code == 401


def _conditions(res: httpx.Response) -> list:
    """The signed conditions, decoded from the base64 policy MinIO will verify."""
    fields = res.json()["fields"]
    return json.loads(base64.b64decode(fields["policy"]))["conditions"]


async def test_the_policy_carries_the_size_and_type_limits(token_for):
    """B6.18: the old presigned PUT signed no length and no content type, so the
    5 MB / image-only rule lived in the browser only."""
    res = await _post("/storage/upload-url", await token_for("admin"), UPLOAD)
    assert res.status_code == 200, res.text
    body = res.json()
    conditions = _conditions(res)
    # the key is pinned to the path the API hands back, so a form cannot write elsewhere
    assert ["eq", "$key", body["path"]] in conditions
    assert ["content-length-range", 1, MAX_BYTES] in conditions
    assert ["starts-with", "$Content-Type", "image/"] in conditions
    # both fields the policy requires must be in the form the browser is told to send
    assert body["fields"]["key"] == body["path"]
    assert body["fields"]["Content-Type"] == "image/png"
    assert body["max_bytes"] == MAX_BYTES
    assert body["upload_url"].endswith(f"/{settings.minio_bucket}")


@pytest.mark.parametrize(
    "body",
    [
        {"filename": "a.svg", "content_type": "image/svg+xml"},  # extension not allowed
        {"filename": "a.png", "content_type": "text/plain"},  # type not an image
        {"filename": "a.png", "content_type": ""},  # empty type
    ],
)
async def test_a_non_image_request_is_422(token_for, body):
    res = await _post("/storage/upload-url", await token_for("admin"), body)
    assert res.status_code == 422, res.text
    assert res.json()["detail"] == "فرمت تصویر مجاز نیست"


async def test_signing_stays_open_to_any_signed_in_user(token_for):
    res = await _post("/storage/sign", await token_for(), {"paths": ["uploads/a.png", "cat"]})
    assert res.status_code == 200
    assert res.json() == [
        {"path": "uploads/a.png", "url": "http://minio.test/get"},
        {"path": "cat", "url": None},
    ]


async def test_the_catalog_guard_matches_product_editing(token_for):
    """The same role set that may PATCH a product may presign its images."""
    for roles in ((), ("support",), ("order_manager",), ("admin",)):
        token = await token_for(*roles)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            patch = await client.patch(
                "/products/b617-missing", headers={"Authorization": f"Bearer {token}"}, json={}
            )
        upload = await _post("/storage/upload-url", token, UPLOAD)
        # 404 = passed the guard and found no product; 403 = refused by the guard
        assert (patch.status_code != 403) == (upload.status_code == 200), (roles, patch.status_code)
