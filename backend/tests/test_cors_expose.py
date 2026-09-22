"""CORS exposes Content-Disposition to the frontend origin (AB-FE-02).

The admin export buttons download CSV/XLSX through a cross-origin `fetch`
(frontend :5173 → backend :8000) and name the file from the RFC-6266
`Content-Disposition` header. Browsers hide every non-safelisted response
header from script unless it is listed in `Access-Control-Expose-Headers`, so
without it the download silently loses its server-chosen filename.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://sande:sande@localhost:5432/postgres")
os.environ.setdefault("JWT_SECRET", "test-secret")

import httpx  # noqa: E402

from app.main import app  # noqa: E402

FRONTEND_ORIGIN = "http://localhost:5173"


async def _get(path: str, origin: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(path, headers={"Origin": origin})


async def test_allowed_origin_sees_content_disposition():
    res = await _get("/health", FRONTEND_ORIGIN)
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == FRONTEND_ORIGIN
    exposed = res.headers.get("access-control-expose-headers", "").lower()
    assert "content-disposition" in exposed


async def test_unknown_origin_is_not_allowed():
    # Starlette adds its static CORS headers (incl. expose-headers) to every
    # response; the browser only honours them when Allow-Origin matches, so the
    # gate that must stay closed for a foreign origin is Allow-Origin itself.
    res = await _get("/health", "https://evil.example")
    assert "access-control-allow-origin" not in res.headers
