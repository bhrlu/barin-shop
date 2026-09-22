"""Notification infrastructure (B2.1, decision D2).

What is pinned here:

* the in-app inbox API — own rows only, newest first, paginated, unread
  filter/count, idempotent mark-read, read-all, 401/404 paths;
* every live business event (order created / paid / shipped / cancelled,
  refund approved / settled) writes exactly one notification, however often the
  transition is repeated, and a rolled-back transaction leaves none;
* the SMS/email switches — internal notifications never depend on them, a
  channel sends only when switched on AND its provider is configured, and a
  missing or failing provider never fails the order/payment/refund;
* outbox retries are safe (a `sent` row is never re-sent);
* only admin/super_admin may read or change the switches;
* the Kavenegar/SMTP adapters, against a stub transport / stub SMTP class only
  (no real credentials exist — nothing here talks to the real services).

The HTTP tests run the app in-process against the live Postgres of the
docker-compose stack and skip when none is reachable. Each test creates its own
users/products and removes them (notifications cascade from the user). The
global switches are restored after every test that touches them.
"""

import os
import smtplib
from urllib.parse import parse_qsl
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
from app.services import notification_providers as providers  # noqa: E402
from app.services import notifications  # noqa: E402
from app.services.notification_providers import (  # noqa: E402
    KavenegarSmsProvider,
    ProviderError,
    SmtpEmailProvider,
)

ADDRESS = {
    "full_name": "آزمون اعلان",
    "phone": "۰۹۱۲۱۱۱۲۲۳۳",
    "province": "تهران",
    "city": "تهران",
    "line": "خیابان آزمون، پلاک ۲",
    "postal_code": "1234567890",
}


# --- pure helpers ---------------------------------------------------------------


class TestMessages:
    def test_digits_and_money_follow_the_storefront_format(self):
        assert notifications.fa(260922) == "۲۶۰۹۲۲"
        assert notifications.toman(1_250_000) == "۱,۲۵۰,۰۰۰"

    def test_phone_is_normalised_to_ascii(self):
        assert notifications.normalize_phone("۰۹۱۲ ۱۱۱-۲۲۳۳") == "09121112233"
        assert notifications.normalize_phone("+98 912 111 2233") == "+989121112233"
        assert notifications.normalize_phone("") is None
        assert notifications.normalize_phone(None) is None

    def test_shipped_message_keeps_the_tracking_code_copyable(self):
        order = {"order_number": "2609220001", "total": 1, "tracking_code": "TRK-42"}
        text_ = notifications.order_message("shipped", order)
        assert "۲۶۰۹۲۲۰۰۰۱" in text_ and "TRK-42" in text_

    def test_cancelled_paid_order_points_at_the_refund(self):
        paid = {"order_number": "1", "total": 1, "payment_status": "paid"}
        unpaid = {**paid, "payment_status": "unpaid"}
        assert "بازپرداخت" in notifications.order_message("cancelled", paid)
        assert "بازپرداخت" not in notifications.order_message("cancelled", unpaid)

    def test_settled_refund_carries_the_bank_code(self):
        refund = {"order_number": "7", "amount": 189_000, "bank_tracking_code": "PAYA-9"}
        text_ = notifications.refund_message("settled", refund)
        assert "۱۸۹,۰۰۰" in text_ and "PAYA-9" in text_


# --- provider adapters (stub transports only) ---------------------------------------


def _kavenegar(handler, key: str = "SECRET-KEY-123", sender: str = "10004346"):
    return KavenegarSmsProvider(key, sender, transport=httpx.MockTransport(handler))


class TestKavenegar:
    async def test_sends_the_documented_request(self):
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["form"] = dict(parse_qsl(request.content.decode()))
            return httpx.Response(200, json={"return": {"status": 200}, "entries": []})

        await _kavenegar(handler).send("09121112233", "سلام")
        assert seen["url"] == "https://api.kavenegar.com/v1/SECRET-KEY-123/sms/send.json"
        assert seen["form"] == {"receptor": "09121112233", "message": "سلام", "sender": "10004346"}

    async def test_rejection_is_a_provider_error_without_the_key(self):
        def handler(request):
            return httpx.Response(418, json={"return": {"status": 418, "message": "اعتبار"}})

        with pytest.raises(ProviderError) as exc:
            await _kavenegar(handler).send("09121112233", "x")
        assert "418" in str(exc.value)
        assert "SECRET-KEY-123" not in str(exc.value)

    async def test_network_failure_hides_the_key_in_the_url(self):
        def handler(request):
            raise httpx.ConnectError("connection refused", request=request)

        with pytest.raises(ProviderError) as exc:
            await _kavenegar(handler).send("09121112233", "x")
        assert "SECRET-KEY-123" not in str(exc.value)
        assert exc.value.__cause__ is None and exc.value.__suppress_context__

    async def test_garbage_response_is_a_provider_error(self):
        with pytest.raises(ProviderError):
            await _kavenegar(lambda r: httpx.Response(502, text="<html>")).send("0912", "x")

    async def test_unconfigured_never_calls_out(self):
        called = []

        def handler(request):
            called.append(request)
            return httpx.Response(200, json={"return": {"status": 200}})

        provider = _kavenegar(handler, key="")
        assert not provider.configured()
        with pytest.raises(ProviderError):
            await provider.send("09121112233", "x")
        assert called == []


