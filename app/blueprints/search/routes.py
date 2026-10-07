"""Queries available to clients: transaction history of an account for a month."""

from flask import Blueprint, abort, render_template, request

from app.auth import current_user, has_permission, permission_required
from app.periods import current_year, parse_year_month
from app.repositories import accounts, remittances

bp = Blueprint("search", __name__, template_folder="templates")

# (endpoint, caption, required permission)
MENU = [
    ("search.remittances_history", "Посмотреть историю изменений счёта", "search.view"),
]


@bp.get("/")
@permission_required("search.view")
def index():
    items = [(endpoint, caption) for endpoint, caption, perm in MENU if has_permission(perm)]
    return render_template("search/index.html", menu=items)


@bp.get("/remittances_history")
@permission_required("search.view")
def remittances_history():
    user = current_user()
    own_accounts = accounts.list_for_contract(user.contract_num)
    own_nums = {a["account_num"] for a in own_accounts}

    selected_account = request.args.get("account")
    if selected_account is None:  # the form has not been submitted yet
        return render_template(
            "search/remittances_history.html", accounts=own_accounts, now_year=current_year()
        )

    # The account number comes from the client and must not be trusted: only own accounts are allowed.
    if selected_account not in own_nums:
        abort(403)

    try:
        period = parse_year_month(request.args.get("year"), request.args.get("month"))
    except ValueError as exc:
        return (
            render_template(
                "search/remittances_history.html",
                accounts=own_accounts,
                error=str(exc),
                now_year=current_year(),
            ),
            400,
        )

    operations = remittances.annotate_direction(
        remittances.list_for_account_month(selected_account, period), selected_account
    )
    return render_template(
        "search/remittances_history.html",
        accounts=own_accounts,
        operations=operations,
        selected={"account": selected_account, "year": period.year, "month": period.month},
    )
