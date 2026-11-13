from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import security
from ..auth.decorators import student_required
from ..models import bookmark as bookmark_model
from ..models import eligibility as rule_model
from ..models import examination as exam_model
from ..services import eligibility_engine as engine
from ..utils import registration_state
from .helpers import remembered_standard

bp = Blueprint("bookmarks", __name__, url_prefix="/bookmarks")


@bp.route("/")
@student_required
def saved():
    exams = bookmark_model.exams_for(g.user["id"])
    standard = remembered_standard()
    rules = rule_model.rules_by_exam([e["id"] for e in exams])
    items = []
    for exam in exams:
        key, label = registration_state(exam)
        result = engine.evaluate(rules[exam["id"]], standard) if standard else None
        items.append({"exam": exam, "result": result, "state": key, "state_label": label, "bookmarked": True})
    return render_template("bookmarks/list.html", items=items, standard=standard)


@bp.route("/<int:exam_id>/toggle", methods=["POST"])
@student_required
def toggle(exam_id):
    exam = exam_model.get_exam(exam_id)
    if exam is None or not exam["is_published"]:
        abort(404)
    if bookmark_model.is_bookmarked(g.user["id"], exam_id):
        bookmark_model.remove(g.user["id"], exam_id)
        flash(f"Removed {exam['name']} from your saved examinations.", "info")
    else:
        bookmark_model.add(g.user["id"], exam_id)
        flash(f"Saved {exam['name']}.", "success")
    target = security.safe_next_url(request.form.get("next"))
    return redirect(target or url_for("exams.detail", exam_id=exam_id))
