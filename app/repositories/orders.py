"""Creation of orders; the goods are taken from the stock in the same transaction."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app import db, sql


class OutOfStock(Exception):
    """Raised when a product is not available in the requested quantity."""

    def __init__(self, product_name: str) -> None:
        super().__init__(product_name)
        self.product_name = product_name


@dataclass(frozen=True)
class OrderLine:
    product_id: int
    name: str
    quantity: int
    total_price: Decimal  # total price of the line, stored in order_details.line_total


def create_order(user_id: int, lines: list[OrderLine]) -> int:
    """Create an order, take its lines from the stock and store them, atomically.

    Either everything is stored or nothing: if any product is out of stock the whole
    transaction is rolled back and OutOfStock is raised. Lines are processed in product id
    order so that concurrent orders lock the product rows in the same order (no deadlocks).
    """
    with db.transaction() as cur:
        cur.execute(sql.load("orders/create.sql"), {"user_id": user_id})
        order_id = cur.fetchone()["order_id"]
        for line in sorted(lines, key=lambda line: line.product_id):
            cur.execute(
                sql.load("orders/reserve_stock.sql"),
                {"prod_id": line.product_id, "count": line.quantity},
            )
            if cur.rowcount != 1:
                raise OutOfStock(line.name)
            cur.execute(
                sql.load("orders/insert_detail.sql"),
                {
                    "order_id": order_id,
                    "prod_id": line.product_id,
                    "count": line.quantity,
                    "line_total": line.total_price,
                },
            )
    return order_id
