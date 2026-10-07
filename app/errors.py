"""Error handlers: proper HTTP status codes for error pages."""

from __future__ import annotations

import logging

from flask import Flask, render_template
from flask_wtf.csrf import CSRFError
from psycopg2 import OperationalError
from psycopg2.pool import PoolError

log = logging.getLogger(__name__)


def _page(status: int, title: str, msg: str = ""):
    return render_template("errors/error.html", title=title, msg=msg), status


def register(app: Flask) -> None:
    @app.errorhandler(CSRFError)
    def csrf_error(_exc):
        return _page(
            400, "Не удалось проверить запрос", "Страница устарела. Обновите её и повторите действие."
        )

    @app.errorhandler(400)
    def bad_request(_exc):
        return _page(400, "Некорректный запрос")

    @app.errorhandler(403)
    def forbidden(_exc):
        return _page(
            403, "Доступ запрещён", "У вас недостаточно прав для использования этого раздела системы"
        )

    @app.errorhandler(404)
    def not_found(_exc):
        return _page(404, "Страница не найдена")

    @app.errorhandler(405)
    def method_not_allowed(_exc):
        return _page(405, "Метод не поддерживается")

    @app.errorhandler(429)
    def too_many(_exc):
        return _page(429, "Слишком много попыток", "Подождите немного и повторите.")

    @app.errorhandler(OperationalError)
    @app.errorhandler(PoolError)
    def db_unavailable(exc):
        log.error("database unavailable: %s", exc)
        return _page(503, "Сервис временно недоступен", "Попробуйте повторить позже.")

    @app.errorhandler(500)
    def server_error(_exc):
        return _page(500, "Произошла ошибка", "Мы уже знаем о проблеме. Попробуйте позже.")
