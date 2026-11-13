"""SQLite access layer (standard-library sqlite3, one connection per request)."""
import sqlite3

from flask import current_app, g


def get_db():
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DATABASE"])
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def query_all(sql, params=()):
    return get_db().execute(sql, params).fetchall()


def query_one(sql, params=()):
    return get_db().execute(sql, params).fetchone()


def execute(sql, params=(), commit=True):
    """Run one write statement. Returns lastrowid. Pass commit=False inside a
    multi-statement unit of work and call get_db().commit() yourself."""
    conn = get_db()
    cur = conn.execute(sql, params)
    if commit:
        conn.commit()
    return cur.lastrowid


def init_db():
    """Create all tables (idempotent)."""
    conn = get_db()
    with current_app.open_resource("schema.sql") as handle:
        conn.executescript(handle.read().decode("utf-8"))
    conn.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
