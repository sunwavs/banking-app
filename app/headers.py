"""HTTP security headers added to every response.

The Content-Security-Policy allows only same-origin resources and forbids inline styles and
scripts; the templates therefore contain neither (this is verified by the test suite).
"""

from __future__ import annotations

from flask import Flask, Response, request

CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "img-src 'self'",
        "style-src 'self'",
        "script-src 'self'",
        "font-src 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
    ]
)

_STATIC_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
}


def init_app(app: Flask) -> None:
    hsts = app.config["SESSION_COOKIE_SECURE"]  # the deployment is served over HTTPS

    @app.after_request
    def add_security_headers(response: Response) -> Response:
        for name, value in _STATIC_HEADERS.items():
            response.headers.setdefault(name, value)
        if hsts:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.endpoint != "static":  # pages show personal data: never keep them in a cache
            response.headers.setdefault("Cache-Control", "no-store")
        return response
