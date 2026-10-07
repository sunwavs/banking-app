"""Access to the investment catalog (cached in Redis)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app import db, sql
from app.cache import get_cache

CATALOG_CACHE_KEY = "investments:catalog"


@dataclass(frozen=True)
class Product:
    id: int
    name: str
    price: Decimal
    stock: int  # units in stock (products.prod_balance)


def get_catalog() -> dict[str, Product]:
    """Return the catalog as ``{str(id): Product}``, cached in Redis for CACHE_TTL_SECONDS."""
    rows = get_cache().get_or_set(CATALOG_CACHE_KEY, lambda: db.fetch_all(sql.load("products/list.sql")))
    # A JSON cache returns Decimal values as strings/numbers, so they are normalized to one type.
    return {
        str(row["prod_id"]): Product(
            row["prod_id"], row["name"], Decimal(str(row["price"])), int(row["stock"])
        )
        for row in rows
    }


def invalidate_catalog() -> None:
    """Drop the cached catalog (call after the stock has changed)."""
    get_cache().delete(CATALOG_CACHE_KEY)
