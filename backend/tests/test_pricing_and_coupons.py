"""Unit tests for pure logic: pricing, coupon rules, payment helpers."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
os.environ.setdefault("JWT_SECRET", "test-secret")

from datetime import UTC, datetime, timedelta  # noqa: E402
from uuid import uuid4  # noqa: E402

import pytest  # noqa: E402

from app.config import settings  # noqa: E402
from app.services.coupons import (  # noqa: E402
    Coupon,
    CouponError,
    compute_discount,
    generate_code,
    validate_coupon,
)
from app.services.payments import fake_reference, tracking_code  # noqa: E402
from app.services.pricing import quote, shipping_fee  # noqa: E402

# --- pricing -------------------------------------------------------------------


class TestPricing:
    def test_flat_shipping_below_threshold(self):
        assert shipping_fee(1_500_000) == settings.shipping_flat_fee

    def test_free_shipping_at_threshold(self):
        assert shipping_fee(2_000_000) == 0

    def test_free_shipping_above_threshold(self):
        assert shipping_fee(2_500_000) == 0

    def test_quote_without_discount(self):
        q = quote(subtotal=1_000_000, discount=0)
        assert q.total == 1_000_000 + settings.shipping_flat_fee

    def test_quote_discount_is_capped_at_subtotal(self):
        q = quote(subtotal=100_000, discount=500_000)
        assert q.discount == 100_000
        # fully-discounted merchandise still owes shipping (below free threshold)
        assert q.shipping == settings.shipping_flat_fee
        assert q.total == settings.shipping_flat_fee

    def test_quote_never_negative(self):
        q = quote(subtotal=300_000, discount=200_000)
        assert q.total == 100_000 + settings.shipping_flat_fee


# --- coupons -------------------------------------------------------------------


def make_coupon(**overrides) -> Coupon:
    base = dict(
        id=uuid4(),
        code="TEST10",
        percent_off=10,
        amount_off=None,
        min_subtotal=0,
        max_uses=None,
        max_uses_per_user=1,
        used_count=0,
        starts_at=None,
        expires_at=None,
        active=True,
        created_at=datetime.now(UTC),
    )
    base.update(overrides)
    return Coupon(**base)


class TestComputeDiscount:
    def test_percent(self):
        assert compute_discount(make_coupon(percent_off=25), 800_000) == 200_000

    def test_amount(self):
        assert compute_discount(make_coupon(percent_off=None, amount_off=50_000), 800_000) == 50_000

    def test_discount_capped_at_subtotal(self):
        coupon = make_coupon(percent_off=None, amount_off=999_999)
        assert compute_discount(coupon, 100_000) == 100_000


class TestValidateCoupon:
    def test_happy_path(self):
        c = make_coupon(percent_off=10)
        assert validate_coupon(c, 1_000_000, uuid4(), prior_uses=0) == 100_000

    def test_inactive(self):
        c = make_coupon(active=False)
        with pytest.raises(CouponError) as e:
            validate_coupon(c, 1_000_000, uuid4(), 0)
        assert e.value.code == "inactive"

    def test_expired(self):
        c = make_coupon(expires_at=datetime.now(UTC) - timedelta(days=1))
        with pytest.raises(CouponError) as e:
            validate_coupon(c, 1_000_000, uuid4(), 0)
        assert e.value.code == "expired"

    def test_not_started(self):
        c = make_coupon(starts_at=datetime.now(UTC) + timedelta(days=1))
        with pytest.raises(CouponError) as e:
            validate_coupon(c, 1_000_000, uuid4(), 0)
        assert e.value.code == "not_started"

    def test_min_subtotal(self):
        c = make_coupon(min_subtotal=1_500_000)
        with pytest.raises(CouponError) as e:
            validate_coupon(c, 1_000_000, uuid4(), 0)
        assert e.value.code == "min_subtotal"

    def test_global_exhausted(self):
        c = make_coupon(max_uses=10, used_count=10)
        with pytest.raises(CouponError) as e:
            validate_coupon(c, 1_000_000, uuid4(), 0)
        assert e.value.code == "exhausted"

    def test_per_user_limit(self):
        c = make_coupon(max_uses_per_user=1)
        with pytest.raises(CouponError) as e:
            validate_coupon(c, 1_000_000, uuid4(), prior_uses=1)
        assert e.value.code == "per_user_limit"


def test_generate_code_format():
    code = generate_code("SANDE")
    assert code.startswith("SANDE")
    assert len(code) == len("SANDE") + 6
    assert all(ch in "ABCDEFGHJKLMNPQRSTUVWXYZ23456789" for ch in code[len("SANDE") :])


# --- payment helpers -------------------------------------------------------------


def test_tracking_code_format():
    assert tracking_code("260810", "abc123def456…") == "SND-260810-ABC123"


def test_fake_reference_format():
    ref = fake_reference("260810")
    assert ref.startswith("SND-260810-")
    assert ref.rsplit("-", 1)[1].isdigit()