class _FakeSMTP:
    instances: list["_FakeSMTP"] = []
    fail = False

    def __init__(self, host, port, timeout):
        self.host, self.port, self.calls, self.sent = host, port, [], []
        _FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.calls.append("starttls")

    def login(self, username, password):
        self.calls.append(("login", username))

    def send_message(self, msg):
        if _FakeSMTP.fail:
            raise smtplib.SMTPRecipientsRefused({msg["To"]: (550, b"no such user")})
        self.sent.append(msg)


class TestSmtp:
    @pytest.fixture(autouse=True)
    def fake_smtp(self, monkeypatch):
        _FakeSMTP.instances, _FakeSMTP.fail = [], False
        monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
        monkeypatch.setattr(smtplib, "SMTP_SSL", _FakeSMTP)

    def _provider(self, **kw):
        return SmtpEmailProvider(
            "smtp.example.test", 587, "mailer", "pa55word!", "shop@example.test", **kw
        )

    async def test_sends_with_starttls_and_login(self):
        await self._provider().send("a@example.test", "موضوع", "متن")
        smtp = _FakeSMTP.instances[0]
        assert (smtp.host, smtp.port) == ("smtp.example.test", 587)
        assert smtp.calls == ["starttls", ("login", "mailer")]
        msg = smtp.sent[0]
        assert (msg["From"], msg["To"], msg["Subject"]) == (
            "shop@example.test",
            "a@example.test",
            "موضوع",
        )
        assert msg.get_content().strip() == "متن"

    async def test_implicit_ssl_skips_starttls(self):
        await self._provider(use_ssl=True).send("a@example.test", "s", "b")
        assert "starttls" not in _FakeSMTP.instances[0].calls

    async def test_failure_is_a_provider_error_without_the_password(self):
        _FakeSMTP.fail = True
        with pytest.raises(ProviderError) as exc:
            await self._provider().send("a@example.test", "s", "b")
        assert "SMTPRecipientsRefused" in str(exc.value)
        assert "pa55word!" not in str(exc.value)

    def test_unconfigured_without_host_or_sender(self):
        assert not SmtpEmailProvider("", from_address="x@y").configured()
        assert not SmtpEmailProvider("smtp.example.test").configured()


def test_missing_credentials_is_a_valid_configuration():
    """No real credentials exist: the default factories must say so, not fail."""
    if not settings.kavenegar_api_key:
        assert providers.sms_provider().configured() is False
    if not (settings.smtp_host and settings.smtp_from):
        assert providers.email_provider().configured() is False


# --- live database fixtures -------------------------------------------------------------


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
async def switches(db):
    """Restore the store-wide switches whatever the test set them to."""
    before = await notifications.load_switches(db)
    await db.commit()
    yield
    await _set_switches(db, sms=before["sms"], email=before["email"])


async def _set_switches(db, *, sms: bool, email: bool) -> None:
    await db.execute(
        text("UPDATE public.notification_settings SET sms_enabled = :s, email_enabled = :e"),
        {"s": sms, "e": email},
    )
    await db.commit()


