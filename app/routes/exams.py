from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for

from ..models import bookmark as bookmark_model
from ..models import eligibility as rule_model
from ..models import examination as exam_model
from ..models import note as note_model
from ..services import eligibility_engine as engine
from ..services.note_access import access_for_notes
from ..utils import STATE_RANK, parse_standard, registration_state
from .helpers import remembered_standard

bp = Blueprint("exams", __name__, url_prefix="/exams")


def _clean_choice(value, allowed):
    return value if value in allowed else None


@bp.route("/")
def list_exams():
    raw = request.args.get("standard")
    if raw is not None:
        standard = parse_standard(raw)
        if standard is None:
            flash("Choose a standard from 1 to 10.", "error")
            return redirect(url_for("main.select_standard"))
        session["standard"] = standard
    else:
        standard = remembered_standard()
    if standard is None:
        flash("Choose your standard first so we can show matching examinations.", "info")
        return redirect(url_for("main.select_standard", next=url_for("exams.list_exams")))

    q = (request.args.get("q") or "").strip()[:100]
    category = _clean_choice(request.args.get("category"), exam_model.CATEGORIES)
    board = _clean_choice(request.args.get("board"), exam_model.BOARDS)
    medium = _clean_choice(request.args.get("medium"), exam_model.MEDIUMS)
    view = "all" if request.args.get("view") == "all" else "matching"

    exams = exam_model.list_exams(q=q or None, category=category, board=board, medium=medium)
    rules = rule_model.rules_by_exam([e["id"] for e in exams])
    saved = bookmark_model.exam_ids_for(g.user["id"]) if g.user is not None and g.user["role"] == "student" else set()

    groups = {engine.ELIGIBLE: [], engine.VERIFY: [], engine.NOT_ELIGIBLE: []}
    for exam, result in engine.evaluate_many(exams, rules, standard):
        state_key, state_label = registration_state(exam)
        groups[result.status].append({
            "exam": exam, "result": result, "state": state_key, "state_label": state_label,
            "bookmarked": exam["id"] in saved,
        })
    for items in groups.values():
        items.sort(key=lambda item: (STATE_RANK[item["state"]], item["exam"]["name"].lower()))

    return render_template(
        "exams/list.html", standard=standard, groups=groups, view=view,
        q=q, category=category, board=board, medium=medium,
        categories=exam_model.CATEGORIES, boards=exam_model.BOARDS, mediums=exam_model.MEDIUMS,
        total=sum(len(v) for v in groups.values()), disclaimer=engine.DISCLAIMER,
    )


@bp.route("/<int:exam_id>")
def detail(exam_id):
    exam = exam_model.get_exam(exam_id)
    is_admin = g.user is not None and g.user["role"] == "admin"
    if exam is None or (not exam["is_published"] and not is_admin):
        abort(404)

    rules = rule_model.rules_for_exam(exam_id)
    standard = remembered_standard()
    result = engine.evaluate(rules, standard) if standard else None
    state_key, state_label = registration_state(exam)
    notes = note_model.notes_for_exam(exam_id, published_only=not is_admin)
    bookmarked = (g.user is not None and g.user["role"] == "student"
                  and bookmark_model.is_bookmarked(g.user["id"], exam_id))
    return render_template(
        "exams/detail.html", exam=exam, rules=rules, standard=standard, result=result,
        state_key=state_key, state_label=state_label, notes=notes,
        access=access_for_notes(g.user, notes), bookmarked=bookmarked, disclaimer=engine.DISCLAIMER,
    )
