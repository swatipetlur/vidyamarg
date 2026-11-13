from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .. import security
from ..models import user as user_model
from ..validators import validate_registration

bp = Blueprint("auth", __name__, url_prefix="/auth")

# Used to keep response time similar whether or not the email exists.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


def _after_login_target(user, default_endpoint):
    return security.safe_next_url(request.args.get("next") or request.form.get("next")) or url_for(default_endpoint)


def _attempt_login(role, template, default_endpoint):
    if g.user is not None and g.user["role"] == role:
        return redirect(url_for(default_endpoint))

    next_url = request.args.get("next") or request.form.get("next") or ""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if security.too_many_failures(email):
            flash("Too many failed attempts. Please wait a few minutes and try again.", "error")
            return render_template(template, email=email, next_url=next_url), 429

        user = user_model.get_by_email(email)
        stored_hash = user["password_hash"] if user else _DUMMY_HASH
        password_ok = check_password_hash(stored_hash, password)
        if user and password_ok and user["role"] == role and user["is_active"]:
            security.clear_failures(email)
            security.login_session(user)
            flash(f"Welcome back, {user['full_name']}.", "success")
            return redirect(_after_login_target(user, default_endpoint))

        security.record_failure(email)
        flash("Incorrect email or password.", "error")
        return render_template(template, email=email, next_url=next_url), 401
    return render_template(template, email="", next_url=next_url)


@bp.route("/login", methods=["GET", "POST"])
def login():
    return _attempt_login("student", "auth/login.html", "main.home")


@bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    return _attempt_login("admin", "auth/admin_login.html", "admin.dashboard")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user is not None:
        return redirect(url_for("main.home"))
    if request.method == "POST":
        clean, errors = validate_registration(request.form)
        if not errors and user_model.get_by_email(clean["email"]):
            errors["email"] = "An account with this email already exists. Try logging in."
        if errors:
            return render_template("auth/register.html", form=request.form, errors=errors), 400
        user_id = user_model.create_user(
            clean["full_name"], clean["email"], generate_password_hash(clean["password"]),
            "student", clean["standard"],
        )
        security.login_session(user_model.get_by_id(user_id))
        flash("Your account is ready. Choose your standard to see matching examinations.", "success")
        return redirect(url_for("main.select_standard") if not clean["standard"] else url_for("exams.list_exams"))
    return render_template("auth/register.html", form={}, errors={})


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.home"))
