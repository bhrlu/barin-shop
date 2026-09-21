"""Query-parameter helpers for the catalog list endpoint.

Facet filters accept **both** shapes, because both are natural in a URL and both
appear in practice (a repeated param from `URLSearchParams.append`, a
comma-separated one from a hand-typed link):

    /products?size=M&size=L
    /products?size=M,L
    /products?size=M&size=L,M

Values are trimmed, empty entries dropped and duplicates removed (order kept).
"""

from collections.abc import Iterable


def split_multi(values: Iterable[str] | None) -> list[str]:
    """Flatten repeated/comma-separated facet values into a clean list."""
    if not values:
        return []
    out: list[str] = []
    for value in values:
        out.extend(part.strip() for part in value.split(",") if part.strip())
    return list(dict.fromkeys(out))
