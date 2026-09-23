"""Password reset (F2.3): one-time, expiring, hash-stored tokens + the reset email.

`request_reset` never reveals whether an email has an account: the router answers
the same way for an unknown address, a known one and a throttled one. Only the
SHA-256 of the token is stored; the raw token exists solely in the emailed link.
A new link supersedes every earlier one, a link works once, and it expires after
`PASSWORD_RESET_TTL_MINUTES`. The email goes through the canonical notification
service (`queue_private_email`: email switch on AND SMTP configured, sent after
COMMIT, body never persisted).

A reset stamps `users.password_changed_at`, which ends every session issued
before it (B6.14, enforced in `app/auth.py`).
"""

import hashlib
import logging
import secrets

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.security import hash_password
from app.services import notifications

log = logging.getLogger(__name__)

TOKEN_BYTES = 32


class ResetError(Exception):
    """The link is unknown, already used, superseded or expired (caller maps to 400)."""


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def reset_link(raw: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/reset-password?token={raw}"


def reset_email(link: str) -> tuple[str, str]:
    minutes = notifications.fa(settings.password_reset_ttl_minutes)
    subject = f"بازیابی رمز عبور — {notifications.BRAND}"
    body = (
        "سلام،\n\n"
        "برای تعیین رمز عبور تازهٔ حساب ساندِه روی لینک زیر بزنید. این لینک "
        f"تا {minutes} دقیقهٔ دیگر و فقط یک بار کار می‌کند:\n\n"
        f"{link}\n\n"
        "اگر شما درخواست بازیابی نداده‌اید، این ایمیل را نادیده بگیرید؛ "
        "رمز عبور فعلی شما تغییری نمی‌کند.\n\n"
        f"{notifications.BRAND}"
    )
    return subject, body


async def request_reset(session: AsyncSession, email: str) -> None:
    """Issue a link for this address if it has an account; silent otherwise."""
    # housekeeping: spent or expired rows are useless after a day
    await session.execute(
        text(
            "DELETE FROM public.password_reset_tokens "
            "WHERE created_at < now() - interval '1 day'"
        )
    )
    user = (
        await session.execute(
            text("SELECT id, email FROM public.users WHERE lower(email) = :email"),
            {"email": email.strip().lower()},
        )
    ).mappings().first()
    if user is None:
        return

    recent = (
        await session.execute(
            text(
                "SELECT COUNT(*) FROM public.password_reset_tokens "
                "WHERE user_id = :uid AND created_at > now() - interval '1 hour'"
            ),
            {"uid": str(user["id"])},
        )
    ).scalar_one()
    if recent >= settings.password_reset_max_per_hour:
        log.info("password reset throttled for a user (%d links in the last hour)", recent)
        return

    # only the newest link works: earlier unused ones are spent now
    await session.execute(
        text(
            "UPDATE public.password_reset_tokens SET used_at = now() "
            "WHERE user_id = :uid AND used_at IS NULL"
        ),
        {"uid": str(user["id"])},
    )
    raw = secrets.token_urlsafe(TOKEN_BYTES)
    await session.execute(
        text(
            "INSERT INTO public.password_reset_tokens (user_id, token_hash, expires_at) "
            "VALUES (:uid, :hash, now() + make_interval(mins => :ttl))"
        ),
        {
            "uid": str(user["id"]),
            "hash": hash_token(raw),
            "ttl": settings.password_reset_ttl_minutes,
        },
    )
    subject, body = reset_email(reset_link(raw))
    await notifications.queue_private_email(
        session, to=user["email"], subject=subject, body=body, kind="password_reset"
    )


async def reset_password(session: AsyncSession, raw_token: str, new_password: str) -> None:
    """Consume a valid link and set the new password (caller commits)."""
    row = (
        await session.execute(
            text(
                "SELECT id, user_id FROM public.password_reset_tokens "
                "WHERE token_hash = :hash AND used_at IS NULL AND expires_at > now() "
                "FOR UPDATE"
            ),
            {"hash": hash_token(raw_token)},
        )
    ).mappings().first()
    if row is None:
        raise ResetError("invalid or expired reset link")

    await session.execute(
        text(
            "UPDATE public.users SET password_hash = :ph, password_changed_at = now(), "
            "updated_at = now() WHERE id = :uid"
        ),
        {"ph": hash_password(new_password), "uid": str(row["user_id"])},
    )
    # this link and any sibling still outstanding are spent
    await session.execute(
        text(
            "UPDATE public.password_reset_tokens SET used_at = now() "
            "WHERE user_id = :uid AND used_at IS NULL"
        ),
        {"uid": str(row["user_id"])},
    )
