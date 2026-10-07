"""End-to-end checks of the sandbox database (db/schema.sql + db/seed.sql).

Each test gets its own copy of a freshly created sandbox database and drives the application
through the demo users documented in db/seed.sql.
"""

from __future__ import annotations

import itertools
from decimal import Decimal

import psycopg2
import pytest

from app import create_app
from tests.conftest import DB_PARAMS, ROOT, _read, _test_config

PASSWORD = "sandbox-password"
TEMPLATE = "ris_sandbox_template"
_counter = itertools.count()


def _admin():
    conn = psycopg2.connect(**DB_PARAMS)
    conn.autocommit = True
    return conn


@pytest.fixture(scope="module")
def sandbox_template(_schema):
    admin = _admin()
    with admin.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {TEMPLATE} WITH (FORCE)")
        cur.execute(f"CREATE DATABASE {TEMPLATE}")
    conn = psycopg2.connect(**{**DB_PARAMS, "dbname": TEMPLATE})
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(_read(ROOT / "db" / "schema.sql"))
        cur.execute(_read(ROOT / "db" / "seed.sql"))
    conn.close()
    yield
    with admin.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {TEMPLATE} WITH (FORCE)")
    admin.close()


@pytest.fixture
def sandbox(sandbox_template):
    """A private copy of the sandbox database plus an application connected to it."""
    name = f"ris_sandbox_{next(_counter)}"
    admin = _admin()
    with admin.cursor() as cur:
        cur.execute(f"CREATE DATABASE {name} TEMPLATE {TEMPLATE}")
    params = {**DB_PARAMS, "dbname": name}
    app = create_app(_test_config(DB_PARAMS=params))
    conn = psycopg2.connect(**params)
    conn.autocommit = True

    class Sandbox:
        def client(self, login: str):
            c = app.test_client()
            resp = c.post("/lk/login", data={"login": login, "password": PASSWORD})
            assert resp.status_code == 302, f"{login} cannot sign in"
            return c

        def query(self, sql, args=None):
            with conn.cursor() as cur:
                cur.execute(sql, args)
                return cur.fetchall() if cur.description else None

    yield Sandbox()
    conn.close()
    app.extensions["db_pool"].close()
    with admin.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
    admin.close()


def test_every_demo_user_can_sign_in(sandbox):
    for login in ("client1", "client2", "client3", "manager1", "analyst1", "operator1"):
        sandbox.client(login)


def test_seed_balances_are_consistent_with_the_history(sandbox):
    rows = dict(sandbox.query("SELECT account_num, balance FROM accounts"))
    assert rows == {
        "10000001": Decimal("4764.75"),
        "10000002": Decimal("1424.75"),
        "20000001": Decimal("7770.00"),
        "30000001": Decimal("840.50"),
    }


def test_seed_passwords_are_stored_as_bcrypt_hashes(sandbox):
    hashes = [r[0] for r in sandbox.query("SELECT password_hash FROM users")]
    assert len(hashes) == 6 and all(h.startswith("$2a$12$") for h in hashes)
    assert "sandbox-password" not in " ".join(hashes)


def test_client_sees_only_own_accounts(sandbox):
    html = sandbox.client("client1").get("/lk/").get_data(as_text=True)
    assert "10000001" in html and "4764.75" in html and "10000002" in html
    assert "20000001" not in html


def test_history_for_a_seeded_month(sandbox):
    c = sandbox.client("client1")
    html = c.get("/search/remittances_history?account=10000001&year=2024&month=1").get_data(as_text=True)
    assert "-250.00" in html and "+100.00" in html and "-40.50" in html
    assert c.get("/search/remittances_history?account=20000001&year=2024&month=1").status_code == 403


def test_transfer_moves_money_through_the_trigger(sandbox):
    c = sandbox.client("client1")
    resp = c.post("/transfer/", data={"sender": "10000001", "receiver": "20000001", "trans_sum": "100"})
    assert resp.status_code == 302
    rows = dict(sandbox.query("SELECT account_num, balance FROM accounts"))
    assert rows["10000001"] == Decimal("4664.75") and rows["20000001"] == Decimal("7870.00")


def test_transfer_larger_than_balance_is_refused(sandbox):
    resp = sandbox.client("client3").post(
        "/transfer/", data={"sender": "30000001", "receiver": "10000001", "trans_sum": "900"}
    )
    assert resp.status_code == 400 and "Недостаточно средств" in resp.get_data(as_text=True)
    assert sandbox.query("SELECT balance FROM accounts WHERE account_num = '30000001'") == [
        (Decimal("840.50"),)
    ]


def test_reports_for_the_seeded_period(sandbox):
    analyst = sandbox.client("analyst1")
    for slug in ("sent-sum", "transfer-count"):
        resp = analyst.post(f"/reports/{slug}/new", data={"MonthReport": "1", "YearReport": "2024"})
        assert resp.status_code == 302
    sent = sandbox.query("SELECT account_num, sent_sum FROM sent_report ORDER BY account_num")
    assert sent == [("10000001", Decimal("290.50")), ("20000001", Decimal("100.00"))]
    counts = sandbox.query(
        "SELECT account_num, transfer_count FROM transfer_count_report ORDER BY account_num"
    )
    assert counts == [("10000001", 2), ("20000001", 1)]

    manager = sandbox.client("manager1")
    assert manager.get("/reports/sent-sum/2024-01").status_code == 200
    assert (
        manager.post("/reports/sent-sum/new", data={"MonthReport": "2", "YearReport": "2024"}).status_code
        == 403
    )
    assert sandbox.client("operator1").get("/reports/").status_code == 403


def test_client_can_place_an_order(sandbox):
    c = sandbox.client("client2")
    assert c.post("/investments/basket/add", data={"prod_id": "1"}).status_code == 302
    assert c.post("/investments/order").status_code == 302
    assert sandbox.query("SELECT user_id FROM orders") == [(2,)]  # client2 is the second user
    assert sandbox.query("SELECT prod_id, count_item, line_total FROM order_details") == [
        (1, 1, Decimal("100.00"))
    ]
    assert sandbox.query("SELECT prod_balance FROM products WHERE prod_id = 1") == [
        (99,)
    ]  # one unit left the stock
