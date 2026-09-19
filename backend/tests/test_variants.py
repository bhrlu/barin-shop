"""Unit tests for the per-variant stock resolver.

A variant row is authoritative for its size×color; without one the product's
aggregate stock is used. Deactivated variants make the combination unavailable.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.services.variants import variant_stock  # noqa: E402


def _product(stock: int) -> dict:
    return {"stock": stock}


def test_falls_back_to_product_stock_without_variant():
    assert variant_stock(_product(25), None) == (25, True)


def test_variant_stock_overrides_product_stock():
    assert variant_stock(_product(25), {"stock": 2, "active": True}) == (2, True)


def test_inactive_variant_marks_combo_unavailable():
    stock, ok = variant_stock(_product(25), {"stock": 5, "active": False})
    assert ok is False


def test_zero_variant_stock_is_sold_out():
    assert variant_stock(_product(25), {"stock": 0, "active": True}) == (0, True)
