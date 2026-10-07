"""Redis-backed cache.

* The client is created once at application start-up, not per request.
* The cache key is chosen by the caller.
* If Redis is unavailable the application keeps working and recomputes the value.
* An empty result (``[]``) is a valid cached value, not a miss.
* The TTL is set atomically (``SET ... EX``).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import redis
from flask import Flask, current_app

log = logging.getLogger(__name__)
_MISS = object()


class RedisCache:
    def __init__(self, client: redis.Redis | None, default_ttl: int) -> None:
        self._client = client
        self._default_ttl = default_ttl

    def _get(self, key: str) -> Any:
        if self._client is None:
            return _MISS
        try:
            raw = self._client.get(key)
        except redis.RedisError as exc:
            log.warning("cache get failed for %r: %s", key, exc)
            return _MISS
        if raw is None:
            return _MISS
        try:
            return json.loads(raw)
        except ValueError:
            log.warning("cache value for %r is not valid JSON, ignoring it", key)
            return _MISS

    def _set(self, key: str, value: Any, ttl: int) -> None:
        if self._client is None or ttl <= 0:
            return
        try:
            # default=str: Decimal/date are serialized as strings; the caller restores the types.
            self._client.set(key, json.dumps(value, default=str), ex=ttl)
        except (redis.RedisError, TypeError) as exc:
            log.warning("cache set failed for %r: %s", key, exc)

    def delete(self, key: str) -> None:
        if self._client is None:
            return
        try:
            self._client.delete(key)
        except redis.RedisError as exc:
            log.warning("cache delete failed for %r: %s", key, exc)

    def get_or_set(self, key: str, factory: Callable[[], Any], ttl: int | None = None) -> Any:
        hit = self._get(key)
        if hit is not _MISS:
            return hit
        value = factory()
        self._set(key, value, self._default_ttl if ttl is None else ttl)
        return value


def init_app(app: Flask) -> None:
    client = None
    if app.config["CACHE_ENABLED"]:
        client = redis.Redis(
            **app.config["REDIS_PARAMS"],
            decode_responses=True,
            socket_timeout=1,
            socket_connect_timeout=1,
        )
    app.extensions["cache"] = RedisCache(client, app.config["CACHE_TTL_SECONDS"])


def get_cache() -> RedisCache:
    return current_app.extensions["cache"]
