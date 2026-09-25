"""Pure unit tests for the B2.5a/D11 webhook primitives (no DB, no HTTP)."""

import os

os.environ.setdefault("JWT_SECRET", "test-secret")

import hashlib  # noqa: E402
import hmac  # noqa: E402

from app.config import settings  # noqa: E402
from app.services import webhooks  # noqa: E402


def test_event_set_is_the_d11_closed_set():
    assert sorted(webhooks.EVENTS.values()) == [
        "order.cancelled",
        "order.created",
        "order.delivered",
        "order.paid",
        "order.shipped",
    ]


def test_sign_matches_reference_hmac():
    body = b'{"event":"order.paid"}'
    expected = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    assert webhooks.sign("s3cret", body) == expected
    assert webhooks.sign("s3cret", body + b" ") != expected


def test_configured_requires_both_values(monkeypatch):
    monkeypatch.setattr(settings, "webhook_order_url", "")
    monkeypatch.setattr(settings, "webhook_hmac_secret", "")
    assert webhooks.configured() is False
    monkeypatch.setattr(settings, "webhook_order_url", "https://example.test/hook")
    assert webhooks.configured() is False  # url without secret is still off
    monkeypatch.setattr(settings, "webhook_hmac_secret", "s3cret")
    assert webhooks.configured() is True


def test_state_never_leaks_the_secret(monkeypatch):
    monkeypatch.setattr(settings, "webhook_order_url", "https://example.test/hook")
    monkeypatch.setattr(settings, "webhook_hmac_secret", "s3cret-value")
    state = webhooks.state()
    assert state["enabled"] is True
    assert state["url"] == "https://example.test/hook"
    assert "s3cret-value" not in str(state)


def test_payload_is_the_raw_dump_envelope():
    payload = webhooks.webhook_payload(
        "order.created",
        "2026-09-25T10:00:00+00:00",
        {"id": "ord-1", "total": 150000, "note": None, "created_at": "2026-09-25T10:00:00+00:00"},
        [{"id": "it-1", "price": 150000, "quantity": 1, "size": None}],
    )
    assert set(payload) == {"event", "occurred_at", "order", "items"}
    assert payload["event"] == "order.created"
    assert payload["order"]["total"] == 150000  # raw dump keeps the column
    assert payload["order"]["note"] is None
    assert payload["items"][0]["size"] is None


def test_payload_json_serializes_uuid_and_datetime():
    from datetime import datetime
    from uuid import uuid4

    order_id = uuid4()
    payload = webhooks.webhook_payload(
        "order.paid",
        datetime(2026, 9, 25, 12, 0),
        {"id": order_id, "created_at": datetime(2026, 9, 25, 11, 0)},
        [],
    )
    assert payload["order"]["id"] == str(order_id)
    assert payload["order"]["created_at"] == "2026-09-25T11:00:00"
