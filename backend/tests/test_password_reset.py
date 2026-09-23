"""Password reset (F2.3).

Pinned here: the forgot endpoint answers identically for unknown, known and
throttled addresses; only the token's SHA-256 is stored; the emailed link resets
the password once, expires, and is superseded by a newer link; the email follows
the B2.1 channel rule (email switch AND configured provider, sent after COMMIT,
never persisted in `notification_deliveries`); a provider failure never fails the
request. Live-DB tests skip when no database is reachable.
"""

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
from app.security import hash_password  # noqa: E402
from app.services import notification_providers as providers  # noqa: E402
from app.services import notifications  # noqa: E402
from app.services.notification_providers import ProviderError  # noqa: E402
from app.services.password_reset import hash_token, reset_email, reset_link  # noqa: E402

OLD_PASSWORD = "old-secret-1"
NEW_PASSWORD = "new-secret-2"
LINK_RE = re.compile(r"/reset-password\?token=([A-Za-z0-9_\-]+)")


# --- pure --------------------------------------------------------------------------


def test_token_is_stored_as_sha256():
    assert hash_token("abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_email_carries_the_link_and_ttl():
    link = reset_link("TOKEN123")
    assert link.endswith("/reset-password?token=TOKEN123")
    assert link.startswith(settings.frontend_url.rstrip("/"))
    subject, body = reset_email(link)
    assert "بازیابی رمز عبور" in subject
    assert link in body and notifications.fa(settings.password_reset_ttl_minutes) in body


# --- fixtures ----------------------------------------------------------------------


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
    await notifications.drain()
    await engine.dispose()


@pytest.fixture
async def user(db):
    email = f"f23-{uuid4().hex[:8]}@test.local"
    uid = (
        await db.execute(
            text("INSERT INTO public.users (email, password_hash) VALUES (:e, :h) RETURNING id"),
            {"e": email, "h": hash_password(OLD_PASSWORD)},
        )
    ).scalar()
    await db.commit()
    try:
        yield {"id": uid, "email": email}
    finally:
        await notifications.drain()
        await db.execute(text("DELETE FROM public.users WHERE id = :u"), {"u": str(uid)})
        await db.commit()


@pytest.fixture
async def email_on(db):
    """Email switch on for the test; restored afterwards."""
    before = await notifications.load_switches(db)
    await db.execute(text("UPDATE public.notification_settings SET email_enabled = true"))
    await db.commit()
    yield
    await db.execute(
        text("UPDATE public.notification_settings SET email_enabled = :e"),
        {"e": before["email"]},
    )
    await db.commit()


class _FakeEmail:
    name = "fake-email"

    def __init__(self) -> None:
        self.is_configured = True
        self.fail = False
        self.sent: list[tuple[str, str, str]] = []

    def configured(self) -> bool:
        return self.is_configured

    async def send(self, recipient: str, subject: str, body: str) -> None:
        if self.fail:
            raise ProviderError("fake-email: down")
        self.sent.append((recipient, subject, body))


@pytest.fixture
def mailbox(monkeypatch):
    fake = _FakeEmail()
    monkeypatch.setattr(providers, "email_provider", lambda: fake)
    return fake


async def _post(path: str, json: dict) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        return await client.post(path, json=json)


async def _forgot(email: str) -> httpx.Response:
    res = await _post("/auth/password/forgot", {"email": email})
    await notifications.drain()
    return res


async def _login(email: str, password: str) -> int:
    return (await _post("/auth/login", {"email": email, "password": password})).status_code


async def _tokens(db, user_id) -> list[dict]:
    await db.commit()
    rows = await db.execute(
        text(
            "SELECT token_hash, used_at, expires_at FROM public.password_reset_tokens "
            "WHERE user_id = :u ORDER BY created_at"
        ),
        {"u": str(user_id)},
    )
    return [dict(r) for r in rows.mappings().all()]


def _token_from(mail: tuple[str, str, str]) -> str:
    match = LINK_RE.search(mail[2])
    assert match, mail[2]
    return match.group(1)


# --- forgot: enumeration safety + storage ---------------------------------------------


async def test_unknown_and_known_addresses_get_the_same_answer(db, user, mailbox, email_on):
    unknown = await _forgot(f"nobody-{uuid4().hex[:6]}@test.local")
    known = await _forgot(user["email"].upper())  # case-insensitive lookup
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()
    assert len(mailbox.sent) == 1 and mailbox.sent[0][0] == user["email"]


async def test_only_the_hash_is_stored_and_nothing_hits_the_outbox(db, user, mailbox, email_on):
    await _forgot(user["email"])
    raw = _token_from(mailbox.sent[0])
    rows = await _tokens(db, user["id"])
    assert len(rows) == 1 and rows[0]["token_hash"] == hash_token(raw)
    dump = (
        await db.execute(
            text(
                "SELECT row_to_json(t)::text FROM public.password_reset_tokens t "
                "WHERE user_id = :u"
            ),
            {"u": str(user["id"])},
        )
    ).scalar()
    assert raw not in dump
    outbox = (
        await db.execute(
            text(
                "SELECT COUNT(*) FROM public.notification_deliveries d "
                "JOIN public.notifications n ON n.id = d.notification_id WHERE n.user_id = :u"
            ),
            {"u": str(user["id"])},
        )
    ).scalar()
    assert outbox == 0  # a reset is email-only and its body is never persisted


async def test_malformed_request_is_422(db):
    assert (await _post("/auth/password/forgot", {"email": "x"})).status_code == 422
    assert (await _post("/auth/password/forgot", {})).status_code == 422


# --- reset --------------------------------------------------------------------------


async def test_link_resets_the_password_once(db, user, mailbox, email_on):
    await _forgot(user["email"])
    raw = _token_from(mailbox.sent[0])
    ok = await _post("/auth/password/reset", {"token": raw, "password": NEW_PASSWORD})
    assert ok.status_code == 200 and ok.json() == {"ok": True}
    assert await _login(user["email"], NEW_PASSWORD) == 200
    assert await _login(user["email"], OLD_PASSWORD) == 401
    again = await _post("/auth/password/reset", {"token": raw, "password": "third-secret"})
    assert again.status_code == 400
    assert "منقضی" in again.json()["detail"]
    assert await _login(user["email"], NEW_PASSWORD) == 200


async def test_expired_link_is_rejected(db, user, mailbox, email_on):
    await _forgot(user["email"])
    raw = _token_from(mailbox.sent[0])
    await db.execute(
        text(
            "UPDATE public.password_reset_tokens SET expires_at = now() - interval '1 second' "
            "WHERE token_hash = :h"
        ),
        {"h": hash_token(raw)},
    )
    await db.commit()
    res = await _post("/auth/password/reset", {"token": raw, "password": NEW_PASSWORD})
    assert res.status_code == 400
    assert await _login(user["email"], OLD_PASSWORD) == 200


async def test_a_newer_link_supersedes_the_older_one(db, user, mailbox, email_on):
    await _forgot(user["email"])
    await _forgot(user["email"])
    first, second = (_token_from(m) for m in mailbox.sent)
    assert first != second
    assert (
        await _post("/auth/password/reset", {"token": first, "password": NEW_PASSWORD})
    ).status_code == 400
    assert (
        await _post("/auth/password/reset", {"token": second, "password": NEW_PASSWORD})
    ).status_code == 200


async def test_unknown_token_and_bad_password_are_rejected(db, user):
    bogus = {"token": "x" * 43, "password": NEW_PASSWORD}
    assert (await _post("/auth/password/reset", bogus)).status_code == 400
    assert (
        await _post("/auth/password/reset", {"token": "x" * 43, "password": "123"})
    ).status_code == 422
    assert (
        await _post("/auth/password/reset", {"token": "short", "password": NEW_PASSWORD})
    ).status_code == 422


# --- throttling ---------------------------------------------------------------------


async def test_throttled_requests_look_identical_and_send_nothing(db, user, mailbox, email_on):
    tries = settings.password_reset_max_per_hour + 2
    answers = [await _forgot(user["email"]) for _ in range(tries)]
    assert {r.status_code for r in answers} == {202}
    assert len({r.text for r in answers}) == 1
    assert len(mailbox.sent) == settings.password_reset_max_per_hour
    assert len(await _tokens(db, user["id"])) == settings.password_reset_max_per_hour


# --- channel rule (B2.1) --------------------------------------------------------------


async def test_email_switch_off_sends_nothing_but_answers_the_same(db, user, mailbox):
    before = await notifications.load_switches(db)
    await db.execute(text("UPDATE public.notification_settings SET email_enabled = false"))
    await db.commit()
    try:
        res = await _forgot(user["email"])
    finally:
        await db.execute(
            text("UPDATE public.notification_settings SET email_enabled = :e"),
            {"e": before["email"]},
        )
        await db.commit()
    assert res.status_code == 202
    assert mailbox.sent == []


async def test_unconfigured_smtp_sends_nothing(db, user, mailbox, email_on):
    mailbox.is_configured = False
    res = await _forgot(user["email"])
    assert res.status_code == 202 and mailbox.sent == []


async def test_provider_failure_never_fails_the_request(db, user, mailbox, email_on):
    mailbox.fail = True
    res = await _forgot(user["email"])
    assert res.status_code == 202
    assert len(await _tokens(db, user["id"])) == 1  # the link exists; the user can ask again


async def test_rollback_sends_nothing(db, user, mailbox, email_on):
    from app.services.password_reset import request_reset

    await request_reset(db, user["email"])
    assert db.info.get("notification_private_emails")
    await db.rollback()
    await notifications.drain()
    assert mailbox.sent == []
    assert await _tokens(db, user["id"]) == []
