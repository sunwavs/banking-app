"""Money transfer form and submission."""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.auth import current_user, permission_required
from app.repositories import accounts, transfers
from app.repositories.transfers import TransferError

bp = Blueprint("transfer", __name__, template_folder="templates")


@bp.route("/", methods=["GET", "POST"])
@permission_required("transfer.make")
def index():
    user = current_user()
    if request.method == "POST":
        try:
            transfers.make_transfer(
                contract_num=user.contract_num,
                sender=request.form.get("sender", "").strip(),
                receiver=request.form.get("receiver", "").strip(),
                amount_raw=request.form.get("trans_sum", ""),
            )
        except TransferError as exc:
            return (
                render_template(
                    "transfer/transfer_dialog.html",
                    accounts=accounts.list_for_contract(user.contract_num),
                    error=str(exc),
                ),
                400,
            )
        flash("Перевод был успешно осуществлён", "success")
        return redirect(
            url_for("transfer.index")
        )  # Post/Redirect/Get: refreshing the page does not repeat the transfer

    return render_template(
        "transfer/transfer_dialog.html", accounts=accounts.list_for_contract(user.contract_num)
    )
