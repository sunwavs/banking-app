"""Loading of SQL queries from the app/sql directory.

Queries are stored in .sql files. Values are passed ONLY through database driver
parameters (``%(name)s``); queries are never built by string concatenation.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parent / "sql"


@cache
def load(name: str) -> str:
    """Return the query text, e.g. ``load("users/find_by_login.sql")``."""
    return (SQL_DIR / name).read_text(encoding="utf-8")
