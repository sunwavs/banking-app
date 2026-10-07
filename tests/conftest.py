"""Shared fixtures.

Integration tests run against a real PostgreSQL server (DB_* / TEST_DB_* variables) using the
production schema from db/schema.sql plus the test-only trigger from tests/hooks.sql.
If the database is unavailable these tests are skipped; unit tests need no database.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg2
import pytest

from app import create_app
from app.security import hash_password

ROOT = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent

DB_PARAMS = {
    "host": os.environ.get("TEST_DB_HOST", os.environ.get("DB_HOST", "127.0.0.1")),
    "port": int(os.environ.get("TEST_DB_PORT", os.environ.get("DB_PORT", "5432"))),
    "user": os.environ.get("TEST_DB_USER", os.environ.get("DB_USER", "ris")),
    "password": os.environ.get("TEST_DB_PASSWORD", os.environ.get("DB_PASSWORD", "ris")),
    "dbname": os.environ.get("TEST_DB_NAME", os.environ.get("DB_NAME", "ris_test")),
}

# The application keeps the database session in UTC (calendar months are UTC months).
APP_DB_PARAMS = {**DB_PARAMS, "options": "-c timezone=UTC"}

PASSWORDS = {"alice": "alice-pass", "bob": "bob-pass", "mgr": "mgr-pass", "ana": "ana-pass", "op": "op-pass"}


def _test_config(**overrides) -> dict:
    cfg = {
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "DB_PARAMS": APP_DB_PARAMS,
        "CACHE_ENABLED": False,
        "SESSION_COOKIE_SECURE": False,
        "WTF_CSRF_ENABLED": False,
        "RATELIMIT_ENABLED": False,
        "LOG_LEVEL": "WARNING",
    }
    cfg.update(overrides)
    return cfg


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def _schema():
    try:
        conn = psycopg2.connect(**DB_PARAMS)
    except psycopg2.OperationalError as exc:
        pytest.skip(f"PostgreSQL is unavailable: {exc}")
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(_read(TESTS / "teardown.sql"))
        cur.execute(_read(ROOT / "db" / "schema.sql"))
        cur.execute(_read(TESTS / "hooks.sql"))
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def _hashes():
    # bcrypt is intentionally slow, so the hashes are computed once per session
    return {name: hash_password(pw) for name, pw in PASSWORDS.items()}


@pytest.fixture
def seeded(_schema, _hashes):
    """Reset the data before every test."""
    h = _hashes
    with _schema.cursor() as cur:
        cur.execute(
            "TRUNCATE order_details, orders, products, sent_report, transfer_count_report, "
            "remittances, accounts, users, clients RESTART IDENTITY CASCADE"
        )
        cur.execute(
            "INSERT INTO clients (contract_num, last_name, phone_num, reg_date) VALUES "
            "('1', 'Client A', '0', '2020-01-01'), ('2', 'Client B', '0', '2020-01-01')"
        )
        cur.execute(
            "INSERT INTO accounts (account_num, balance, last_change, contract_num) VALUES "
            "('11111111', 1000, '2024-01-01+00', '1'), ('22222222', 50, '2024-01-01+00', '1'), "
            "('33333333', 500, '2024-01-01+00', '2')"
        )
        # Load the history with the triggers disabled so that it does not move the balances.
        cur.execute("ALTER TABLE remittances DISABLE TRIGGER USER")
        cur.execute(
            """INSERT INTO remittances
               (amount, remittance_moment, sender_account_id, receiver_account_id) VALUES
               (10, '2023-12-05 10:00+00', '11111111', '33333333'),
               (5,  '2023-12-15 12:30+00', '33333333', '11111111'),
               (7,  '2024-01-02 09:00+00', '11111111', '33333333')"""
        )
        cur.execute("ALTER TABLE remittances ENABLE TRIGGER USER")
        cur.execute(
            "INSERT INTO users (login, password_hash, role, contract_num) VALUES "
            "('alice', %s, 'external', '1'), ('bob', %s, 'external', '2'), "
            "('mgr', %s, 'manager', NULL), ('ana', %s, 'analyst', NULL), ('op', %s, 'operator', NULL)",
            (h["alice"], h["bob"], h["mgr"], h["ana"], h["op"]),
        )
        cur.execute(
            "INSERT INTO products (prod_name, prod_price, prod_balance) VALUES "
            "('Bond', 100.50, 100), ('Share', 20, 100)"
        )
    return _schema


@pytest.fixture
def app(seeded):
    app = create_app(_test_config())
    yield app
    app.extensions["db_pool"].close()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login(client):
    def _login(name: str):
        resp = client.post("/lk/login", data={"login": name, "password": PASSWORDS[name]})
        assert resp.status_code == 302, resp.get_data(as_text=True)
        return client

    return _login


@pytest.fixture
def make_app(seeded):
    """Application factory for non-default configurations (CSRF, rate limiting, ...)."""
    created = []

    def _make(**overrides):
        a = create_app(_test_config(**overrides))
        created.append(a)
        return a

    yield _make
    for a in created:
        a.extensions["db_pool"].close()


@pytest.fixture
def query(seeded):
    def _q(sql, params=None):
        with seeded.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else None

    return _q