@pytest.fixture
async def people(db):
    """Two customers (A has a profile phone, B has none) + staff of every role."""
    created: dict = {}

    async def make(label: str, role: str | None = None, phone: str | None = None) -> dict:
        email = f"b21-{label}-{uuid4().hex[:8]}@test.local"
        uid = (
            await db.execute(
                text(
                    "INSERT INTO public.users (email, password_hash) VALUES (:e, 'x') RETURNING id"
                ),
                {"e": email},
            )
        ).scalar()
        await db.execute(
            text("INSERT INTO public.profiles (id, full_name, phone) VALUES (:u, :n, :p)"),
            {"u": str(uid), "n": label, "p": phone},
        )
        if role:
            await db.execute(
                text("INSERT INTO public.user_roles (user_id, role) VALUES (:u, :r)"),
                {"u": str(uid), "r": role},
            )
        created[label] = {
            "id": uid,
            "email": email,
            "token": create_access_token(uid, email, "customer"),
        }
        return created[label]

    await make("a", phone="۰۹۱۲ ۳۴۵ ۶۷۸۹")
    await make("b")
    for role in ("admin", "super_admin", "order_manager", "support"):
        await make(role, role=role)
    await db.commit()
    try:
        yield created
    finally:
        await notifications.drain()
        ids = [str(p["id"]) for p in created.values()]
        # audit rows only SET NULL on user delete — drop the ones these actors wrote
        await db.execute(
            text("DELETE FROM public.audit_logs WHERE admin_id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": ids},
        )
        await db.execute(
            text("DELETE FROM public.users WHERE id = ANY(CAST(:ids AS uuid[]))"), {"ids": ids}
        )
        await db.commit()


@pytest.fixture
async def product(db):
    pid = f"test-b21-{uuid4().hex[:8]}"
    await db.execute(
        text(
            "INSERT INTO public.products (id, name, category, price, sizes, stock, active) "
            "VALUES (:pid, 'B2.1 test', 'test', 100000, ARRAY['M'], 10, true)"
        ),
        {"pid": pid},
    )
    await db.commit()
    try:
        yield pid
    finally:
        await notifications.drain()
        # orders reference products only through order_items (SET NULL / cascade)
        await db.execute(text("DELETE FROM public.products WHERE id = :pid"), {"pid": pid})
        await db.commit()


class _FakeChannel:
    def __init__(self, name: str) -> None:
        self.name = name
        self.is_configured = True
        self.fail = False
        self.sent: list[tuple] = []

    def configured(self) -> bool:
        return self.is_configured

    async def send(self, recipient: str, *content: str) -> None:
        if self.fail:
            raise ProviderError(f"{self.name}: down")
        self.sent.append((recipient, *content))


@pytest.fixture
def fakes(monkeypatch):
    sms, email = _FakeChannel("fake-sms"), _FakeChannel("fake-email")
    monkeypatch.setattr(providers, "sms_provider", lambda: sms)
    monkeypatch.setattr(providers, "email_provider", lambda: email)
    return sms, email


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _call(method: str, path: str, token: str | None = None, **kw) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with _client() as client:
        return await client.request(method, path, headers=headers, **kw)


async def _checkout(token: str, product_id: str, qty: int = 1) -> httpx.Response:
    return await _call(
        "POST",
        "/checkout",
        token,
        json={
            "lines": [{"product_id": product_id, "size": "M", "color": "مشکی", "quantity": qty}],
            "address": ADDRESS,
        },
    )


async def _pay(order_id: str, token: str) -> httpx.Response:
    """The built-in payment simulator (simulation mode: no merchant id configured)."""
    return await _call(
        "POST", f"/orders/{order_id}/payment-complete", token, json={"outcome": "success"}
    )


async def _rows(db, user_id, type_: str | None = None) -> list[dict]:
    sql = "SELECT id, type, title, message, data, event_key, read_at FROM public.notifications "
    sql += "WHERE user_id = CAST(:u AS uuid)"
    params = {"u": str(user_id)}
    if type_:
        sql += " AND type = :t"
        params["t"] = type_
    await db.commit()  # fresh snapshot
    return [dict(r) for r in (await db.execute(text(sql), params)).mappings().all()]


async def _deliveries(db, user_id) -> list[dict]:
    await db.commit()
    rows = await db.execute(
        text(
            "SELECT d.id, d.channel, d.recipient, d.status, d.provider, d.attempts, "
            "d.last_error, n.type FROM public.notification_deliveries d "
            "JOIN public.notifications n ON n.id = d.notification_id "
            "WHERE n.user_id = CAST(:u AS uuid) ORDER BY d.channel"
        ),
        {"u": str(user_id)},
    )
    return [dict(r) for r in rows.mappings().all()]


async def _seed_inbox(db, user_id, count: int) -> None:
    """`count` notifications, each in its own transaction (distinct created_at)."""
    for n in range(1, count + 1):
        await notifications.notify(
            db,
            user_id=user_id,
            type_="order_created",
            event_key=f"test:{n}",
            message=f"پیام {n}",
            data={"n": n},
        )
        await db.commit()


