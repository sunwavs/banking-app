def test_history_shows_direction(login):
    c = login("alice")
    html = c.get("/search/remittances_history?account=11111111&year=2023&month=12").get_data(as_text=True)
    assert "-10.00" in html and "Получатель: 33333333" in html  # outgoing
    assert "+5.00" in html and "Отправитель: 33333333" in html  # incoming
    assert "2023-12-05 10:00" in html  # timestamps are shown without seconds and offset
    assert "2024-01-02" not in html  # another month is not included


def test_empty_month(login):
    html = (
        login("alice")
        .get("/search/remittances_history?account=11111111&year=2020&month=1")
        .get_data(as_text=True)
    )
    assert "Нет информации об операциях" in html


def test_cannot_read_history_of_foreign_account(login):
    c = login("alice")
    assert c.get("/search/remittances_history?account=33333333&year=2023&month=12").status_code == 403
    assert c.get("/search/remittances_history?account=' OR 1=1 --&year=2023&month=12").status_code == 403


def test_bad_period_is_400_not_500(login):
    c = login("alice")
    for qs in ("year=abc&month=1", "year=2023&month=13", "year=1&month=1", "month=1"):
        assert c.get(f"/search/remittances_history?account=11111111&{qs}").status_code == 400, qs


def test_form_page(login):
    assert login("alice").get("/search/remittances_history").status_code == 200
