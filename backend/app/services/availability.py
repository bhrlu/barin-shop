"""Orderability by `availability` — shared by the stock pre-check and checkout.

`availability` is a merchandising state, not a stock count. `coming_soon` is
never orderable — the release date (not the warehouse) holds it back. Since
B4.13 (decision D4) a `preorder` product **is** orderable: the money is real
but the physical stock is not touched at checkout, and the order line carries
`is_preorder = true` as the fulfilment flag.
"""

from collections.abc import Mapping
from typing import Any

READY = "in_stock"
PREORDER = "preorder"


def availability_issue(product: Mapping[str, Any]) -> str | None:
    """`None` when the product may be ordered, else the issue reason to report."""
    availability = product.get("availability") or READY
    if availability == PREORDER:
        return None  # D4: preorder is purchasable (no stock decrement at checkout)
    if availability != READY:
        return "not_available"
    return None


def is_preorder(product: Mapping[str, Any]) -> bool:
    """Whether this line is a preorder (drives checkout's stock handling)."""
    return (product.get("availability") or READY) == PREORDER
