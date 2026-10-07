"""Access to the transaction history."""

from __future__ import annotations

from datetime import date

from app import db, sql
from app.periods import next_month


def list_for_account_month(account_num: str, period: date) -> list[dict]:
    return db.fetch_all(
        sql.load("remittances/list_for_account_month.sql"),
        {
            "account_num": account_num,
            "period_start": period.isoformat(),
            "period_end": next_month(period).isoformat(),
        },
    )


def annotate_direction(operations: list[dict], account_num: str) -> list[dict]:
    """Add an ``incoming`` flag (money arrived on the account). The input list is not modified."""
    return [{**op, "incoming": op["receiver_account_id"] == account_num} for op in operations]
