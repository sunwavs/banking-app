"""Personal area: sign in, sign out and the list of the client's accounts."""

from flask import Blueprint, current_app, redirect, render_template, request, url_for

from app.auth import current_user, login_required, login_user, logout_user
from app.extensions import limiter
from app.repositories import accounts, users

bp = Blueprint("lk", __name__, template_folder="templates")


@bp.get("/")
@login_required
def index():
    user = current_user()
    cards = accounts.list_for_contract(user.contract_num) if user.contract_num is not None else []
    return render_template("lk/index.html", cards_data=cards)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["LOGIN_RATE_LIMIT"], methods=["POST"])
def login():
    if request.method == "GET" and current_user() is not None:
        return redirect(url_for("lk.index"))
    if request.method == "POST":
        user = users.authenticate(request.form.get("login", ""), request.form.get("password", ""))
        if user is not None:
            login_user(user)
            return redirect(url_for("lk.index"))
        return render_template("lk/login_screen.html", err_message="Неправильный логин или пароль")
    return render_template("lk/login_screen.html")


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    return render_template("lk/logout_screen.html")
