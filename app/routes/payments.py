from flask import (Blueprint, abort, current_app, flash, g, redirect, render_template,
                   request, url_for)

from .. import security
from ..auth.decorators import login_required, student_required
from ..models import note as note_model
from ..models import order as order_model
from ..services.payments import PaymentConfigError, PaymentError, service
from ..services.payments.mock_provider import OUTCOMES

bp = Blueprint("payments", __name__, url_prefix="/payments")


def _own_order_or_404(order_id):
    order = order_model.get_order(order_id)
    if order is None:
        abort(404)
    if g.user["role"] != "admin" and order["user_id"] != g.user["id"]:
        abort(404)  # do not reveal other people's orders
    return order


@bp.route("/checkout/<int:note_id>", methods=["POST"])
@student_required
def checkout(note_id):
    """Create an order. The browser sends nothing but the note id; the price,
    currency and provider all come from the server."""
    note = note_model.get_note(note_id)
    if note is None or not note["is_published"]:
        abort(404)
    try:
        order, checkout_data = service.create_order(g.user, note)
    except PaymentConfigError as exc:
        flash(f"Payments are not available right now. {exc}", "error")
        return redirect(url_for("notes.detail", note_id=note_id))
    except PaymentError as exc:
        flash(str(exc), "error")
        return redirect(url_for("notes.detail", note_id=note_id))

    if order["provider"] == "mock":
        return redirect(url_for("payments.mock_gateway", order_id=order["id"]))
    return render_template("payments/checkout.html", order=order, checkout=checkout_data)


@bp.route("/verify", methods=["POST"])
@student_required
def verify():
    """Browser hands back the provider's signed result. We trust nothing in
    it until the provider driver has verified it."""
    raw_id = request.form.get("order_id", "")
    if not raw_id.isdigit():
        abort(400)
    order = _own_order_or_404(int(raw_id))
    payload = {k: v for k, v in request.form.items() if k not in ("csrf_token", "order_id")}
    try:
        order, message = service.verify_and_apply(order, payload)
    except PaymentError as exc:
        flash(f"We could not confirm the payment: {exc}", "error")
        return redirect(url_for("payments.status", order_id=order["id"]))
    flash(message, "success" if order["status"] == "paid" else "info")
    return redirect(url_for("payments.status", order_id=order["id"]))


@bp.route("/<int:order_id>/cancel", methods=["POST"])
@student_required
def cancel(order_id):
    order = _own_order_or_404(order_id)
    if order["status"] != "paid":
        order_model.set_status(order_id, "cancelled", commit=True)
        flash("Payment cancelled. Your note stays locked.", "info")
    return redirect(url_for("payments.status", order_id=order_id))


@bp.route("/status/<int:order_id>")
@login_required
def status(order_id):
    order = _own_order_or_404(order_id)
    return render_template("payments/status.html", order=order)


@bp.route("/my-orders")
@student_required
def my_orders():
    return render_template("payments/my_orders.html", orders=order_model.orders_for_user(g.user["id"]))


@bp.route("/webhook/<provider_name>", methods=["POST"])
@security.csrf_exempt
def webhook(provider_name):
    """Provider-to-server notification. Authenticated by the provider's signature,
    never by a session or cookie."""
    try:
        code = service.handle_webhook(provider_name, request.get_data(), request.headers)
    except PaymentConfigError:
        abort(404)
    return ("", code)


@bp.route("/mock/pay/<int:order_id>", methods=["GET", "POST"])
@student_required
def mock_gateway(order_id):
    """Local stand-in for a bank page. It is only reachable for orders created
    with the mock provider and only while ALLOW_MOCK_PAYMENTS is on."""
    order = _own_order_or_404(order_id)
    if order["provider"] != "mock" or not current_app.config["ALLOW_MOCK_PAYMENTS"]:
        abort(404)
    if order["status"] == "paid":
        return redirect(url_for("payments.status", order_id=order_id))

    if request.method == "POST":
        outcome = request.form.get("outcome")
        if outcome not in OUTCOMES:
            abort(400)
        provider = service.get_provider("mock")
        # The gateway signs the result using the amount stored in OUR database.
        payload = provider.simulate_gateway(order["provider_order_id"], outcome, order["amount_paise"])
        order, message = service.apply_result(order, provider.verify_payment(payload))
        flash(message, "success" if order["status"] == "paid" else "info")
        return redirect(url_for("payments.status", order_id=order_id))
    return render_template("payments/mock_gateway.html", order=order)
