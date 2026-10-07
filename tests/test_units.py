"""Unit tests that need no database."""

from datetime import date

import pytest
import redis

from app.cache import RedisCache
from app.periods import next_month, parse_period_slug, parse_year_month
from app.repositories.transfers import TransferError, parse_amount
from app.security import hash_password, verify_password


@pytest.mark.parametrize(
    "raw,expected", [("10", "10"), ("10.5", "10.5"), ("10,25", "10.25"), (" 0.01 ", "0.01")]
)
def test_parse_amount_ok(raw, expected):
    assert str(parse_amount(raw)) == expected


@pytest.mark.parametrize("raw", ["0", "-5", "abc", "", "NaN", "Infinity", "1e999", "1.001", "1000000000"])
def test_parse_amount_rejects(raw):
    with pytest.raises(TransferError):
        parse_amount(raw)


def test_periods():
    assert parse_year_month("2023", "12") == date(2023, 12, 1)
    assert next_month(date(2023, 12, 1)) == date(2024, 1, 1)
    assert parse_period_slug("2023-12") == date(2023, 12, 1)
    for bad in [("x", "1"), ("2023", "13"), ("1800", "1"), (None, None)]:
        with pytest.raises(ValueError):
            parse_year_month(*bad)
    with pytest.raises(ValueError):
        parse_period_slug("23-12-01")


def test_password_hashing():
    h = hash_password("secret")
    assert verify_password("secret", h)
    assert not verify_password("other", h)
    assert not verify_password("secret", None)
    assert not verify_password("secret", "not-a-hash")
    long_pw = "я" * 100  # more than 72 bytes must not raise
    assert verify_password(long_pw, hash_password(long_pw))


class FakeRedis:
    def __init__(self):
        self.data, self.sets = {}, []

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value, ex=None):
        self.data[key] = value
        self.sets.append((key, ex))


class BrokenRedis:
    def get(self, key):
        raise redis.ConnectionError("down")

    def set(self, *a, **k):
        raise redis.ConnectionError("down")


def test_cache_hit_miss_and_empty_list():
    cache, calls = RedisCache(FakeRedis(), 10), []

    def factory():
        calls.append(1)
        return []

    assert cache.get_or_set("k", factory) == []
    assert cache.get_or_set("k", factory) == []  # an empty list is a cache hit, not a miss
    assert len(calls) == 1


def test_cache_sets_ttl_atomically():
    fake = FakeRedis()
    RedisCache(fake, 10).get_or_set("k", lambda: {"a": 1})
    assert fake.sets == [("k", 10)]


def test_cache_degrades_when_redis_down():
    assert RedisCache(BrokenRedis(), 10).get_or_set("k", lambda: [1]) == [1]


def test_cache_delete():
    fake = FakeRedis()
    fake.delete = lambda key: fake.data.pop(key, None)
    cache = RedisCache(fake, 10)
    cache.get_or_set("k", lambda: 1)
    cache.delete("k")
    assert cache.get_or_set("k", lambda: 2) == 2


def test_cache_delete_survives_redis_outage():
    class Broken:
        def delete(self, key):
            raise redis.ConnectionError("down")

    RedisCache(Broken(), 10).delete("k")  # must not raise


def test_cache_disabled():
    assert RedisCache(None, 10).get_or_set("k", lambda: 42) == 42


def test_cache_ignores_a_corrupt_value():
    fake = FakeRedis()
    fake.data["k"] = "{not json"
    assert RedisCache(fake, 10).get_or_set("k", lambda: [1]) == [1]
