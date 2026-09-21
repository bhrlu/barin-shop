"""Unit tests for the catalog list helpers.

`availability_issue()` gates ordering for `coming_soon`/`preorder` products in
both `POST /stock/check` and checkout; `split_multi()` normalises the repeatable
and/or comma-separated facet query params.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.services.availability import availability_issue  # noqa: E402
from app.services.catalog_filters import split_multi  # noqa: E402

# --- availability ----------------------------------------------------------------


class TestAvailabilityIssue:
    def test_in_stock_is_orderable(self):
        assert availability_issue({"availability": "in_stock"}) is None

    def test_coming_soon_is_blocked(self):
        assert availability_issue({"availability": "coming_soon"}) == "not_available"

    def test_preorder_is_blocked(self):
        assert availability_issue({"availability": "preorder"}) == "not_available"

    def test_missing_column_falls_back_to_orderable(self):
        # rows read before the column existed must not start rejecting orders
        assert availability_issue({}) is None

    def test_null_availability_falls_back_to_orderable(self):
        assert availability_issue({"availability": None}) is None

    def test_stock_does_not_override_availability(self):
        # plenty of stock, still not released
        assert availability_issue({"availability": "coming_soon", "stock": 999}) == "not_available"


# --- facet params ----------------------------------------------------------------


class TestSplitMulti:
    def test_none_and_empty(self):
        assert split_multi(None) == []
        assert split_multi([]) == []
        assert split_multi(["", "  "]) == []

    def test_single_value(self):
        assert split_multi(["M"]) == ["M"]

    def test_repeated_params(self):
        assert split_multi(["M", "L"]) == ["M", "L"]

    def test_comma_separated(self):
        assert split_multi(["M,L,XL"]) == ["M", "L", "XL"]

    def test_mixed_and_trimmed(self):
        assert split_multi(["M, L", " XL "]) == ["M", "L", "XL"]

    def test_dedupes_keeping_order(self):
        assert split_multi(["L,M", "M"]) == ["L", "M"]

    def test_ignores_empty_segments(self):
        assert split_multi(["M,,L,"]) == ["M", "L"]

    def test_persian_colour_names(self):
        assert split_multi(["کرم، سفید".replace("،", ",")]) == ["کرم", "سفید"]
