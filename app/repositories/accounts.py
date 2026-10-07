"""Access to accounts."""

from __future__ import annotations

from app import db, sql


def list_for_contract(contract_num: str) -> list[dict]:
    return db.fetch_all(sql.load("accounts/list_by_contract.sql"), {"contract_num": contract_num})
