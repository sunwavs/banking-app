"""Application configuration: everything is read from environment variables (see .env.example)."""

from __future__ import annotations

import os
from datetime import timedelta


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def load_config() -> dict:
    db_params = {
        "host": os.environ.get("DB_HOST", "127.0.0.1"),
        "port": _env_int("DB_PORT", 5432),
        "user": os.environ.get("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD", ""),
        "dbname": os.environ.get("DB_NAME", "Bank"),
        "connect_timeout": _env_int("DB_CONNECT_TIMEOUT", 5),
        # Calendar months (reports, history) are months in this time zone.
        "options": "-c timezone=" + os.environ.get("DB_TIMEZONE", "UTC"),
    }
    if not db_params["password"]:
        del db_params["password"]  # e.g. peer/trust authentication

    return {
        "SECRET_KEY": os.environ.get("SECRET_KEY", ""),
        "DB_PARAMS": db_params,
        "DB_POOL_MIN": _env_int("DB_POOL_MIN", 1),
        "DB_POOL_MAX": _env_int("DB_POOL_MAX", 10),
        "CACHE_ENABLED": _env_bool("CACHE_ENABLED", True),
        "REDIS_PARAMS": {
            "host": os.environ.get("REDIS_HOST", "127.0.0.1"),
            "port": _env_int("REDIS_PORT", 6379),
            "db": _env_int("REDIS_DB", 0),
        },
        "CACHE_TTL_SECONDS": _env_int("CACHE_TTL_SECONDS", 10),
        # The session is stored in a signed cookie that holds only the user id.
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": _env_bool("SESSION_COOKIE_SECURE", True),
        "PERMANENT_SESSION_LIFETIME": timedelta(minutes=_env_int("SESSION_LIFETIME_MINUTES", 30)),
        "LOGIN_RATE_LIMIT": os.environ.get("LOGIN_RATE_LIMIT", "10 per minute"),
        "RATELIMIT_STORAGE_URI": os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
        # Number of reverse proxies in front of the application (0 = none). The client address,
        # scheme and host are taken from the X-Forwarded-* headers of that many proxies.
        "PROXY_HOPS": _env_int("PROXY_HOPS", 0),
        "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO"),
    }
