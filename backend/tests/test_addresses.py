"""Regression tests for address response shaping.

`AddressOut.created_at` is a `str`, but Postgres returns a `datetime`. Passing
the raw datetime to the model made Pydantic raise a ResponseValidationError,
which FastAPI surfaced as a 500 on both GET /addresses and POST /addresses.
`_row_to_out` now isoformats it (matching products/auth/coupons).
"""

import os
from datetime import UTC, datetime
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.routers.addresses import _row_to_out  # noqa: E402


def _row(created_at):
    return {
        "id": uuid4(),
        "user_id": uuid4(),
        "title": "خانه",
        "receiver": "گیرنده",
        "phone": "09120000000",
        "province": "تهران",
        "city": "تهران",
        "postal_code": "1998765432",
        "line": "خیابان تست، پلاک ۱",
        "is_default": False,
        "created_at": created_at,
    }


def test_row_to_out_isoformats_datetime():
    created = datetime(2026, 9, 19, 12, 30, tzinfo=UTC)
    out = _row_to_out(_row(created))
    assert out.created_at == created.isoformat()
    assert isinstance(out.created_at, str)


def test_row_to_out_handles_null_created_at():
    out = _row_to_out(_row(None))
    assert out.created_at is None
