"""FastAPI application entrypoint.

Sole backend for the SÂNDÉ store: own auth (JWT), products, orders, coupons,
payments, storage (MinIO), admin.
"""

import logging
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.config import settings
from app.routers import (
    addresses,
    admin,
    auth,
    checkout,
    contact,
    coupons,
    exports,
    favorites,
    health,
    notifications,
    orders,
    payments,
    products,
    profile,
    reviews,
    search,
    stock,
    storage,
    webhooks,
)
from app.services import audit
from app.services.client_ip import resolve_client_ip

logging.basicConfig(level=logging.INFO)

# B5.1e: the API runs no DDL and owns no object. Its connection is the DML-only
# role in `DATABASE_URL`; the schema comes from the one-shot `db-init` job, which
# runs `startup_ddl()` (and the seeds) as the schema owner. The compose `backend`
# service therefore starts after `db-init` has exited 0 — see infra/docker-compose.yml.
app = FastAPI(
    title="SÂNDÉ Backend",
    description=(
        "Auth · Catalog · Coupons · Payments · Stock · Storage (MinIO) · Contact · "
        "Notifications"
    ),
    version="0.3.0",
)

# The frontend dev server and production origin both need to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # the admin export downloads (AB-FE-02) read the RFC-6266 filename; a
    # cross-origin fetch only sees response headers that are exposed here
    expose_headers=["Content-Disposition"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(products.router)
app.include_router(reviews.router)
app.include_router(addresses.router)
app.include_router(favorites.router)
app.include_router(orders.router)
app.include_router(admin.router)
app.include_router(storage.router)
app.include_router(search.router)
app.include_router(stock.router)
app.include_router(contact.router)
app.include_router(coupons.router)
app.include_router(checkout.router)
app.include_router(payments.router)
app.include_router(exports.router)
app.include_router(notifications.router)
app.include_router(webhooks.router)


@app.middleware("http")
async def capture_client_ip(request: Request, call_next):
    """Record the caller's IP for the audit trail (B5.1a) and the contact throttle (B3.11).

    Runs first (registered last). `resolve_client_ip` believes X-Forwarded-For
    only from a configured trusted proxy (`TRUSTED_PROXIES`, none by default —
    compose publishes the backend directly), else it uses the socket peer. The
    value lands in `audit.client_ip_ctx`.
    """
    ip = resolve_client_ip(
        request.client.host if request.client else None,
        request.headers.get("x-forwarded-for"),
    )
    audit.client_ip_ctx.set(ip)
    return await call_next(request)


@app.middleware("http")
async def zarinpal_status_mapping(request: Request, call_next):
    """Map Zarinpal's Status=NOK query param to the internal ok=false contract."""
    if request.url.path == "/payments/zarinpal/callback":
        qs = parse_qs(urlparse(str(request.url)).query)
        if qs.get("Status", ["OK"])[0] == "NOK":
            request.scope["query_string"] = b"ok=false&authority=" + _authority_from(qs).encode()
    return await call_next(request)


def _authority_from(qs: dict) -> str:
    return qs.get("Authority", [""])[0]


# Friendly root → docs
@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")
