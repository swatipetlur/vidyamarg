"""CSRF protection, session-user loading, login throttling, security headers."""
import hmac
import secrets
import time
from urllib.parse import urlparse

from flask import abort, current_app, g, request, session

from .models import user as user_model


# ---------------------------------------------------------------- CSRF
def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def csrf_exempt(view):
    """Mark a view as exempt (only for server-to-server webhooks that carry
    their own signature)."""
    view._csrf_exempt = True
    return view


def protect_csrf():
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    view = current_app.view_functions.get(request.endpoint)
    if view is not None and getattr(view, "_csrf_exempt", False):
        return
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
    expected = session.get("csrf_token", "")
    if not expected or not hmac.compare_digest(sent.encode(), expected.encode()):
        abort(400, description="Your form expired or was invalid. Please go back, reload the page and try again.")


# ------------------------------------------------------------ session user
def load_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id is None:
        return
    found = user_model.get_by_id(user_id)
    if found is not None and found["is_active"]:
        g.user = found
    else:
        session.pop("user_id", None)


def login_session(user_row):
    """Start a fresh session for the user (prevents session fixation)."""
    keep_standard = session.get("standard")
    session.clear()
    session.permanent = True
    session["user_id"] = user_row["id"]
    standard = keep_standard or user_row["current_standard"]
    if standard:
        session["standard"] = standard


def safe_next_url(target):
    """Allow only local, relative redirect targets."""
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return None
    return target


# ------------------------------------------------------- login throttling
_failures = {}


def _key(email):
    return f"{request.remote_addr}|{(email or '').lower()}"


def too_many_failures(email):
    window = current_app.config["LOGIN_WINDOW_SECONDS"]
    now = time.monotonic()
    recent = [t for t in _failures.get(_key(email), []) if now - t < window]
    _failures[_key(email)] = recent
    return len(recent) >= current_app.config["LOGIN_MAX_FAILURES"]


def record_failure(email):
    _failures.setdefault(_key(email), []).append(time.monotonic())


def clear_failures(email):
    _failures.pop(_key(email), None)


def reset_throttle():
    _failures.clear()


# -------------------------------------------------------- response headers
def _content_security_policy():
    script = ["'self'"]
    frame = ["'none'"]
    connect = ["'self'"]
    img = ["'self'", "data:"]
    if current_app.config["PAYMENT_PROVIDER"] == "razorpay":
        script.append("https://checkout.razorpay.com")
        frame = ["https://api.razorpay.com", "https://checkout.razorpay.com"]
        connect += ["https://api.razorpay.com", "https://lumberjack.razorpay.com"]
        img.append("https:")
    return "; ".join([
        "default-src 'self'",
        "script-src " + " ".join(script),
        "style-src 'self'",
        "img-src " + " ".join(img),
        "connect-src " + " ".join(connect),
        "frame-src " + " ".join(frame),
        "object-src 'none'",
        "base-uri 'self'",
        "frame-ancestors 'none'",
    ])


def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Content-Security-Policy", _content_security_policy())
    if request.endpoint and request.endpoint.startswith(("payments.", "admin.", "auth.")):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


def init_app(app):
    app.before_request(load_user)
    app.before_request(protect_csrf)
    app.after_request(add_security_headers)

    @app.context_processor
    def inject_globals():
        return {
            "current_user": g.get("user"),
            "current_standard": session.get("standard"),
        }

    app.jinja_env.globals["csrf_token"] = csrf_token
