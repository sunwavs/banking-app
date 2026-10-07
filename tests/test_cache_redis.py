"""Catalog cache on a real Redis server (skipped if Redis is unavailable)."""

import os

import pytest
import redis

from app.repositories.products import CATALOG_CACHE_KEY

REDIS = {
    "host": os.environ.get("REDIS_HOST", "127.0.0.1"),
    "port": int(os.environ.get("REDIS_PORT", "6379")),
    "db": 15,  # a separate Redis database so that foreign keys are left alone
}


@pytest.fixture
def redis_client():
    client = redis.Redis(**REDIS, decode_responses=True)
    try:
        client.ping()
    except redis.RedisError as exc:
        pytest.skip(f"Redis is unavailable: {exc}")
    client.flushdb()
    yield client
    client.flushdb()


def test_catalog_is_cached_with_ttl(make_app, redis_client, query):
    app = make_app(CACHE_ENABLED=True, REDIS_PARAMS=REDIS, CACHE_TTL_SECONDS=30)
    client = app.test_client()
    client.post("/lk/login", data={"login": "alice", "password": "alice-pass"})

    assert "Bond" in client.get("/investments/").get_data(as_text=True)
    assert 0 < redis_client.ttl(CATALOG_CACHE_KEY) <= 30

    query("UPDATE products SET prod_name = 'Changed' WHERE prod_id = 1")
    html = client.get("/investments/").get_data(as_text=True)
    assert "Bond" in html and "Changed" not in html  # the second request is served from the cache

    redis_client.delete(CATALOG_CACHE_KEY)
    assert "Changed" in client.get("/investments/").get_data(as_text=True)


def test_app_works_when_redis_is_down(make_app):
    app = make_app(CACHE_ENABLED=True, REDIS_PARAMS={"host": "127.0.0.1", "port": 1, "db": 0})
    client = app.test_client()
    client.post("/lk/login", data={"login": "alice", "password": "alice-pass"})
    resp = client.get("/investments/")
    assert resp.status_code == 200 and "Bond" in resp.get_data(as_text=True)
