import pytest

from tests.conftest import APP_DB_PARAMS, PASSWORDS


def test_session_holds_only_the_user_id(client):
    resp = client.post("/lk/login", data={"login": "alice", "password": PASSWORDS["alice"]})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/lk/")
    with client.session_transaction() as sess:
        assert sess["user_id"] == 1
        # the cookie is signed but readable: neither the password nor the role may be in it
        assert not {"password", "login", "role", "contract_num"} & set(sess)


def test_login_wrong_password(client):
    resp = client.post("/lk/login", data={"login": "alice", "password": "nope"})
    assert resp.status_code == 200
    assert "Неправильный логин или пароль" in resp.get_data(as_text=True)
    with client.session_transaction() as sess:
        assert "user" not in sess


@pytest.mark.parametrize(
    "login,password",
    [
        ("' OR '1'='1", "' OR '1'='1"),
        ("alice' --", "x"),
        ("alice", "' OR trim(password_hash) <> '"),
        ("", ""),
    ],
)
def test_login_sql_injection_does_not_work(client, login, password):
    resp = client.post("/lk/login", data={"login": login, "password": password})
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        assert "user" not in sess


def test_internal_user_gets_permissions_of_the_role(login):
    assert login("mgr").get("/reports/").status_code == 200


def test_unauthenticated_redirects_to_login(client):
    for url in ("/lk/", "/transfer/", "/search/", "/investments/", "/reports/"):
        resp = client.get(url)
        assert resp.status_code == 302 and "/lk/login" in resp.headers["Location"], url


def test_logout_is_post_only_and_clears_session(login):
    c = login("alice")
    assert c.get("/lk/logout").status_code == 405
    assert c.post("/lk/logout").status_code == 200
    with c.session_transaction() as sess:
        assert "user" not in sess
    assert c.get("/lk/").status_code == 302


@pytest.mark.parametrize(
    "user,url,status",
    [
        ("alice", "/reports/", 403),
        ("mgr", "/transfer/", 403),
        ("mgr", "/reports/sent-sum/new", 403),
        ("ana", "/reports/sent-sum/new", 200),
        ("op", "/reports/", 403),
        ("op", "/lk/", 200),
    ],
)
def test_permissions(login, user, url, status):
    assert login(user).get(url).status_code == status


def test_csrf_enforced(make_app):
    client = make_app(WTF_CSRF_ENABLED=True).test_client()
    resp = client.post("/lk/login", data={"login": "alice", "password": PASSWORDS["alice"]})
    assert resp.status_code == 400


def test_login_rate_limit(make_app):
    client = make_app(RATELIMIT_ENABLED=True, LOGIN_RATE_LIMIT="3 per minute").test_client()
    codes = [
        client.post("/lk/login", data={"login": "alice", "password": "bad"}).status_code for _ in range(5)
    ]
    assert codes[:3] == [200, 200, 200] and codes[3:] == [429, 429]


def test_missing_secret_key_fails_fast(monkeypatch):
    from app import create_app

    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        create_app()


def test_every_post_form_carries_csrf_token(make_app):
    """End-to-end scenario with CSRF enabled: tokens are taken from the rendered pages."""
    import re

    client = make_app(WTF_CSRF_ENABLED=True).test_client()

    def token(url):
        html = client.get(url).get_data(as_text=True)
        found = re.search(r'name="csrf_token" value="([^"]+)"', html)
        assert found, f"no csrf_token on {url}"
        return found.group(1)

    assert (
        client.post(
            "/lk/login",
            data={"login": "alice", "password": PASSWORDS["alice"], "csrf_token": token("/lk/login")},
        ).status_code
        == 302
    )
    assert (
        client.post(
            "/transfer/",
            data={
                "sender": "11111111",
                "receiver": "33333333",
                "trans_sum": "1",
                "csrf_token": token("/transfer/"),
            },
        ).status_code
        == 302
    )
    client.post("/investments/basket/add", data={"prod_id": "1", "csrf_token": token("/investments/")})
    assert client.post("/investments/order", data={"csrf_token": token("/investments/")}).status_code == 302
    # the same request without a token is rejected
    assert client.post("/investments/order").status_code == 400
    assert client.post("/lk/logout", data={"csrf_token": token("/lk/")}).status_code == 200


def test_role_change_applies_immediately(login, query):
    c = login("ana")
    assert c.get("/reports/sent-sum/new").status_code == 200
    query("UPDATE users SET role = 'operator' WHERE login = 'ana'")
    assert c.get("/reports/sent-sum/new").status_code == 403


def test_deactivated_user_loses_access_and_cannot_sign_in(login, query):
    c = login("alice")
    assert c.get("/lk/").status_code == 200
    query("UPDATE users SET is_active = false WHERE login = 'alice'")
    resp = c.get("/lk/")
    assert resp.status_code == 302 and "/lk/login" in resp.headers["Location"]
    with c.session_transaction() as sess:
        assert "user_id" not in sess
    resp = c.post("/lk/login", data={"login": "alice", "password": PASSWORDS["alice"]})
    assert resp.status_code == 200 and "Неправильный логин или пароль" in resp.get_data(as_text=True)


def test_error_page_renders_when_the_database_is_down(make_app):
    app = make_app(DB_PARAMS={**APP_DB_PARAMS, "port": 1})  # nothing listens there
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = 1
    resp = client.get("/lk/")
    assert resp.status_code == 503 and "Сервис временно недоступен" in resp.get_data(as_text=True)


def test_signed_in_user_is_redirected_from_the_login_form(login):
    resp = login("alice").get("/lk/login")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/lk/")


def test_error_pages_share_one_layout(login):
    c = login("alice")
    for resp, status in ((c.get("/lk/logout"), 405), (c.get("/reports/"), 403), (c.get("/nowhere"), 404)):
        assert resp.status_code == status
        assert "<html lang=" in resp.get_data(as_text=True)  # the common template, not a bare server page


def test_signing_in_again_switches_the_user(client):
    """A POST with other credentials replaces the current session; only the GET is redirected."""
    for name, expected_id in (("alice", 1), ("mgr", 3)):
        resp = client.post("/lk/login", data={"login": name, "password": PASSWORDS[name]})
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            assert sess["user_id"] == expected_id
