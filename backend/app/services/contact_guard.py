"""Contact-form abuse guard (B3.11, decision D1).

`POST /contact` is public, so every attempt — accepted or rejected — is written
to `contact_attempts` and an IP may make at most `contact_rate_limit` attempts
per sliding `contact_rate_window_seconds` (5 per 10 minutes by default). A
filled honeypot field is rejected but still counts. Guests and signed-in users
share the same per-IP boundary. No Redis, no CAPTCHA: PostgreSQL only.

Concurrency: the count and the insert run under a per-IP transaction advisory
lock, so parallel requests from one address are serialised and cannot all see
"4 so far" and slip past the limit together. The lock is released when the
request's transaction commits.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

ACCEPTED = "accepted"
HONEYPOT = "honeypot"
THROTTLED = "throttled"

# rows older than this are no longer needed by any window
_RETENTION_SECONDS = 86_400


async def record_attempt(session: AsyncSession, *, ip: str | None, honeypot: bool) -> str:
    """Decide and record one attempt; returns ACCEPTED, HONEYPOT or THROTTLED.

    Runs on the request's session and does not commit: an accepted attempt
    commits together with the stored message, a rejected one must be committed
    by the caller before raising (the session dependency rolls back on errors).
    """
    key = ip or "unknown"
    window = settings.contact_rate_window_seconds
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
        {"k": f"contact:{key}"},
    )
    recent = (
        await session.execute(
            text(
                "SELECT COUNT(*) FROM public.contact_attempts "
                "WHERE ip = :ip AND created_at > now() - make_interval(secs => :window)"
            ),
            {"ip": key, "window": window},
        )
    ).scalar_one()
    if recent >= settings.contact_rate_limit:
        outcome = THROTTLED
    elif honeypot:
        outcome = HONEYPOT
    else:
        outcome = ACCEPTED
    await session.execute(
        text("INSERT INTO public.contact_attempts (ip, outcome) VALUES (:ip, :outcome)"),
        {"ip": key, "outcome": outcome},
    )
    await session.execute(
        text(
            "DELETE FROM public.contact_attempts "
            "WHERE created_at < now() - make_interval(secs => :keep)"
        ),
        {"keep": max(window, _RETENTION_SECONDS)},
    )
    return outcome
