import threading
from decimal import Decimal

import pytest

from tests.conftest import PASSWORDS


def _balance(query, num):
    return query("SELECT balance FROM accounts WHERE account_num=%s", (num,))[0][0]


def _count(query):
    return query("SELECT count(*) FROM remittances")[0][0]


def _post(c, **kw):
    data = {"sender": "11111111", "receiver": "33333333", "trans_sum": "100"}
    data.update(kw)
    return c.post("/transfer/", data=data)


def test_successful_transfer_and_redirect_after_post(login, query):
    c = login("alice")
    resp = _post(c, trans_sum="100.50")
    assert resp.status_code == 302  # Post/Redirect/Get: refreshing the page does not repeat the transfer
    assert "успешно" in c.get("/transfer/").get_data(as_text=True)
    assert _balance(query, "11111111") == Decimal("899.50")
    assert _balance(query, "33333333") == Decimal("600.50")
    assert _count(query) == 4


def test_cannot_spend_from_someone_elses_account(login, query):
    c = login("alice")
    resp = _post(c, sender="33333333", receiver="22222222")  # 33333333 belongs to bob
    assert resp.status_code == 400 and "Счёт списания не найден" in resp.get_data(as_text=True)
    assert _balance(query, "33333333") == 500 and _count(query) == 3


@pytest.mark.parametrize(
    "kw,text",
    [
        ({"trans_sum": "0"}, "Некорректная сумма"),
        ({"trans_sum": "-1"}, "Некорректная сумма"),
        ({"trans_sum": "abc"}, "Некорректная сумма"),
        ({"trans_sum": "NaN"}, "Некорректная сумма"),
        ({"trans_sum": "0.001"}, "Некорректная сумма"),
        ({"trans_sum": "5000"}, "Недостаточно средств"),
        ({"trans_sum": "1000.01"}, "Недостаточно средств"),  # one cent more than the balance
        ({"receiver": "1234567"}, "Некорректный номер получателя"),  # 7 digits
        ({"receiver": "1234567890123"}, "Некорректный номер получателя"),  # 13 digits
        ({"receiver": "abcdefgh"}, "Некорректный номер получателя"),
        ({"receiver": ""}, "Некорректный номер получателя"),
        ({"receiver": "99999999"}, "Счёт получателя не найден"),
        ({"receiver": "11111111"}, "тот же счёт"),
        ({"sender": "' OR 1=1 --"}, "Счёт списания не найден"),
        ({"sender": "99999999"}, "Счёт списания не найден"),
    ],
)
def test_rejected_transfers_leave_no_trace(login, query, kw, text):
    resp = _post(login("alice"), **kw)
    assert resp.status_code == 400 and text in resp.get_data(as_text=True)
    assert _count(query) == 3 and _balance(query, "11111111") == 1000


def test_the_entire_balance_can_be_transferred(login, query):
    resp = _post(login("alice"), trans_sum="1000")
    assert resp.status_code == 302
    assert _balance(query, "11111111") == 0 and _balance(query, "33333333") == 1500


def test_sender_may_be_a_twelve_digit_account(login, query):
    query("INSERT INTO accounts (account_num, balance, contract_num) VALUES ('123456789012', 100, '1')")
    resp = _post(login("alice"), sender="123456789012", receiver="33333333", trans_sum="10")
    assert resp.status_code == 302 and _balance(query, "123456789012") == 90


def test_missing_form_fields_do_not_crash(login):
    assert login("alice").post("/transfer/", data={}).status_code == 400


def test_concurrent_transfers_cannot_overdraw(app, query):
    """Two simultaneous transfers of 600 from an account holding 1000: exactly one succeeds.
    The tests/hooks.sql trigger delays the transaction while the account locks are held,
    which widens the race window."""
    clients = []
    for _ in range(2):
        c = app.test_client()
        assert c.post("/lk/login", data={"login": "alice", "password": PASSWORDS["alice"]}).status_code == 302
        clients.append(c)

    barrier, codes = threading.Barrier(2), []

    def worker(c):
        barrier.wait()
        codes.append(_post(c, trans_sum="600").status_code)

    threads = [threading.Thread(target=worker, args=(c,)) for c in clients]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert sorted(codes) == [302, 400]
    assert _balance(query, "11111111") == 400
    assert _balance(query, "33333333") == 1100
