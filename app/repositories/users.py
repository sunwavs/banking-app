"""Users of the web application: bank clients and bank staff."""

from __future__ import annotations

from dataclasses import dataclass

from app import db, sql
from app.security import verify_password


@dataclass(frozen=True)
class User:
    id: int
    login: str
    role: str
    contract_num: str | None = None  # set for bank clients (role "external") only


def _to_user(row: dict) -> User:
    return User(id=row["id"], login=row["login"], role=row["role"], contract_num=row["contract_num"])


def find_by_id(user_id: int) -> User | None:
    """Return an active user, or None if the user does not exist or has been deactivated."""
    row = db.fetch_one(sql.load("users/find_by_id.sql"), {"user_id": user_id})
    return _to_user(row) if row else None


def authenticate(login: str, password: str) -> User | None:
    row = db.fetch_one(sql.load("users/find_by_login.sql"), {"login": login.strip()})
    if row is None:
        verify_password(password, None)  # equalizes the response time for unknown logins
        return None
    if not verify_password(password, row["password_hash"]) or not row["is_active"]:
        return None
    return _to_user(row)
