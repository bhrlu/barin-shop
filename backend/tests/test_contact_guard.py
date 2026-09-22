"""Contact-form abuse guard (B3.11, decision D1) and client-IP resolution.

`POST /contact` is public. D1 fixes the rules: at most 5 attempts per IP per
10 minutes, accepted and rejected attempts both count, a filled honeypot field
is rejected, guests and signed-in users share the boundary, and the answers do
not reveal how the limit works. The limit is only as good as the IP it is keyed
on, so `X-Forwarded-For` must be ignored unless it comes from a trusted proxy.

The HTTP tests run the app in-process (ASGI) against the live Postgres of the
docker-compose stack and skip when none is reachable. Each test uses its own
documentation-range IPv6 address as the socket peer, so they never touch the
bucket a developer's browser is using, and they clean up their rows.
"""

import asyncio
import ipaddress
import os
import re
from uuid import uuid4

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://sande:sande@localhost:5432/postgres"
)
os.environ.setdefault("JWT_SECRET", "test-secret")

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import SessionLocal, engine, startup_ddl  # noqa: E402
from app.main import app  # noqa: E402
from app.security import create_access_token  # noqa: E402
from app.services import client_ip  # noqa: E402
from app.services.client_ip import parse_networks, resolve_client_ip  # noqa: E402

LIMIT = settings.contact_rate_limit


# --- client IP resolution (pure) ---------------------------------------------


class TestResolveClientIp:
    TRUSTED = parse_networks("10.0.0.0/8, 172.23.0.1")

    def test_no_forwarded_header_uses_the_peer(self):
        assert resolve_client_ip("1.2.3.4", None, []) == "1.2.3.4"

    def test_forwarded_header_from_an_untrusted_peer_is_ignored(self):
        # the spoof this task exists to stop: any client can send the header
        assert resolve_client_ip("1.2.3.4", "9.9.9.9", []) == "1.2.3.4"
        assert resolve_client_ip("8.8.8.8", "5.5.5.5", self.TRUSTED) == "8.8.8.8"

    def test_default_configuration_trusts_no_proxy(self):
        assert client_ip.TRUSTED_PROXIES == parse_networks(settings.trusted_proxies)
        if not settings.trusted_proxies:
            assert resolve_client_ip("1.2.3.4", "9.9.9.9") == "1.2.3.4"

    def test_trusted_proxy_chain_is_walked_right_to_left(self):
        # the client may prepend anything; the proxy appended the real address last
        assert resolve_client_ip("10.0.0.5", "6.6.6.6, 5.5.5.5", self.TRUSTED) == "5.5.5.5"
        assert (
            resolve_client_ip("10.0.0.5", "6.6.6.6, 5.5.5.5, 10.0.0.9", self.TRUSTED)
            == "5.5.5.5"
        )

    def test_ipv6_hop(self):
        assert resolve_client_ip("10.0.0.5", "2001:db8::1", self.TRUSTED) == "2001:db8::1"

    def test_malformed_hop_falls_back_to_the_peer(self):
        assert resolve_client_ip("10.0.0.5", "garbage", self.TRUSTED) == "10.0.0.5"

    def test_all_hops_trusted_means_an_internal_client(self):
        assert resolve_client_ip("10.0.0.5", "10.1.1.1", self.TRUSTED) == "10.1.1.1"

    def test_no_peer(self):
        assert resolve_client_ip(None, "5.5.5.5", self.TRUSTED) is None


# --- POST /contact guard (live database) --------------------------------------


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
async def peer(db):
    """A fresh socket-peer address; its attempts and messages are removed afterwards."""
    ip = _addr(f"2001:db8::{uuid4().hex[:4]}:{uuid4().hex[:4]}")
    marker = f"b311-{uuid4().hex[:8]}@test.local"
    try:
        yield {"ip": ip, "marker": marker}
    finally:
        await db.execute(text("DELETE FROM public.contact_attempts WHERE ip = :ip"), {"ip": ip})
        await db.execute(
            text("DELETE FROM public.contact_messages WHERE contact = :c"), {"c": marker}
        )
        await db.commit()


def _addr(text_: str) -> str:
    """Canonical form, as the resolver stores it (`::0af1` → `::af1`)."""
    return str(ipaddress.ip_address(text_))


def _client(ip: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False, client=(ip, 40000)),
        base_url="http://test",
    )


def _body(marker: str, **extra) -> dict:
    return {"name": "آزمون", "contact": marker, "message": "سلام، سؤالی درباره سایز دارم.", **extra}


async def _post(ip: str, body: dict, headers: dict | None = None) -> httpx.Response:
    async with _client(ip) as client:
        return await client.post("/contact", json=body, headers=headers or {})


async def _stored(db, marker: str) -> int:
    return (
        await db.execute(
            text("SELECT COUNT(*) FROM public.contact_messages WHERE contact = :c"), {"c": marker}
        )
    ).scalar_one()


async def _attempts(db, ip: str) -> list[str]:
    rows = await db.execute(
        text("SELECT outcome FROM public.contact_attempts WHERE ip = :ip ORDER BY id"), {"ip": ip}
    )
    return [r[0] for r in rows.all()]


async def test_limit_per_window_then_generic_429(db, peer):
    for _ in range(LIMIT):
        assert (await _post(peer["ip"], _body(peer["marker"]))).status_code == 201
    blocked = await _post(peer["ip"], _body(peer["marker"]))
    assert blocked.status_code == 429
    detail = blocked.json()["detail"]
    # generic: no counts, window, header or mechanism leaked
    assert not re.search(r"[0-9۰-۹]", detail)
    assert not re.search(r"(?i)rate|limit|ip|redis|window", detail)
    assert "retry-after" not in blocked.headers
    assert await _stored(db, peer["marker"]) == LIMIT
    assert await _attempts(db, peer["ip"]) == ["accepted"] * LIMIT + ["throttled"]