# --- inbox API ------------------------------------------------------------------------


async def test_new_user_has_an_empty_inbox(db, people):
    token = people["b"]["token"]
    res = await _call("GET", "/notifications", token)
    assert res.status_code == 200
    assert res.json() == {"items": [], "total": 0, "page": 1, "page_size": 20, "pages": 1}
    assert (await _call("GET", "/notifications/unread-count", token)).json() == {"unread": 0}


async def test_list_is_own_newest_first_and_paginated(db, people, switches):
    await _set_switches(db, sms=False, email=False)
    a, b = people["a"], people["b"]
    await _seed_inbox(db, a["id"], 5)
    await _seed_inbox(db, b["id"], 1)

    first = (await _call("GET", "/notifications?page=1&page_size=2", a["token"])).json()
    assert (first["total"], first["pages"], first["page_size"]) == (5, 3, 2)
    assert [item["data"]["n"] for item in first["items"]] == [5, 4]
    last = (await _call("GET", "/notifications?page=3&page_size=2", a["token"])).json()
    assert [item["data"]["n"] for item in last["items"]] == [1]
    item = first["items"][0]
    assert set(item) == {"id", "type", "title", "message", "data", "read_at", "created_at"}
    assert item["read_at"] is None

    theirs = (await _call("GET", "/notifications", b["token"])).json()
    assert theirs["total"] == 1 and theirs["items"][0]["message"] == "پیام 1"

    bad = await _call("GET", "/notifications?page=0", a["token"])
    assert bad.status_code == 422
    too_big = await _call("GET", "/notifications?page_size=101", a["token"])
    assert too_big.status_code == 422


async def test_unread_filter_count_and_mark_read(db, people, switches):
    await _set_switches(db, sms=False, email=False)
    a, b = people["a"], people["b"]
    await _seed_inbox(db, a["id"], 3)
    items = (await _call("GET", "/notifications", a["token"])).json()["items"]
    target = items[1]["id"]

    # someone else's id is indistinguishable from a missing one
    assert (await _call("PATCH", f"/notifications/{target}/read", b["token"])).status_code == 404
    assert (await _call("PATCH", f"/notifications/{uuid4()}/read", a["token"])).status_code == 404
    assert (await _call("PATCH", "/notifications/not-a-uuid/read", a["token"])).status_code == 422

    first = await _call("PATCH", f"/notifications/{target}/read", a["token"])
    assert first.status_code == 200 and first.json()["read_at"] is not None
    again = await _call("PATCH", f"/notifications/{target}/read", a["token"])
    assert again.json()["read_at"] == first.json()["read_at"]  # idempotent

    assert (await _call("GET", "/notifications/unread-count", a["token"])).json() == {"unread": 2}
    unread = (await _call("GET", "/notifications?unread=true", a["token"])).json()
    assert unread["total"] == 2 and target not in [i["id"] for i in unread["items"]]


async def test_read_all_touches_only_the_callers_rows(db, people, switches):
    await _set_switches(db, sms=False, email=False)
    a, b = people["a"], people["b"]
    await _seed_inbox(db, a["id"], 3)
    await _seed_inbox(db, b["id"], 2)

    res = await _call("POST", "/notifications/read-all", a["token"])
    assert res.status_code == 200 and res.json() == {"updated": 3}
    assert (await _call("POST", "/notifications/read-all", a["token"])).json() == {"updated": 0}
    assert (await _call("GET", "/notifications/unread-count", a["token"])).json() == {"unread": 0}
    assert (await _call("GET", "/notifications/unread-count", b["token"])).json() == {"unread": 2}


async def test_anonymous_and_invalid_tokens_are_rejected(db):
    for method, path in (
        ("GET", "/notifications"),
        ("GET", "/notifications/unread-count"),
        ("PATCH", f"/notifications/{uuid4()}/read"),
        ("POST", "/notifications/read-all"),
    ):
        assert (await _call(method, path)).status_code == 401
        assert (await _call(method, path, "not-a-jwt")).status_code == 401


# --- business events + idempotency ---------------------------------------------------------


async def test_repeated_event_creates_one_notification(db, people):
    a = people["a"]
    first = await notifications.notify(
        db, user_id=a["id"], type_="order_paid", event_key="order:x:paid", message="m"
    )
    await db.commit()
    second = await notifications.notify(
        db, user_id=a["id"], type_="order_paid", event_key="order:x:paid", message="m"
    )
    await db.commit()
    assert first is not None and second is None
    assert len(await _rows(db, a["id"])) == 1


