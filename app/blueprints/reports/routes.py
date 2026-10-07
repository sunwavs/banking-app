"""Monthly reports for bank staff: listing, generation and viewing."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth import permission_required
from app.periods import (
    MAX_YEAR,
    MIN_YEAR,
    current_year,
    parse_period_slug,
    parse_year_month,
    period_slug,
)
from app.repositories import reports
from app.repositories.reports import REPORT_TYPES, CreateResult

bp = Blueprint("reports", __name__, template_folder="templates")


def _report_type(slug: str) -> reports.ReportType:
    report = REPORT_TYPES.get(slug)
    if report is None:
        abort(404)
    return report


@bp.get("/")
@permission_required("reports.view")
def index():
    return render_template("reports/index.html", report_types=REPORT_TYPES.values())


@bp.get("/<slug>/")
@permission_required("reports.view")
def report_list(slug):
    report = _report_type(slug)
    periods = [(p, period_slug(p)) for p in reports.list_periods(report)]
    return render_template("reports/list.html", report=report, periods=periods)


@bp.route("/<slug>/new", methods=["GET", "POST"])
@permission_required("reports.create")
def report_create(slug):
    report = _report_type(slug)
    form_ctx = {"report": report, "year_min": MIN_YEAR, "year_max": MAX_YEAR, "default_year": current_year()}

    if request.method == "GET":
        return render_template("reports/create.html", **form_ctx)

    try:
        period = parse_year_month(request.form.get("YearReport"), request.form.get("MonthReport"))
    except ValueError as exc:
        return render_template("reports/create.html", error=str(exc), **form_ctx), 400

    result = reports.create(report, period)
    if result is CreateResult.NO_DATA:
        return render_template("reports/create.html", no_data=True, **form_ctx)
    if result is CreateResult.ALREADY_EXISTS:
        flash("Такой отчёт уже существует", "warning")
    else:
        flash("Отчёт успешно создан!", "success")
    return redirect(url_for("reports.report_view", slug=slug, period=period_slug(period)))


@bp.get("/<slug>/<period>")
@permission_required("reports.view")
def report_view(slug, period):
    report = _report_type(slug)
    try:
        period_date = parse_period_slug(period)
    except ValueError:
        abort(404)
    rows = reports.get_rows(report, period_date)
    if not rows:
        abort(404)
    return render_template("reports/view.html", report=report, rows=rows, period=period_date)
