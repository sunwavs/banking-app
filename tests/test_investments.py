"""Basket, orders and stock handling."""

from decimal import Decimal


def test_basket_uses_catalog_prices(login):
    c = login("alice")
    for _ in range(2):
        assert c.post("/investments/basket/add", data={"prod_id": "1"}).status_code == 302
    with c.session_transaction() as sess:
        assert sess["basket"] == {"1": 2}  # only the id and the quantity are stored in the cookie
    html = c.get("/investments/").get_data(as_text=True)
    assert "Количество: 2" in html and "201.00" in html and "Итого: 201.00" in html


def test_unknown_product_and_forbidden_get(login):
    c = login("alice")
    assert c.post("/investments/basket/add", data={"prod_id": "999"}).status_code == 404
    assert c.post("/investments/basket/add", data={"prod_id": "1' OR '1'='1"}).status_code == 404
    assert c.get("/investments/order").status_code == 405  # placing an order is not possible with GET
    assert c.get("/investments/basket/clear").status_code == 405


def test_order_is_created_atomically_and_basket_cleared(login, query):
    c = login("alice")
    c.post("/investments/basket/add", data={"prod_id": "1"})
    c.post("/investments/basket/add", data={"prod_id": "2"})
    c.post("/investments/basket/add", data={"prod_id": "2"})
    resp = c.post("/investments/order")
    assert resp.status_code == 302 and "order_id=1" in resp.headers["Location"]
    assert query("SELECT count(*) FROM orders")[0][0] == 1
    rows = query("SELECT prod_id, count_item, line_total FROM order_details ORDER BY prod_id")
    assert rows == [(1, 1, Decimal("100.50")), (2, 2, Decimal("40.00"))]
    assert query("SELECT user_id FROM orders") == [(1,)]  # the order belongs to the signed-in user
    with c.session_transaction() as sess:
        assert "basket" not in sess
    assert "Номер заказа: 1" in c.get(resp.headers["Location"]).get_data(as_text=True)


def test_empty_order_creates_nothing(login, query):
    c = login("alice")
    resp = c.post("/investments/order")
    assert resp.status_code == 302
    assert "Корзина пуста" in c.get("/investments/").get_data(as_text=True)
    assert query("SELECT count(*) FROM orders")[0][0] == 0


def test_failed_order_rolls_back(login, query):
    c = login("alice")
    c.post("/investments/basket/add", data={"prod_id": "1"})
    # make the insertion of an order line fail: no empty order may remain
    query("ALTER TABLE order_details ADD CONSTRAINT boom CHECK (count_item < 0)")
    try:
        c.application.config["PROPAGATE_EXCEPTIONS"] = False
        assert c.post("/investments/order").status_code == 500
    finally:
        query("ALTER TABLE order_details DROP CONSTRAINT boom")
    assert query("SELECT count(*) FROM orders")[0][0] == 0
    assert query("SELECT prod_balance FROM products WHERE prod_id = 1")[0][0] == 100  # stock restored


def _stock(query, prod_id=1):
    return query("SELECT prod_balance FROM products WHERE prod_id = %s", (prod_id,))[0][0]


def test_catalog_shows_stock(login):
    html = login("alice").get("/investments/").get_data(as_text=True)
    assert "В наличии: 100" in html


def test_out_of_stock_product_cannot_be_added(login, query):
    query("UPDATE products SET prod_balance = 0 WHERE prod_id = 1")
    c = login("alice")
    assert "Нет в наличии" in c.get("/investments/").get_data(as_text=True)
    c.post("/investments/basket/add", data={"prod_id": "1"})
    assert "Недостаточно товара" in c.get("/investments/").get_data(as_text=True)
    with c.session_transaction() as sess:
        assert "basket" not in sess


def test_cannot_put_more_into_the_basket_than_is_in_stock(login, query):
    query("UPDATE products SET prod_balance = 2 WHERE prod_id = 1")
    c = login("alice")
    for _ in range(3):
        c.post("/investments/basket/add", data={"prod_id": "1"})
    with c.session_transaction() as sess:
        assert sess["basket"] == {"1": 2}


def test_order_takes_the_goods_from_the_stock(login, query):
    c = login("alice")
    for _ in range(3):
        c.post("/investments/basket/add", data={"prod_id": "1"})
    c.post("/investments/basket/add", data={"prod_id": "2"})
    assert c.post("/investments/order").status_code == 302
    assert _stock(query, 1) == 97 and _stock(query, 2) == 99


def test_order_is_refused_atomically_when_the_stock_ran_out_meanwhile(login, query):
    c = login("alice")
    c.post("/investments/basket/add", data={"prod_id": "2"})
    c.post("/investments/basket/add", data={"prod_id": "1"})
    query("UPDATE products SET prod_balance = 0 WHERE prod_id = 1")  # another buyer took the last unit
    resp = c.post("/investments/order")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/investments/")
    assert "нет в наличии" in c.get("/investments/").get_data(as_text=True)
    # nothing is stored, and the line that could have been served was not taken either
    assert query("SELECT count(*) FROM orders")[0][0] == 0
    assert _stock(query, 2) == 100 and _stock(query, 1) == 0
