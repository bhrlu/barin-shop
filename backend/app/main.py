"""FastAPI application entrypoint.

Sole backend for the SÂNDÉ store: own auth (JWT), products, orders, coupons,
payments, storage (MinIO), admin.
"""

import logging
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.config import settings
from app.db import startup_ddl
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
    orders,
    payments,
    products,
    reviews,
    search,
    stock,
    storage,
)
from app.services import audit

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_ddl()
    yield


app = FastAPI(
    title="SÂNDÉ Backend",
    description="Auth · Catalog · Coupons · Payments · Stock · Storage (MinIO) · Contact",
    version="0.3.0",
    lifespan=lifespan,
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
)

app.include_router(health.router)
app.include_router(auth.router)
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


@app.middleware("http")
async def capture_client_ip(request: Request, call_next):
    """Record the caller's IP for the audit trail (B5.1a).

    Runs first (registered last): trusts X-Forwarded-For when present — the
    backend always sits behind the compose proxy / loopback — and falls back to
    the socket peer. The value lands in audit_logs.ip_address via
    `audit.client_ip_ctx` whenever a privileged mutation writes an entry.
    """
    xff = request.headers.get("x-forwarded-for")
    ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else None)
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
