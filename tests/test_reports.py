import pytest


def test_create_sent_sum_report(login, query):
    c = login("ana")
    resp = c.post("/reports/sent-sum/new", data={"MonthReport": "12", "YearReport": "2023"})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/reports/sent-sum/2023-12")
    html = c.get(resp.headers["Location"]).get_data(as_text=True)
    assert "11111111" in html and "33333333" in html
    # creating the same report again does not produce duplicates
    resp = c.post("/reports/sent-sum/new", data={"MonthReport": "12", "YearReport": "2023"})
    assert "уже существует" in c.get(resp.headers["Location"]).get_data(as_text=True)
    assert query("SELECT count(*) FROM sent_report")[0][0] == 2


def test_transfer_count_report_is_wired_to_its_own_data(login):
    c = login("ana")
    c.post("/reports/transfer-count/new", data={"MonthReport": "12", "YearReport": "2023"})
    html = c.get("/reports/transfer-count/2023-12").get_data(as_text=True)
    assert "Количество переводов" in html and "sent_sum" not in html
    assert "2023-12" in c.get("/reports/transfer-count/").get_data(as_text=True)
    assert "2023-12" not in c.get("/reports/sent-sum/").get_data(as_text=True)


def test_no_data_month(login):
    resp = login("ana").post("/reports/sent-sum/new", data={"MonthReport": "5", "YearReport": "2020"})
    assert resp.status_code == 200 and "Нет информации" in resp.get_data(as_text=True)


def test_manager_can_view_but_not_create(login):
    login("ana").post("/reports/sent-sum/new", data={"MonthReport": "12", "YearReport": "2023"})
    c = login("mgr")
    assert c.get("/reports/sent-sum/2023-12").status_code == 200
    assert c.post("/reports/sent-sum/new", data={"MonthReport": "1", "YearReport": "2024"}).status_code == 403


@pytest.mark.parametrize(
    "url",
    [
        "/reports/unknown/",
        "/reports/sent-sum/23-12",
        "/reports/sent-sum/garbage",
        "/reports/sent-sum/2020-01",
    ],
)
def test_bad_urls_are_404(login, url):
    assert login("ana").get(url).status_code == 404


def test_bad_form_is_400(login):
    assert (
        login("ana")
        .post("/reports/sent-sum/new", data={"MonthReport": "x", "YearReport": "2023"})
        .status_code
        == 400
    )


def test_report_creation_is_atomic(login, query):
    """A report is stored completely or not at all: one failing row rolls back the whole procedure."""
    query("ALTER TABLE sent_report ADD CONSTRAINT reject_five CHECK (sent_sum <> 5)")
    try:
        c = login("ana")
        c.application.config["PROPAGATE_EXCEPTIONS"] = False
        assert (
            c.post("/reports/sent-sum/new", data={"MonthReport": "12", "YearReport": "2023"}).status_code
            == 500
        )
    finally:
        query("ALTER TABLE sent_report DROP CONSTRAINT reject_five")
    assert query("SELECT count(*) FROM sent_report")[0][0] == 0
