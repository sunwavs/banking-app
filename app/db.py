"""PostgreSQL access: connection pool and transactions.

* The pool is created lazily: the application starts without a database and fails on first use.
* Every operation takes a connection from the pool and returns it afterwards.
* Exceptions are never swallowed: the transaction is rolled back and the error propagates
  (and is turned into a 503/500 page in app.errors).
"""

from __future__ import annotations

import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from flask import Flask, current_app
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

Params = Mapping[str, Any] | None


class _LazyPool:
    def __init__(self, params: dict, minconn: int, maxconn: int) -> None:
        self._params = params
        self._minconn = minconn
        self._maxconn = maxconn
        self._pool: ThreadedConnectionPool | None = None
        self._lock = threading.Lock()

    def get(self) -> ThreadedConnectionPool:
        if self._pool is None:
            with self._lock:
                if self._pool is None:
                    self._pool = ThreadedConnectionPool(self._minconn, self._maxconn, **self._params)
        return self._pool

    def close(self) -> None:
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None


def init_app(app: Flask) -> None:
    app.extensions["db_pool"] = _LazyPool(
        app.config["DB_PARAMS"], app.config["DB_POOL_MIN"], app.config["DB_POOL_MAX"]
    )


@contextmanager
def transaction() -> Iterator[RealDictCursor]:
    """Yield a cursor inside a transaction: commit on success, rollback on any exception."""
    pool = current_app.extensions["db_pool"].get()
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.commit()
    except BaseException:
        if not conn.closed:
            conn.rollback()
        raise
    finally:
        pool.putconn(conn, close=bool(conn.closed))


def fetch_all(sql: str, params: Params = None) -> list[dict]:
    with transaction() as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def fetch_one(sql: str, params: Params = None) -> dict | None:
    with transaction() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row is not None else None


def execute(sql: str, params: Params = None) -> int:
    """Run a statement without a result set and return the number of affected rows."""
    with transaction() as cur:
        cur.execute(sql, params)
        return cur.rowcount
