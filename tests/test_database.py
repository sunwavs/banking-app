"""Tests of the database itself: constraints, the transfer trigger and the report procedures."""

import json
import threading
from datetime import UTC, datetime
from decimal import Decimal

import psycopg2
import pytest
from psycopg2 import errors

from app.security import verify_password
from tests.conftest import DB_PARAMS, ROOT


def _remit(query, amount, sender="11111111", receiver="33333333", moment=None):
    if moment is None:
        return query(
            "INSERT INTO remittances (amount, sender_account_id, receiver_account_id) VALUES (%s, %s, %s)",
            (amount, sender, receiver),
        )
    return query(
        "INSERT INTO remittances (amount, remittance_moment, sender_account_id, receiver_account_id) "
        "VALUES (%s, %s, %s, %s)",
        (amount, moment, sender, receiver),
    )


# ---------------------------------------------------------------- passwords


def test_plaintext_password_cannot_be_stored(query):
    with pytest.raises(errors.CheckViolation):
        query("INSERT INTO users (login, password_hash, role) VALUES ('x', 'secret', 'manager')")


def test_hash_password_function_produces_a_valid_bcrypt_hash(query):
    hashed = query("SELECT hash_password(%s)", ("my secret",))[0][0]
    assert verify_password("my secret", hashed) and not verify_password("other", hashed)
    query(
        "INSERT INTO users (login, password_hash, role) VALUES ('x', %s, 'manager')", (hashed,)
    )  # passes the CHECK


def test_user_role_and_contract_must_be_consistent(query):
    ok_hash = query("SELECT hash_password('p')")[0][0]
    with pytest.raises(errors.CheckViolation):  # a client needs a contract
        query("INSERT INTO users (login, password_hash, role) VALUES ('x', %s, 'external')", (ok_hash,))
    with pytest.raises(errors.CheckViolation):  # staff has no contract
        query(
            "INSERT INTO users (login, password_hash, role, contract_num) VALUES ('x', %s, 'manager', '1')",
            (ok_hash,),
        )
    with pytest.raises(errors.UniqueViolation):
        query("INSERT INTO users (login, password_hash, role) VALUES ('mgr', %s, 'manager')", (ok_hash,))


def test_database_roles_match_the_permission_manifest(query):
    in_db = {r[0] for r in query("SELECT unnest(enum_range(NULL::user_role))::text")}
    manifest = set(json.loads((ROOT / "app" / "access.json").read_text(encoding="utf-8")))
    assert in_db == manifest


# ---------------------------------------------------------------- column types


def test_account_number_columns_share_one_domain(query):
    rows = query(
        "SELECT table_name, column_name, domain_name FROM information_schema.columns "
        "WHERE table_schema = 'public' "
        "AND column_name IN ('account_num', 'sender_account_id', 'receiver_account_id')"
    )
    assert len(rows) == 5 and {r[2] for r in rows} == {"account_number"}


def test_contract_number_columns_have_one_type(query):
    rows = query(
        "SELECT table_name, data_type, character_maximum_length FROM information_schema.columns "
        "WHERE table_schema = 'public' AND column_name = 'contract_num'"
    )
    assert {r[0] for r in rows} == {"clients", "accounts", "users"}
    assert len({(r[1], r[2]) for r in rows}) == 1


def test_money_columns_share_the_exact_money_domain(query):
    cols = [
        ("accounts", "balance"),
        ("remittances", "amount"),
        ("sent_report", "sent_sum"),
        ("products", "prod_price"),
        ("order_details", "line_total"),
    ]
    for table, column in cols:
        domain = query(
            "SELECT domain_name FROM information_schema.columns WHERE table_schema = 'public' "
            "AND table_name = %s AND column_name = %s",
            (table, column),
        )[0][0]
        assert domain == "money_amount", f"{table}.{column}"
    assert query(
        "SELECT numeric_precision, numeric_scale FROM information_schema.domains "
        "WHERE domain_name = 'money_amount'"
    ) == [(18, 2)]


def test_money_has_no_floating_point_error(query):
    query(
        "INSERT INTO accounts (account_num, balance, contract_num) "
        "VALUES ('90000001', 1.00, '1'), ('90000002', 0, '1')"
    )
    for _ in range(3):
        _remit(query, "0.10", "90000001", "90000002")
    assert query("SELECT balance FROM accounts WHERE account_num = '90000001'") == [
        (Decimal("0.70"),)
    ]  # not 0.7000000000000001


# ---------------------------------------------------------------- transfer trigger


def _pgcode(query, *args, **kwargs):
    with pytest.raises(psycopg2.Error) as exc:
        _remit(query, *args, **kwargs)
    return exc.value.pgcode


def test_trigger_applies_the_remittance_to_both_balances(query):
    _remit(query, "250.25")
    assert query(
        "SELECT account_num, balance FROM accounts WHERE account_num IN ('11111111', '33333333') ORDER BY 1"
    ) == [("11111111", Decimal("749.75")), ("33333333", Decimal("750.25"))]


def test_trigger_checks_the_amount_being_transferred_not_earlier_remittances(query):
    # 11111111 already has a small remittance in its history (amount 10); a larger one must still fail
    assert _pgcode(query, 1000.01) == "RIS02"
    assert query("SELECT balance FROM accounts WHERE account_num = '11111111'")[0][0] == 1000