async def test_checkout_notifies_order_created_once(db, people, product, switches):
    await _set_switches(db, sms=False, email=False)
    a = people["a"]
    res = await _checkout(a["token"], product)
    assert res.status_code == 200, res.text
    order_id = res.json()["order_id"]

    rows = await _rows(db, a["id"], "order_created")
    assert len(rows) == 1
    assert rows[0]["event_key"] == f"order:{order_id}:created"
    assert rows[0]["data"] == {"order_id": order_id, "order_number": res.json()["order_number"]}
    assert notifications.fa(res.json()["order_number"]) in rows[0]["message"]

    # the same lifecycle point running again (a retried request) adds nothing
    await notifications.notify_order_event(db, order_id, "created")
    await db.commit()
    assert len(await _rows(db, a["id"], "order_created")) == 1


async def test_failed_checkout_leaves_no_notification(db, people, product, switches):
    await _set_switches(db, sms=False, email=False)
    res = await _checkout(people["a"]["token"], product, qty=20)  # stock is 10
    assert res.status_code == 409
    assert await _rows(db, people["a"]["id"]) == []


async def test_rollback_discards_the_notification_and_its_outbox(db, people, fakes, switches):
    await _set_switches(db, sms=True, email=True)
    sms, email = fakes
    await notifications.notify(
        db, user_id=people["a"]["id"], type_="order_created", event_key="rb:1", message="m"
    )
    assert db.info.get("notification_deliveries")  # queued, not yet sent
    await db.rollback()
    assert "notification_deliveries" not in db.info
    await notifications.drain()
    assert await _rows(db, people["a"]["id"]) == []
    assert sms.sent == [] and email.sent == []


async def test_payment_confirmation_is_notified_once(db, people, product, switches):
    await _set_switches(db, sms=False, email=False)
    a, manager = people["a"], people["order_manager"]
    order_id = (await _checkout(a["token"], product)).json()["order_id"]

    done = await _call(
        "POST", f"/orders/{order_id}/payment-complete", a["token"], json={"outcome": "success"}
    )
    assert done.status_code == 200 and done.json()["ok"] is True
    again = await _call(
        "POST", f"/orders/{order_id}/payment-complete", a["token"], json={"outcome": "success"}
    )
    assert again.status_code == 200
    # staff re-confirming by hand is the same event
    patched = await _call(
        "PATCH", f"/orders/{order_id}", manager["token"], json={"payment_status": "paid"}
    )
    assert patched.status_code == 200
    rows = await _rows(db, a["id"], "order_paid")
    assert len(rows) == 1 and rows[0]["event_key"] == f"order:{order_id}:paid"


async def test_failed_payment_is_not_a_confirmation(db, people, product, switches):
    await _set_switches(db, sms=False, email=False)
    a = people["a"]
    order_id = (await _checkout(a["token"], product)).json()["order_id"]
    res = await _call(
        "POST", f"/orders/{order_id}/payment-complete", a["token"], json={"outcome": "failure"}
    )
    assert res.status_code == 200 and res.json()["ok"] is False
    assert await _rows(db, a["id"], "order_paid") == []


async def test_gateway_verification_is_notified_once(db, people, product, switches):
    await _set_switches(db, sms=False, email=False)
    a = people["a"]
    order_id = (await _checkout(a["token"], product)).json()["order_id"]
    started = await _call("POST", "/payments/start", a["token"], json={"order_id": order_id})
    assert started.status_code == 200, started.text
    authority = started.json()["authority"]
    for expected in ("paid", "already_paid"):
        res = await _call("POST", f"/payments/verify?authority={authority}", a["token"])
        assert res.status_code == 200 and res.json()["status"] == expected
    assert len(await _rows(db, a["id"], "order_paid")) == 1


async def test_shipping_is_notified_once_with_the_tracking_code(db, people, product, switches):
    await _set_switches(db, sms=False, email=False)
    a, manager = people["a"], people["order_manager"]
    order_id = (await _checkout(a["token"], product)).json()["order_id"]
    await _pay(order_id, a["token"])

    shipped = await _call(
        "PATCH",
        f"/orders/{order_id}",
        manager["token"],
        json={"status": "shipped", "tracking_code": "IRPOST-777"},
    )
    assert shipped.status_code == 200, shipped.text
    # no-op repeat and a later tracking-code edit are not new shipments
    assert (
        await _call("PATCH", f"/orders/{order_id}", manager["token"], json={"status": "shipped"})
    ).status_code == 200
    assert (
        await _call(
            "PATCH", f"/orders/{order_id}", manager["token"], json={"tracking_code": "IRPOST-778"}
        )
    ).status_code == 200
    rows = await _rows(db, a["id"], "order_shipped")
    assert len(rows) == 1 and "IRPOST-777" in rows[0]["message"]


