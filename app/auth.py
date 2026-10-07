"""User session handling and permission checks.

The session cookie is signed but NOT encrypted, so it holds nothing but the id of the user.
The user (login, role, contract) is read from the database once per request: a changed role
takes effect immediately and a deactivated user loses access at once.

Permissions are defined in app/access.json as "role -> list of permissions"
(for example ``reports.create``), not as "role -> blueprint names".
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps

import psycopg2
from flask import Flask, abort, current_app, flash, g, redirect, session, url_for

from app.repositories.users import User, find_by_id

_SESSION_KEY = "user_id"


def login_user(user: User) -> None:
    session.clear()  # prevents session fixation
    session[_SESSION_KEY] = user.id
    session.permanent = True
    g.current_user = user


def logout_user() -> None:
    session.clear()
    g.current_user = None


def current_user() -> User | None:
    """The signed-in user, loaded from the database once per request."""
    if "current_user" not in g:
        user_id = session.get(_SESSION_KEY)
        user = find_by_id(user_id) if isinstance(user_id, int) else None
        if user is None:
            session.pop(_SESSION_KEY, None)  # the user was removed or deactivated
        g.current_user = user
    return g.current_user


def permissions_for(role: str) -> set[str]:
    return set(current_app.config["ACCESS_MANIFEST"].get(role, []))


def has_permission(permission: str) -> bool:
    user = current_user()
    return user is not None and permission in permissions_for(user.role)


def login_required(view: Callable) -> Callable:
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            flash("Для доступа к этой странице необходимо войти в учётную запись", "warning")
            return redirect(url_for("lk.login"))
        return view(*args, **kwargs)

    return wrapper


def permission_required(permission: str) -> Callable:
    def decorator(view: Callable) -> Callable:
        @wraps(view)
        @login_required
        def wrapper(*args, **kwargs):
            if not has_permission(permission):
                abort(403)
            return view(*args, **kwargs)

        return wrapper

    return decorator


def init_app(app: Flask) -> None:
    @app.context_processor
    def inject_auth() -> dict:
        try:
            user = current_user()
        except psycopg2.Error:
            user = None  # error pages must render even when the database is down

        def can(permission: str) -> bool:
            return user is not None and permission in permissions_for(user.role)

        return {"current_user": user, "has_permission": can}
