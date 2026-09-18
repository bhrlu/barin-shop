"""Money math shared by coupon validation, checkout, and payment flows.

Mirrors the frontend cart rules exactly:
- flat shipping fee, free above a threshold
- discount never exceeds subtotal; shipping is computed on the discounted subtotal
"""

from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class PriceQuote:
    subtotal: int
    discount: int
    shipping: int
    total: int


def shipping_fee(subtotal_after_discount: int) -> int:
    if subtotal_after_discount >= settings.free_shipping_threshold:
        return 0
    return settings.shipping_flat_fee


def quote(subtotal: int, discount: int) -> PriceQuote:
    discount = max(0, min(discount, subtotal))
    ship = shipping_fee(subtotal - discount)
    return PriceQuote(
        subtotal=subtotal,
        discount=discount,
        shipping=ship,
        total=subtotal - discount + ship,
    )