async def test_cancellation_is_notified_once(db, people, product, switches):
    await _set_switches(db, sms=False, email=False)
    a, manager = people["a"], people["order_manager"]
    order_id = (await _checkout(a["token"], product)).json()["order_id"]

    assert (await _call("POST", f"/orders/{order_id}/cancel", a["token"])).status_code == 200
    assert (await _call("POST", f"/orders/{order_id}/cancel", a["token"])).status_code == 200
    staff = await _call(
        "PATCH", f"/orders/{order_id}", manager["token"], json={"status": "cancelled"}
    )
    assert staff.status_code == 409  # terminal — unchanged state machine
    rows = await _rows(db, a["id"], "order_cancelled")
    assert len(rows) == 1 and rows[0]["event_key"] == f"order:{order_id}:cancelled"


async def test_staff_cancellation_notifies_the_owner(db, people, product, switches):
    await _set_switches(db, sms=False, email=False)
    a, manager = people["a"], people["order_manager"]
    order_id = (await _checkout(a["token"], product)).json()["order_id"]
    res = await _call(
        "PATCH", f"/orders/{order_id}", manager["token"], json={"status": "cancelled"}
    )
    assert res.status_code == 200
    assert len(await _rows(db, a["id"], "order_cancelled")) == 1
    assert await _rows(db, manager["id"]) == []  # the staff member is not the recipient


async def _refundable(db, people, product) -> tuple[str, str]:
    """A paid then cancelled order of customer A with a pending refund request."""
    a = people["a"]
    order_id = (await _checkout(a["token"], product)).json()["order_id"]
    await _pay(order_id, a["token"])
    await _call("POST", f"/orders/{order_id}/cancel", a["token"])
    req = await _call("POST", f"/orders/{order_id}/refunds", a["token"], json={"reason": "سایز"})
    assert req.status_code == 201, req.text
    return order_id, req.json()["id"]


async def test_refund_approval_and_settlement_are_notified_once(db, people, product, switches):
    await _set_switches(db, sms=False, email=False)
    a, manager = people["a"], people["order_manager"]
    order_id, refund_id = await _refundable(db, people, product)

    for _ in range(2):
        res = await _call(
            "PATCH", f"/refunds/{refund_id}", manager["token"], json={"status": "approved"}
        )
        assert res.status_code == 200
    settle = {"status": "refunded", "bank_tracking_code": "PAYA-123"}
    assert (
        await _call("PATCH", f"/refunds/{refund_id}", manager["token"], json=settle)
    ).status_code == 200
    assert (
        await _call("PATCH", f"/refunds/{refund_id}", manager["token"], json=settle)
    ).status_code == 409  # settlement is terminal (B6.9 behaviour unchanged)

    approved = await _rows(db, a["id"], "refund_approved")
    settled = await _rows(db, a["id"], "refund_settled")
    assert len(approved) == 1 and len(settled) == 1
    assert settled[0]["event_key"] == f"refund:{refund_id}:settled"
    assert "PAYA-123" in settled[0]["message"]
    assert settled[0]["data"]["order_id"] == order_id


async def test_rejected_refund_sends_nothing(db, people, product, switches):
    await _set_switches(db, sms=False, email=False)
    _, refund_id = await _refundable(db, people, product)
    res = await _call(
        "PATCH", f"/refunds/{refund_id}", people["order_manager"]["token"],
        json={"status": "rejected"},
    )
    assert res.status_code == 200
    types = {r["type"] for r in await _rows(db, people["a"]["id"])}
    assert not types & {"refund_approved", "refund_settled"}


# --- external channels -----------------------------------------------------------------------


async def test_both_channels_off_keeps_the_inbox_and_sends_nothing(
    db, people, product, fakes, switches
):
    await _set_switches(db, sms=False, email=False)
    sms, email = fakes
    assert (await _checkout(people["a"]["token"], product)).status_code == 200
    await notifications.drain()
    assert len(await _rows(db, people["a"]["id"], "order_created")) == 1
    assert await _deliveries(db, people["a"]["id"]) == []
    assert sms.sent == [] and email.sent == []


