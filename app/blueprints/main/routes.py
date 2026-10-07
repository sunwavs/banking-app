"""Home page."""

from flask import Blueprint, render_template

bp = Blueprint("main", __name__, template_folder="templates")


@bp.get("/")
def index():
    return render_template("main/index.html")