async def test_throttled_attempts_keep_counting(db, peer):
    for _ in range(LIMIT + 3):
        await _post(peer["ip"], _body(peer["marker"]))
    assert (await _post(peer["ip"], _body(peer["marker"]))).status_code == 429
    assert await _stored(db, peer["marker"]) == LIMIT


async def test_window_slides(db, peer):
    # five attempts just outside the window no longer count
    for _ in range(LIMIT):
        await db.execute(
            text(
                "INSERT INTO public.contact_attempts (ip, outcome, created_at) "
                "VALUES (:ip, 'accepted', now() - make_interval(secs => :age))"
            ),
            {"ip": peer["ip"], "age": settings.contact_rate_window_seconds + 1},
        )
    await db.commit()
    assert (await _post(peer["ip"], _body(peer["marker"]))).status_code == 201
    # …while the same five inside the window would block
    await db.execute(
        text("DELETE FROM public.contact_attempts WHERE ip = :ip"), {"ip": peer["ip"]}
    )
    for _ in range(LIMIT):
        await db.execute(
            text("INSERT INTO public.contact_attempts (ip, outcome) VALUES (:ip, 'accepted')"),
            {"ip": peer["ip"]},
        )
    await db.commit()
    assert (await _post(peer["ip"], _body(peer["marker"]))).status_code == 429


async def test_honeypot_is_rejected_and_not_stored(db, peer):
    res = await _post(peer["ip"], _body(peer["marker"], website="http://spam.example"))
    assert res.status_code == 400
    assert "honeypot" not in res.text.lower() and "website" not in res.text.lower()
    assert await _stored(db, peer["marker"]) == 0
    assert await _attempts(db, peer["ip"]) == ["honeypot"]


async def test_empty_or_blank_honeypot_is_a_normal_message(db, peer):
    assert (await _post(peer["ip"], _body(peer["marker"], website=""))).status_code == 201
    assert (await _post(peer["ip"], _body(peer["marker"], website="   "))).status_code == 201
    assert (await _post(peer["ip"], _body(peer["marker"]))).status_code == 201
    assert await _stored(db, peer["marker"]) == 3


async def test_rejected_attempts_count_toward_the_limit(db, peer):
    for _ in range(3):
        await _post(peer["ip"], _body(peer["marker"], website="spam"))
    for _ in range(LIMIT - 3):
        assert (await _post(peer["ip"], _body(peer["marker"]))).status_code == 201
    assert (await _post(peer["ip"], _body(peer["marker"]))).status_code == 429
    assert await _stored(db, peer["marker"]) == LIMIT - 3


async def test_schema_errors_are_not_attempts(db, peer):
    res = await _post(peer["ip"], {"name": "x", "contact": "y", "message": "z"})
    assert res.status_code == 422
    assert await _attempts(db, peer["ip"]) == []


async def test_limit_is_per_ip(db, peer):
    for _ in range(LIMIT + 1):
        await _post(peer["ip"], _body(peer["marker"]))
    other = _addr(f"2001:db8::{uuid4().hex[:4]}:{uuid4().hex[:4]}")
    try:
        assert (await _post(other, _body(peer["marker"]))).status_code == 201
    finally:
        await db.execute(text("DELETE FROM public.contact_attempts WHERE ip = :ip"), {"ip": other})
        await db.commit()


async def test_spoofed_forwarded_for_does_not_open_new_buckets(db, peer):
    codes = [
        (
            await _post(
                peer["ip"], _body(peer["marker"]), {"X-Forwarded-For": f"198.51.100.{i}"}
            )
        ).status_code
        for i in range(LIMIT + 2)
    ]
    assert codes == [201] * LIMIT + [429, 429]
    assert set(await _attempts(db, peer["ip"])) == {"accepted", "throttled"}


async def test_forwarded_for_from_a_trusted_proxy_is_honoured(db, peer, monkeypatch):
    monkeypatch.setattr(client_ip, "TRUSTED_PROXIES", parse_networks(peer["ip"]))
    clients = [_addr(f"2001:db8:1::{uuid4().hex[:4]}") for _ in range(LIMIT + 2)]
    try:
        codes = [
            (
                await _post(peer["ip"], _body(peer["marker"]), {"X-Forwarded-For": c})
            ).status_code
            for c in clients
        ]
        assert codes == [201] * len(clients)  # each real client has its own bucket
    finally:
        await db.execute(
            text("DELETE FROM public.contact_attempts WHERE ip = ANY(:ips)"), {"ips": clients}
        )
        await db.commit()


async def test_signed_in_callers_share_the_boundary(db, peer):
    user_id = (
        await db.execute(text("SELECT id FROM public.users ORDER BY created_at LIMIT 1"))
    ).scalar_one()
    token = create_access_token(user_id, "b311@test.local", "customer")
    auth = {"Authorization": f"Bearer {token}"}
    for i in range(LIMIT):
        res = await _post(peer["ip"], _body(peer["marker"]), auth if i % 2 else None)
        assert res.status_code == 201
    assert (await _post(peer["ip"], _body(peer["marker"]), auth)).status_code == 429


async def test_parallel_burst_cannot_slip_past_the_limit(db, peer):
    burst = LIMIT * 2
    responses = await asyncio.gather(
        *[_post(peer["ip"], _body(peer["marker"])) for _ in range(burst)]
    )
    codes = sorted(r.status_code for r in responses)
    assert codes == [201] * LIMIT + [429] * LIMIT
    assert await _stored(db, peer["marker"]) == LIMIT