async def test_sms_off_email_on(db, people, product, fakes, switches):
    await _set_switches(db, sms=False, email=True)
    sms, email = fakes
    a = people["a"]
    assert (await _checkout(a["token"], product)).status_code == 200
    await notifications.drain()
    assert sms.sent == []
    assert len(email.sent) == 1
    recipient, subject, body = email.sent[0]
    assert recipient == a["email"] and "ساندِه" in subject and "ساندِه" in body
    rows = await _deliveries(db, a["id"])
    assert [(r["channel"], r["status"], r["attempts"]) for r in rows] == [("email", "sent", 1)]
    assert len(await _rows(db, a["id"], "order_created")) == 1


async def test_sms_on_email_off_uses_the_profile_phone(db, people, product, fakes, switches):
    await _set_switches(db, sms=True, email=False)
    sms, email = fakes
    a = people["a"]
    assert (await _checkout(a["token"], product)).status_code == 200
    await notifications.drain()
    assert email.sent == []
    assert [s[0] for s in sms.sent] == ["09123456789"]  # profile phone, ASCII digits
    rows = await _deliveries(db, a["id"])
    assert [(r["channel"], r["status"]) for r in rows] == [("sms", "sent")]


async def test_sms_falls_back_to_the_order_phone(db, people, product, fakes, switches):
    await _set_switches(db, sms=True, email=False)
    sms, _ = fakes
    assert (await _checkout(people["b"]["token"], product)).status_code == 200  # B: no phone
    await notifications.drain()
    assert [s[0] for s in sms.sent] == ["09121112233"]  # ADDRESS phone, normalised


async def test_no_recipient_is_recorded_as_skipped(db, people, fakes, switches):
    await _set_switches(db, sms=True, email=False)
    sms, _ = fakes
    b = people["b"]
    await notifications.notify(
        db, user_id=b["id"], type_="order_paid", event_key="nr:1", message="m"
    )
    await db.commit()
    await notifications.drain()
    rows = await _deliveries(db, b["id"])
    assert [(r["status"], r["last_error"]) for r in rows] == [("skipped", "no_recipient")]
    assert sms.sent == []


async def test_missing_credentials_never_fail_the_business_flow(db, people, product, switches):
    """Real factories, no credentials configured, both switches on."""
    if settings.kavenegar_api_key or settings.smtp_host:
        pytest.skip("real provider credentials are configured in this environment")
    await _set_switches(db, sms=True, email=True)
    a = people["a"]
    res = await _checkout(a["token"], product)
    assert res.status_code == 200
    order_id = res.json()["order_id"]
    paid = await _call(
        "POST", f"/orders/{order_id}/payment-complete", a["token"], json={"outcome": "success"}
    )
    assert paid.status_code == 200 and paid.json()["ok"] is True
    await notifications.drain()
    rows = await _deliveries(db, a["id"])
    assert len(rows) == 4  # 2 events × 2 channels
    assert {(r["status"], r["last_error"], r["attempts"]) for r in rows} == {
        ("skipped", "provider_not_configured", 0)
    }
    assert {r["provider"] for r in rows} == {"kavenegar", "smtp"}
    assert len(await _rows(db, a["id"])) == 2


async def test_unconfigured_fake_provider_is_skipped(db, people, product, fakes, switches):
    await _set_switches(db, sms=True, email=True)
    sms, email = fakes
    sms.is_configured = email.is_configured = False
    assert (await _checkout(people["a"]["token"], product)).status_code == 200
    await notifications.drain()
    assert sms.sent == [] and email.sent == []
    rows = await _deliveries(db, people["a"]["id"])
    assert {r["status"] for r in rows} == {"skipped"}


async def test_provider_failure_never_fails_the_business_flow(db, people, product, fakes, switches):
    await _set_switches(db, sms=True, email=True)
    sms, email = fakes
    sms.fail = email.fail = True
    a = people["a"]
    res = await _checkout(a["token"], product)
    assert res.status_code == 200
    order_id = res.json()["order_id"]
    await notifications.drain()

    order = (await _call("GET", f"/orders/{order_id}", a["token"])).json()
    assert (order["status"], order["payment_status"]) == ("pending", "unpaid")
    assert len(await _rows(db, a["id"], "order_created")) == 1
    rows = await _deliveries(db, a["id"])
    assert [(r["channel"], r["status"], r["attempts"], r["last_error"]) for r in rows] == [
        ("email", "failed", 1, "fake-email: down"),
        ("sms", "failed", 1, "fake-sms: down"),
    ]

    # a retry after the provider recovers sends once; a second retry is a no-op
    sms.fail = email.fail = False
    ids = [str(r["id"]) for r in rows]
    await notifications.dispatch_deliveries(ids)
    await notifications.dispatch_deliveries(ids)
    assert len(sms.sent) == 1 and len(email.sent) == 1
    rows = await _deliveries(db, a["id"])
    assert {(r["status"], r["attempts"], r["last_error"]) for r in rows} == {("sent", 2, None)}


