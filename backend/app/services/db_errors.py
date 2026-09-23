"""Classifying database errors (shared since B6.9a; first used by B6.9).

A handler may translate *only* the failure it expects into a client answer —
normally a duplicate (`unique_violation`, SQLSTATE 23505) → 409 — and must
re-raise everything else, so a real database fault surfaces as a 500 with its
traceback instead of being reported as "already exists".
"""

from sqlalchemy.exc import IntegrityError


def is_unique_violation(exc: IntegrityError) -> bool:
    """True only for Postgres `unique_violation` (SQLSTATE 23505).

    Everything else IntegrityError covers — foreign-key, not-null and check
    violations — is an unexpected failure, not a duplicate request.
    """
    return getattr(exc.orig, "sqlstate", None) == "23505"
