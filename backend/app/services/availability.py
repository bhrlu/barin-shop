"""Orderability by `availability` — shared by the stock pre-check and checkout.

`availability` is a merchandising state, not a stock count: a `coming_soon` or
`preorder` product is not orderable at all, whatever its `stock` says, because
the release date (not the warehouse) is what holds it back. Both
`POST /stock/check` and checkout apply the rule through this helper, so the
pre-check and the order can never disagree about which products may be bought.

Preorder is intentionally **not** orderable for now: the storefront disables
add-to-cart for it too (see `VariantPicker` / `product.$id.tsx`), and letting a
preorder through would need a fulfilment flag on the order that the schema does
not have. Turning it on later means relaxing `availability_issue()` and adding
that flag — nothing else in the flow assumes it.
"""

from collections.abc import Mapping
from typing import Any

READY = "in_stock"


def availability_issue(product: Mapping[str, Any]) -> str | None:
    """`None` when the product may be ordered, else the issue reason to report."""
    if (product.get("availability") or READY) != READY:
        return "not_available"
    return None
