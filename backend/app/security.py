"""Password hashing (bcrypt via passlib) and JWT issuing/verification.

The backend is the sole identity provider: it issues HS256 access tokens with
`sub` = user UUID, `email`, and `role` (admin|customer) claims.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from jose import jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


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
