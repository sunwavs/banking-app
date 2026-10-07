"""Shopping basket.

The session stores only ``{product id: quantity}``. Names and prices are resolved from the
catalog whenever the basket is displayed and when an order is placed, so a price cannot be
tampered with through the cookie and the cookie stays small.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from flask import session

from app.repositories.products import Product

SESSION_KEY = "basket"


@dataclass(frozen=True)
class BasketLine:
    product_id: int
    name: str
    unit_price: Decimal
    quantity: int

    @property
    def total(self) -> Decimal:
        return self.unit_price * self.quantity


def read() -> dict[str, int]:
    raw = session.get(SESSION_KEY) or {}
    return {str(k): int(v) for k, v in raw.items() if int(v) > 0}


def add(product_id: str) -> None:
    basket = read()
    basket[product_id] = basket.get(product_id, 0) + 1
    session[SESSION_KEY] = basket


def clear() -> None:
    session.pop(SESSION_KEY, None)


def build_lines(basket: dict[str, int], catalog: dict[str, Product]) -> list[BasketLine]:
    """Basket lines with current prices; products that are no longer in the catalog are skipped."""
    return [
        BasketLine(catalog[pid].id, catalog[pid].name, catalog[pid].price, qty)
        for pid, qty in basket.items()
        if pid in catalog
    ]
