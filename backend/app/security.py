"""Password hashing (bcrypt) and JWT issuing/verification.

The backend is the sole identity provider: it issues HS256 access tokens with
`sub` = user UUID, `email`, and `role` (admin|customer) claims.

Uses the bcrypt library directly rather than passlib: passlib 1.7.4 has been
unmaintained since 2020 and cannot even load bcrypt >= 4.1 (its backend probe
passes a >72-byte secret, which newer bcrypt rejects instead of truncating).
The hashes it produced are standard `$2b$` bcrypt, so existing ones still verify.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import bcrypt
from jose import jwt

from app.config import settings

# bcrypt only reads the first 72 bytes and (since 4.1) refuses longer input, while
# the request schemas allow up to 128 characters. Truncate identically on hash and
# verify so any password the schema accepts keeps working.
_BCRYPT_MAX_BYTES = 72


def _password_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_password_bytes(password), hashed.encode("ascii"))
    except ValueError:  # malformed hash stored in the database
        return False


def create_access_token(user_id: UUID, email: str, role: str) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
        "aud": "authenticated",
        "iss": "sandeh-backend",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Raises JWTError on invalid/expired tokens."""
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        audience="authenticated",
        options={"verify_aud": True, "verify_exp": True},
    )
