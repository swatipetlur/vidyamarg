"""Payment orchestration. This is the ONLY code that may mark an order as paid,
and it does so only from a VerificationResult produced by a provider after
its own authenticity checks. Amounts always come from the database."""
import sqlite3

from flask import current_app

from ...db import get_db
from ...models import order as order_model
from .base import PaymentConfigError, PaymentError, VerificationResult
from .mock_provider import MockProvider
from .razorpay_provider import RazorpayProvider


def get_provider(name=None):
    name = name or current_app.config["PAYMENT_PROVIDER"]
    cfg = current_app.config
    if name == "mock":
        if not cfg["ALLOW_MOCK_PAYMENTS"]:
            raise PaymentConfigError("The mock payment gateway is disabled.")
        return MockProvider(cfg["MOCK_PAYMENT_SECRET"] or cfg["SECRET_KEY"])
    if name == "razorpay":
        return RazorpayProvider(cfg["RAZORPAY_KEY_ID"], cfg["RAZORPAY_KEY_SECRET"], cfg["RAZORPAY_WEBHOOK_SECRET"])
    raise PaymentConfigError(f"Unknown payment provider '{name}'.")


def create_order(user, note):
    """Create a local order (price taken from the notes table) and a provider order.
    Returns (order_row, checkout_dict)."""
    if note["is_free"] or not note["is_published"]:
        raise PaymentError("This note cannot be purchased.")
    if order_model.has_paid(user["id"], note["id"]):
        raise PaymentError("You already own this note.")

    provider = get_provider()
    currency = current_app.config["CURRENCY"]
    order_id = order_model.create_order(user["id"], note["id"], note["price_paise"], currency, provider.name)
    try:
        created = provider.create_order(
            amount_paise=note["price_paise"], currency=currency, receipt=f"vm-{order_id}")
    except PaymentError:
        order_model.set_status(order_id, "failed", commit=True)
        raise
    order_model.set_provider_order_id(order_id, created["provider_order_id"])
    return order_model.get_order(order_id), created["checkout"]


def apply_result(order, result):
    """Apply a provider result to an order. Returns (order_row, message)."""
    db = get_db()
    raw = dict(result.raw)

    def _reject(message, status_text):
        order_model.record_payment(order["id"], None, False, status_text, result.amount_paise, raw)
        db.commit()
        return order_model.get_order(order["id"]), message

    if not result.verified:
        return _reject("We could not verify this payment, so your note stays locked.", "unverified")
    if result.provider_order_id != order["provider_order_id"]:
        return _reject("The payment does not match this order.", "order_mismatch")

    if result.provider_payment_id:
        previous = order_model.payment_by_provider_id(result.provider_payment_id)
        if previous is not None and previous["order_id"] != order["id"]:
            return _reject("This payment was already used for another order.", "replayed_payment")

    new_status = None
    if result.status == "paid":
        if result.amount_paise != order["amount_paise"]:
            return _reject("The paid amount does not match the price, so the note stays locked.", "amount_mismatch")
        new_status = "paid"
    elif result.status in ("failed", "cancelled", "pending"):
        new_status = result.status

    try:
        if result.provider_payment_id:
            already = order_model.payment_by_provider_id(result.provider_payment_id)
            if already is None:
                order_model.record_payment(order["id"], result.provider_payment_id, True,
                                           result.status, result.amount_paise, raw)
        else:
            order_model.record_payment(order["id"], None, True, result.status, result.amount_paise, raw)
        if new_status:
            order_model.set_status(order["id"], new_status)
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        order_model.record_payment(order["id"], None, True, "duplicate_needs_review", result.amount_paise, raw)
        db.commit()
        return order_model.get_order(order["id"]), "This note was already paid for. Contact support about the duplicate payment."

    fresh = order_model.get_order(order["id"])
    messages = {
        "paid": "Payment confirmed. Your note is unlocked.",
        "failed": "The payment failed. Your note stays locked.",
        "cancelled": "The payment was cancelled. Your note stays locked.",
        "pending": "The payment is still pending. Your note unlocks when it is confirmed.",
    }
    return fresh, messages.get(fresh["status"], "Payment status updated.")


def verify_and_apply(order, payload):
    provider = get_provider(order["provider"])
    return apply_result(order, provider.verify_payment(payload))


def handle_webhook(provider_name, raw_body, headers):
    """Returns an HTTP-style status code."""
    provider = get_provider(provider_name)
    result = provider.parse_webhook(raw_body, headers)
    if result is None:
        return 200
    if not result.verified:
        return 400
    row = order_model.get_by_provider_order_id(result.provider_order_id)
    if row is None:
        return 200
    apply_result(order_model.get_order(row["id"]), result)
    return 200
