"""Password hashing and verification (bcrypt)."""

from __future__ import annotations

from functools import lru_cache

import bcrypt

_BCRYPT_ROUNDS = 12
_MAX_BYTES = 72  # bcrypt input limit (pgcrypto truncates the same way)


def _prepare(password: str) -> bytes:
    return password.encode("utf-8")[:_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt(_BCRYPT_ROUNDS)).decode()


@lru_cache(maxsize=1)
def _dummy_hash() -> bytes:
    return bcrypt.hashpw(b"dummy-password", bcrypt.gensalt(_BCRYPT_ROUNDS))


def verify_password(password: str, password_hash: str | None) -> bool:
    """Verify a password.

    If there is no hash, the same amount of work is still done: the response time does not
    reveal whether a login exists.
    """
    candidate = _prepare(password)
    if not password_hash:
        bcrypt.checkpw(candidate, _dummy_hash())
        return False
    try:
        return bcrypt.checkpw(candidate, password_hash.encode())
    except ValueError:  # malformed hash in the database
        return False
