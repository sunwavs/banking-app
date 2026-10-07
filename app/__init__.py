"""RIS banking web application (application factory)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from . import auth, cache, db, errors, headers
from .config import load_config
from .extensions import csrf, limiter

BASE_DIR = Path(__file__).resolve().parent


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(load_config())
    if test_config:
        app.config.update(test_config)

    if not app.config["SECRET_KEY"]:
        raise RuntimeError("SECRET_KEY is not set (see .env.example)")

    logging.basicConfig(
        level=app.config["LOG_LEVEL"],
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # The permission manifest is read once and kept in the application config.
    app.config["ACCESS_MANIFEST"] = json.loads((BASE_DIR / "access.json").read_text(encoding="utf-8"))

    hops = app.config["PROXY_HOPS"]
    if hops > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops)

    db.init_app(app)
    cache.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    auth.init_app(app)
    errors.register(app)
    headers.init_app(app)

    from .blueprints.investments.routes import bp as investments_bp
    from .blueprints.lk.routes import bp as lk_bp
    from .blueprints.main.routes import bp as main_bp
    from .blueprints.reports.routes import bp as reports_bp
    from .blueprints.search.routes import bp as search_bp
    from .blueprints.transfer.routes import bp as transfer_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(lk_bp, url_prefix="/lk")
    app.register_blueprint(search_bp, url_prefix="/search")
    app.register_blueprint(transfer_bp, url_prefix="/transfer")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(investments_bp, url_prefix="/investments")

    return app
