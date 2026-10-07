"""Investment catalog, basket and orders."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth import current_user, permission_required
from app.blueprints.investments import basket
from app.repositories import orders, products

bp = Blueprint("investments", __name__, template_folder="templates")


@bp.get("/")
@permission_required("investments.use")
def index():
    catalog = products.get_catalog()
    lines = basket.build_lines(basket.read(), catalog)
    return render_template(
        "investments/market.html",
        items=list(catalog.values()),
        basket_lines=lines,
        basket_total=sum((line.total for line in lines), start=0),
    )


@bp.post("/basket/add")
@permission_required("investments.use")
def add_to_basket():
    prod_id = request.form.get("prod_id", "")
    product = products.get_catalog().get(prod_id)
    if product is None:
        abort(404)
    if basket.read().get(prod_id, 0) + 1 > product.stock:
        flash("Недостаточно товара на складе", "warning")
    else:
        basket.add(prod_id)
    return redirect(url_for("investments.index"))


@bp.post("/basket/clear")
@permission_required("investments.use")
def clear_basket():
    basket.clear()
    return redirect(url_for("investments.index"))


@bp.post("/order")
@permission_required("investments.use")
def make_order():
    lines = basket.build_lines(basket.read(), products.get_catalog())
    if not lines:
        flash("Корзина пуста", "warning")
        return redirect(url_for("investments.index"))
    try:
        order_id = orders.create_order(
            current_user().id,
            [orders.OrderLine(line.product_id, line.name, line.quantity, line.total) for line in lines],
        )
    except orders.OutOfStock as exc:
        flash(f"Товара «{exc.product_name}» нет в наличии в нужном количестве", "warning")
        return redirect(url_for("investments.index"))
    products.invalidate_catalog()
    basket.clear()
    return redirect(url_for("investments.bought", order_id=order_id))


@bp.get("/bought")
@permission_required("investments.use")
def bought():
    return render_template("investments/bought.html", order_id=request.args.get("order_id", type=int))