def test_trigger_allows_spending_exactly_the_whole_balance(query):
    _remit(query, 50, "22222222", "33333333")
    assert query("SELECT balance FROM accounts WHERE account_num = '22222222'")[0][0] == 0


@pytest.mark.parametrize(
    "kwargs,pgcode",
    [
        ({"amount": 0}, "23514"),  # amount must be positive
        ({"amount": -5}, "23514"),
        ({"amount": 1, "receiver": "11111111"}, "23514"),  # sender and receiver must differ
        ({"amount": 1, "receiver": "99999999"}, "23503"),  # unknown receiver
        ({"amount": 1, "sender": "99999999"}, "23503"),  # unknown sender
        ({"amount": 1, "sender": "abc"}, "23514"),  # malformed account number
        ({"amount": 1, "sender": "1234567"}, "23514"),  # too short
    ],
)
def test_invalid_remittances_are_rejected_by_the_database(query, kwargs, pgcode):
    assert _pgcode(query, **kwargs) == pgcode
    assert query("SELECT count(*) FROM remittances")[0][0] == 3


def test_last_change_follows_the_remittance_moment(query):
    moment = datetime(2024, 3, 1, 12, 0, tzinfo=UTC)
    _remit(query, 10, moment=moment)
    rows = query("SELECT last_change FROM accounts WHERE account_num IN ('11111111', '33333333')")
    assert all(r[0] == moment for r in rows)
    assert query("SELECT last_change FROM accounts WHERE account_num = '22222222'")[0][0] != moment


def test_opposite_transfers_do_not_deadlock(seeded):
    """A -> B and B -> A running at the same time from several connections: the accounts are
    locked in a fixed order, so no transaction is ever chosen as a deadlock victim."""
    rounds, failures, stop = 300, [], threading.Event()
    directions = [("11111111", "33333333"), ("33333333", "11111111")] * 2  # 4 connections
    barrier = threading.Barrier(len(directions))

    def worker(sender, receiver):
        conn = psycopg2.connect(**DB_PARAMS)
        try:
            barrier.wait()
            for _ in range(rounds):
                if stop.is_set():  # a failure was seen: do not wait for more deadlock timeouts
                    break
                try:
                    with conn, conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO remittances (amount, sender_account_id, receiver_account_id) "
                            "VALUES (1, %s, %s)",
                            (sender, receiver),
                        )
                except psycopg2.Error as exc:
                    failures.append(exc.pgcode)
                    stop.set()
        finally:
            conn.close()

    threads = [threading.Thread(target=worker, args=d) for d in directions]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert failures == []
    with seeded.cursor() as cur:  # every connection sent as much as it received
        cur.execute(
            "SELECT account_num, balance FROM accounts "
            "WHERE account_num IN ('11111111', '33333333') ORDER BY 1"
        )
        assert cur.fetchall() == [("11111111", Decimal("1000.00")), ("33333333", Decimal("500.00"))]


# ---------------------------------------------------------------- report procedures


def test_report_procedures_are_idempotent(query):
    for _ in range(2):
        query("CALL create_sent_report('2023-12-17')")
        query("CALL create_transfer_count_report('2023-12-31')")
    assert query("SELECT account_num, sent_sum FROM sent_report ORDER BY 1") == [
        ("11111111", Decimal("10.00")),
        ("33333333", Decimal("5.00")),
    ]
    assert query("SELECT account_num, transfer_count FROM transfer_count_report ORDER BY 1") == [
        ("11111111", 1),
        ("33333333", 1),
    ]


def test_report_period_is_the_calendar_month(query):
    _remit(query, 1, moment="2023-12-31 23:59:59+00")
    _remit(query, 2, moment="2024-01-01 00:00:00+00")
    query("CALL create_sent_report('2023-12-01')")
    assert query("SELECT sent_sum FROM sent_report WHERE account_num = '11111111'") == [
        (Decimal("11.00"),)
    ]  # 10 + 1


def test_report_tables_reject_duplicates_and_non_month_dates(query):
    query("INSERT INTO sent_report (report_date, account_num, sent_sum) VALUES ('2024-01-01', '11111111', 1)")
    with pytest.raises(errors.UniqueViolation):
        query(
            "INSERT INTO sent_report (report_date, account_num, sent_sum) "
            "VALUES ('2024-01-01', '11111111', 2)"
        )
    with pytest.raises(errors.CheckViolation):
        query(
            "INSERT INTO sent_report (report_date, account_num, sent_sum) "
            "VALUES ('2024-02-15', '11111111', 2)"
        )


# ---------------------------------------------------------------- ledger and users


def test_remittances_are_append_only(query):
    for statement in ("UPDATE remittances SET amount = 1", "DELETE FROM remittances"):
        with pytest.raises(psycopg2.Error) as exc:
            query(statement)
        assert exc.value.pgcode == "RIS03"
    assert query("SELECT count(*) FROM remittances")[0][0] == 3


@pytest.mark.parametrize("login", ["", " padded", "padded ", " "])
def test_login_must_not_be_empty_or_padded(query, login):
    # the application strips the login before the lookup, so such a user could never sign in
    hashed = query("SELECT hash_password('p')")[0][0]
    with pytest.raises(errors.CheckViolation):
        query("INSERT INTO users (login, password_hash, role) VALUES (%s, %s, 'manager')", (login, hashed))


def test_every_table_is_documented(query):
    undocumented = query(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'r' AND obj_description(c.oid) IS NULL"
    )
    assert undocumented == []
