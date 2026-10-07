"""Project-wide quality checks: HTTP headers, template hygiene, valid HTML, no dead SQL, English comments."""

import ast
import io
import re
import tokenize

import html5lib
import pytest

from tests.conftest import PASSWORDS, ROOT

APP = ROOT / "app"


# ---------------------------------------------------------------- HTTP headers


def test_pages_carry_security_headers(client):
    resp = client.get("/lk/login")
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in resp.headers["Content-Security-Policy"]
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "same-origin"
    assert resp.headers["Cache-Control"] == "no-store"
    assert "Strict-Transport-Security" not in resp.headers  # the test configuration is plain http


def test_hsts_is_sent_when_deployed_over_https(make_app):
    resp = make_app(SESSION_COOKIE_SECURE=True).test_client().get("/lk/login")
    assert resp.headers["Strict-Transport-Security"].startswith("max-age=")


def test_static_files_are_cacheable_but_still_protected(client):
    resp = client.get("/static/css/app.css")
    assert resp.status_code == 200
    assert "no-store" not in resp.headers.get("Cache-Control", "")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_error_pages_carry_security_headers(client):
    resp = client.get("/no-such-page")
    assert resp.status_code == 404 and "Content-Security-Policy" in resp.headers


# ---------------------------------------------------------------- reverse proxy


def _attempt(client, address, forwarded):
    return client.post(
        "/lk/login",
        data={"login": "alice", "password": "bad"},
        headers={"X-Forwarded-For": forwarded},
        environ_overrides={"REMOTE_ADDR": address},
    ).status_code


def test_forwarded_address_is_used_behind_a_proxy(make_app):
    app = make_app(RATELIMIT_ENABLED=True, LOGIN_RATE_LIMIT="2 per minute", PROXY_HOPS=1)
    client = app.test_client()
    codes = [_attempt(client, "10.9.0.1", "203.0.113.1") for _ in range(3)]
    assert codes == [200, 200, 429]  # one client, three attempts
    assert _attempt(client, "10.9.0.1", "203.0.113.2") == 200  # another client behind the same proxy


def test_forwarded_address_is_ignored_without_a_proxy(make_app):
    app = make_app(RATELIMIT_ENABLED=True, LOGIN_RATE_LIMIT="2 per minute", PROXY_HOPS=0)
    client = app.test_client()
    codes = [_attempt(client, "10.9.0.2", f"203.0.113.{n}") for n in range(3)]
    assert codes == [200, 200, 429]  # a spoofed header does not give a fresh allowance


# ---------------------------------------------------------------- templates


def test_templates_have_no_inline_styles_or_scripts():
    """The Content-Security-Policy forbids them, so they would silently not work."""
    offenders = []
    for path in APP.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"\sstyle\s*=|<style|<script(?![^>]*\ssrc=)|\son[a-z]+\s*=", text):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def _render_pages(app, make_client):
    """Yield (description, html) for every kind of page of the application."""
    anonymous = app.test_client()
    yield "home", anonymous.get("/").get_data(as_text=True)
    yield "login", anonymous.get("/lk/login").get_data(as_text=True)
    yield (
        "login error",
        anonymous.post("/lk/login", data={"login": "x", "password": "y"}).get_data(as_text=True),
    )
    yield "404", anonymous.get("/no-such-page").get_data(as_text=True)

    client = make_client("alice")
    for url in (
        "/lk/",
        "/search/",
        "/search/remittances_history",
        "/search/remittances_history?account=11111111&year=2023&month=12",
        "/search/remittances_history?account=11111111&year=2020&month=1",
        "/search/remittances_history?account=11111111&year=abc&month=1",
        "/transfer/",
        "/investments/",
        "/reports/",  # 403 for a client
    ):
        yield url, client.get(url).get_data(as_text=True)
    yield "transfer error", client.post("/transfer/", data={"trans_sum": "0"}).get_data(as_text=True)
    client.post("/investments/basket/add", data={"prod_id": "1"})
    yield "basket", client.get("/investments/").get_data(as_text=True)
    resp = client.post("/investments/order")
    yield "order done", client.get(resp.headers["Location"]).get_data(as_text=True)
    yield "logout", client.post("/lk/logout").get_data(as_text=True)

    analyst = make_client("ana")
    analyst.post("/reports/sent-sum/new", data={"MonthReport": "12", "YearReport": "2023"})
    for url in (
        "/reports/",
        "/reports/sent-sum/",
        "/reports/sent-sum/new",
        "/reports/sent-sum/2023-12",
        "/reports/transfer-count/",
    ):
        yield url, analyst.get(url).get_data(as_text=True)
    yield (
        "no data",
        analyst.post("/reports/sent-sum/new", data={"MonthReport": "5", "YearReport": "2020"}).get_data(
            as_text=True
        ),
    )


def test_every_page_is_valid_html(app):
    def make_client(name):
        c = app.test_client()
        resp = c.post("/lk/login", data={"login": name, "password": PASSWORDS[name]})
        assert resp.status_code == 302
        return c

    parser = html5lib.HTMLParser(strict=True)
    checked = 0
    for description, page in _render_pages(app, make_client):
        try:
            parser.parse(page)
        except html5lib.html5parser.ParseError as exc:
            pytest.fail(f"invalid HTML on {description}: {exc}")
        assert "<html lang=" in page, description
        checked += 1
    assert checked >= 20  # guards against the page list silently becoming empty


# ---------------------------------------------------------------- code hygiene


def test_every_sql_file_is_used_and_every_referenced_file_exists():
    on_disk = {p.relative_to(APP / "sql").as_posix() for p in (APP / "sql").rglob("*.sql")}
    referenced = set()
    for path in APP.rglob("*.py"):
        referenced |= set(re.findall(r'"([a-z_]+/[a-z_]+\.sql)"', path.read_text(encoding="utf-8")))
    assert referenced == on_disk


def test_comments_and_docstrings_are_in_english():
    cyrillic = re.compile("[А-Яа-яЁё]")
    offenders = []
    for path in [*ROOT.glob("*.py"), *APP.rglob("*.py"), *(ROOT / "tests").glob("*.py")]:
        source = path.read_text(encoding="utf-8")
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT and cyrillic.search(token.string):
                offenders.append(f"{path.relative_to(ROOT)}:{token.start[0]}")
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                doc = ast.get_docstring(node, clean=False)
                if doc and cyrillic.search(doc):
                    offenders.append(
                        f"{path.relative_to(ROOT)}: docstring of {getattr(node, 'name', 'module')}"
                    )
    for path in [*(ROOT / "db").glob("*.sql"), *APP.rglob("*.sql")]:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "--" in line and cyrillic.search(line.split("--", 1)[1]):
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == []
