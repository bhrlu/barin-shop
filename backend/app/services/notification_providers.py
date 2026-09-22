"""Outbound notification providers (B2.1, decision D2): Kavenegar SMS + SMTP email.

Only `app/services/notifications.py` talks to these — business code never
imports them. Each provider reports `configured()` from environment settings
(credentials never live in the database) and raises `ProviderError` on any
failure, with a message that is safe to store: it never contains the API key
(Kavenegar puts the key in the URL path) or the SMTP password.

Neither provider has been exercised against the real service yet — no
credentials exist for this store. They are covered by tests with a stub HTTP
transport / stub SMTP class only.
"""

import asyncio
import smtplib
from email.message import EmailMessage
from typing import Protocol

import httpx

from app.config import settings

KAVENEGAR_BASE_URL = "https://api.kavenegar.com"


class ProviderError(Exception):
    """A provider refused or failed to send. `str()` is safe to persist/log."""


class SmsProvider(Protocol):
    name: str

    def configured(self) -> bool: ...

    async def send(self, recipient: str, message: str) -> None: ...


class EmailProvider(Protocol):
    name: str

    def configured(self) -> bool: ...

    async def send(self, recipient: str, subject: str, body: str) -> None: ...


class KavenegarSmsProvider:
    """Kavenegar REST `sms/send.json`: success is `return.status == 200`."""

    name = "kavenegar"

    def __init__(
        self,
        api_key: str,
        sender: str = "",
        *,
        base_url: str = KAVENEGAR_BASE_URL,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._sender = sender
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport  # tests inject httpx.MockTransport

    def configured(self) -> bool:
        return bool(self._api_key)

    async def send(self, recipient: str, message: str) -> None:
        if not self.configured():
            raise ProviderError("kavenegar: not configured")
        form = {"receptor": recipient, "message": message}
        if self._sender:
            form["sender"] = self._sender
        url = f"{self._base_url}/v1/{self._api_key}/sms/send.json"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                resp = await client.post(url, data=form)
        except httpx.HTTPError as exc:
            # the exception text carries the URL, i.e. the API key — keep the class only
            raise ProviderError(f"kavenegar: request failed ({type(exc).__name__})") from None
        try:
            status = int((resp.json().get("return") or {}).get("status"))
        except (ValueError, TypeError, AttributeError):
            raise ProviderError(
                f"kavenegar: unreadable response (HTTP {resp.status_code})"
            ) from None
        if status != 200:
            raise ProviderError(f"kavenegar: rejected (status {status})")


class SmtpEmailProvider:
    """Plain SMTP via the standard library, run in a worker thread."""

    name = "smtp"

    def __init__(
        self,
        host: str,
        port: int = 587,
        username: str = "",
        password: str = "",
        from_address: str = "",
        *,
        starttls: bool = True,
        use_ssl: bool = False,
        timeout: float = 10.0,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from = from_address
        self._starttls = starttls
        self._ssl = use_ssl
        self._timeout = timeout

    def configured(self) -> bool:
        return bool(self._host and self._from)

    async def send(self, recipient: str, subject: str, body: str) -> None:
        if not self.configured():
            raise ProviderError("smtp: not configured")
        msg = EmailMessage()
        msg["From"] = self._from
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.set_content(body)
        try:
            await asyncio.to_thread(self._send_sync, msg)
        except (smtplib.SMTPException, OSError) as exc:
            raise ProviderError(f"smtp: {type(exc).__name__}: {exc}"[:300]) from None

    def _send_sync(self, msg: EmailMessage) -> None:
        smtp_cls = smtplib.SMTP_SSL if self._ssl else smtplib.SMTP
        with smtp_cls(self._host, self._port, timeout=self._timeout) as smtp:
            if self._starttls and not self._ssl:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password)
            smtp.send_message(msg)


def sms_provider() -> SmsProvider:
    """The configured SMS provider (tests monkeypatch this factory)."""
    return KavenegarSmsProvider(
        settings.kavenegar_api_key,
        settings.kavenegar_sender,
        timeout=settings.notification_provider_timeout_seconds,
    )


def email_provider() -> EmailProvider:
    """The configured email provider (tests monkeypatch this factory)."""
    return SmtpEmailProvider(
        settings.smtp_host,
        settings.smtp_port,
        settings.smtp_username,
        settings.smtp_password,
        settings.smtp_from,
        starttls=settings.smtp_starttls,
        use_ssl=settings.smtp_ssl,
        timeout=settings.notification_provider_timeout_seconds,
    )
