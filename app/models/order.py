import json

from ..db import execute, get_db, query_all, query_one


def create_order(user_id, note_id, amount_paise, currency, provider):
    return execute(
        "INSERT INTO orders (user_id, note_id, amount_paise, currency, status, provider) "
        "VALUES (?, ?, ?, ?, 'created', ?)",
        (user_id, note_id, amount_paise, currency, provider),
    )


def set_provider_order_id(order_id, provider_order_id):
    execute(
        "UPDATE orders SET provider_order_id = ?, status = 'pending', updated_at = datetime('now') WHERE id = ?",
        (provider_order_id, order_id),
    )


def get_order(order_id):
    return query_one(
        "SELECT o.*, n.title AS note_title, n.subject AS note_subject, u.full_name AS user_name, u.email AS user_email "
        "FROM orders o JOIN notes n ON n.id = o.note_id JOIN users u ON u.id = o.user_id WHERE o.id = ?",
        (order_id,),
    )


def get_by_provider_order_id(provider_order_id):
    return query_one("SELECT id FROM orders WHERE provider_order_id = ?", (provider_order_id,))


def has_paid(user_id, note_id):
    return query_one(
        "SELECT 1 AS x FROM orders WHERE user_id = ? AND note_id = ? AND status = 'paid' LIMIT 1",
        (user_id, note_id),
    ) is not None


def paid_note_ids(user_id):
    return {r["note_id"] for r in query_all(
        "SELECT note_id FROM orders WHERE user_id = ? AND status = 'paid'", (user_id,))}


def orders_for_user(user_id):
    return query_all(
        "SELECT o.*, n.title AS note_title FROM orders o JOIN notes n ON n.id = o.note_id "
        "WHERE o.user_id = ? ORDER BY o.id DESC", (user_id,))


def all_orders(limit=200):
    return query_all(
        "SELECT o.*, n.title AS note_title, u.full_name AS user_name, u.email AS user_email "
        "FROM orders o JOIN notes n ON n.id = o.note_id JOIN users u ON u.id = o.user_id "
        "ORDER BY o.id DESC LIMIT ?", (limit,))


def payment_by_provider_id(provider_payment_id):
    return query_one("SELECT * FROM payments WHERE provider_payment_id = ?", (provider_payment_id,))


def record_payment(order_id, provider_payment_id, signature_verified, provider_status,
                   amount_paise, raw, commit=False):
    return execute(
        "INSERT INTO payments (order_id, provider_payment_id, signature_verified, provider_status, "
        "amount_paise, raw_payload) VALUES (?, ?, ?, ?, ?, ?)",
        (order_id, provider_payment_id, 1 if signature_verified else 0, provider_status,
         amount_paise, json.dumps(raw, default=str)[:4000]),
        commit=commit,
    )


def set_status(order_id, new_status, commit=False):
    """Change status, but never move an order away from 'paid'."""
    cur = get_db().execute(
        "UPDATE orders SET status = ?, updated_at = datetime('now'), "
        "paid_at = CASE WHEN ? = 'paid' THEN datetime('now') ELSE paid_at END "
        "WHERE id = ? AND status != 'paid'",
        (new_status, new_status, order_id),
    )
    if commit:
        get_db().commit()
    return cur.rowcount


def payments_for_order(order_id):
    return query_all("SELECT * FROM payments WHERE order_id = ? ORDER BY id", (order_id,))


def revenue_paise():
    return query_one("SELECT COALESCE(SUM(amount_paise), 0) AS s FROM orders WHERE status = 'paid'")["s"]


def count(status=None):
    if status:
        return query_one("SELECT COUNT(*) AS n FROM orders WHERE status = ?", (status,))["n"]
    return query_one("SELECT COUNT(*) AS n FROM orders")["n"]
