from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from .. import security
from ..models import examination as exam_model
from ..models import user as user_model
from ..utils import parse_standard
from .helpers import remembered_standard

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
    return render_template("main/home.html", standards=range(1, 11), exam_count=exam_model.count(),
                           selected=remembered_standard())


@bp.route("/select-standard", methods=["GET", "POST"])
def select_standard():
    if request.method == "POST":
        standard = parse_standard(request.form.get("standard"))
        if standard is None:
            flash("Choose a standard from 1 to 10.", "error")
            return render_template("main/select_standard.html", standards=range(1, 11),
                                   selected=remembered_standard()), 400
        session["standard"] = standard
        if g.user is not None and g.user["role"] == "student":
            user_model.set_standard(g.user["id"], standard)
        target = security.safe_next_url(request.form.get("next"))
        return redirect(target or url_for("exams.list_exams"))
    return render_template("main/select_standard.html", standards=range(1, 11), selected=remembered_standard())