async def test_repeated_transitions_send_one_message_per_channel(
    db, people, product, fakes, switches
):
    await _set_switches(db, sms=True, email=True)
    sms, email = fakes
    a = people["a"]
    order_id = (await _checkout(a["token"], product)).json()["order_id"]
    for _ in range(3):
        await _call("POST", f"/orders/{order_id}/cancel", a["token"])
    await notifications.drain()
    # order_created + order_cancelled, once each, on each channel
    assert len(sms.sent) == 2 and len(email.sent) == 2


async def test_switch_turned_off_before_dispatch_is_honoured(db, people, fakes, switches):
    await _set_switches(db, sms=True, email=False)
    sms, _ = fakes
    a = people["a"]
    await notifications.notify(
        db, user_id=a["id"], type_="order_paid", event_key="late:1", message="m"
    )
    # admin flips SMS off in the same instant the event commits
    await db.execute(text("UPDATE public.notification_settings SET sms_enabled = false"))
    await db.commit()
    await notifications.drain()
    rows = await _deliveries(db, a["id"])
    assert [(r["status"], r["last_error"]) for r in rows] == [("skipped", "channel_disabled")]
    assert sms.sent == []


# --- admin switches: authorization + contract ------------------------------------------------


async def test_settings_are_admin_only(db, people, switches):
    path = "/admin/settings/notifications"
    assert (await _call("GET", path)).status_code == 401
    assert (await _call("PATCH", path, json={"sms_enabled": True})).status_code == 401
    for label in ("a", "support", "order_manager"):
        token = people[label]["token"]
        assert (await _call("GET", path, token)).status_code == 403, label
        assert (await _call("PATCH", path, token, json={"sms_enabled": True})).status_code == 403
    for label in ("admin", "super_admin"):
        res = await _call("GET", path, people[label]["token"])
        assert res.status_code == 200, label
        body = res.json()
        assert body["internal_enabled"] is True
        assert (body["sms_provider"], body["email_provider"]) == ("kavenegar", "smtp")


async def test_admin_updates_switches_and_is_audited(db, people, switches):
    await _set_switches(db, sms=False, email=False)
    admin = people["admin"]
    path = "/admin/settings/notifications"

    res = await _call("PATCH", path, admin["token"], json={"sms_enabled": True})
    assert res.status_code == 200
    body = res.json()
    assert (body["sms_enabled"], body["email_enabled"]) == (True, False)
    assert body["updated_by"] == str(admin["id"])
    # the switch alone does not make a channel send: the provider must be configured
    assert body["sms_active"] == (body["sms_enabled"] and body["sms_configured"])

    res = await _call("PATCH", path, people["super_admin"]["token"], json={"email_enabled": True})
    assert (res.json()["sms_enabled"], res.json()["email_enabled"]) == (True, True)

    await db.commit()
    audit = (
        await db.execute(
            text(
                "SELECT old_values, new_values FROM public.audit_logs "
                "WHERE action = 'update_notification_settings' AND admin_id = :u"
            ),
            {"u": str(admin["id"])},
        )
    ).mappings().all()
    assert len(audit) == 1
    assert audit[0]["old_values"] == {"sms_enabled": False, "email_enabled": False}
    assert audit[0]["new_values"] == {"sms_enabled": True, "email_enabled": False}
    await db.execute(
        text("DELETE FROM public.audit_logs WHERE entity_type = 'settings' AND admin_id = ANY("
             "CAST(:ids AS uuid[]))"),
        {"ids": [str(admin["id"]), str(people["super_admin"]["id"])]},
    )
    await db.commit()


async def test_settings_payload_is_validated(db, people, switches):
    token = people["admin"]["token"]
    path = "/admin/settings/notifications"
    assert (await _call("PATCH", path, token, json={})).status_code == 400
    assert (await _call("PATCH", path, token, json={"sms_enabled": "yes"})).status_code == 422
    assert (await _call("PATCH", path, token, json={"sms_enabled": 1})).status_code == 422
    # the in-app inbox has no switch
    assert (
        await _call("PATCH", path, token, json={"internal_enabled": False})
    ).status_code == 422
