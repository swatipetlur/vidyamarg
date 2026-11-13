from functools import wraps

from flask import abort, flash, g, redirect, request, url_for


def _login_redirect(endpoint):
    return redirect(url_for(endpoint, next=request.full_path.rstrip("?")))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "info")
            return _login_redirect("auth.login")
        return view(*args, **kwargs)
    return wrapped


def student_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in as a student to continue.", "info")
            return _login_redirect("auth.login")
        if g.user["role"] != "student":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return _login_redirect("auth.admin_login")
        if g.user["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped
