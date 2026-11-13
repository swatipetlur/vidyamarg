from flask import (Blueprint, abort, flash, g, redirect, render_template, request, url_for)

from ..auth.decorators import admin_required
from ..models import audit as audit_model
from ..models import eligibility as rule_model
from ..models import examination as exam_model
from ..models import note as note_model
from ..models import order as order_model
from ..models import user as user_model
from ..services import uploads
from ..validators import validate_exam, validate_note, validate_rule

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
@admin_required
def _guard():
    """Every admin route requires an authenticated administrator."""
    return None


def _audit(action, entity, entity_id, detail=""):
    audit_model.log(g.user["id"], action, entity, entity_id, detail)


# ----------------------------------------------------------------- dashboard
@bp.route("/")
def dashboard():
    stats = {
        "exams": exam_model.count(), "rules": rule_model.count(), "notes": note_model.count(),
        "students": user_model.count("student"), "orders": order_model.count(),
        "paid": order_model.count("paid"), "revenue": order_model.revenue_paise(),
    }
    return render_template("admin/dashboard.html", stats=stats, orders=order_model.all_orders(limit=8))


# --------------------------------------------------------------- examinations
@bp.route("/exams")
def exams():
    items = exam_model.list_exams(published_only=False)
    rules = rule_model.rules_by_exam([e["id"] for e in items])
    return render_template("admin/exams.html", exams=items, rules=rules)


def _exam_form(exam, form, errors, title):
    return render_template(
        "admin/exam_form.html", exam=exam, form=form, errors=errors, title=title,
        rule_list=rule_model.rules_for_exam(exam["id"]) if exam else [],
        categories=exam_model.CATEGORIES, boards=exam_model.BOARDS, mediums=exam_model.MEDIUMS,
    )


@bp.route("/exams/new", methods=["GET", "POST"])
def exam_new():
    if request.method == "POST":
        clean, errors = validate_exam(request.form)
        if errors:
            return _exam_form(None, request.form, errors, "Add examination"), 400
        exam_id = exam_model.create_exam(clean)
        _audit("create", "examination", exam_id, clean["name"])
        flash("Examination added. Now add its eligibility rules.", "success")
        return redirect(url_for("admin.rule_new", exam_id=exam_id))
    return _exam_form(None, {"is_published": "1"}, {}, "Add examination")


@bp.route("/exams/<int:exam_id>/edit", methods=["GET", "POST"])
def exam_edit(exam_id):
    exam = exam_model.get_exam(exam_id) or abort(404)
    if request.method == "POST":
        clean, errors = validate_exam(request.form)
        if errors:
            return _exam_form(exam, request.form, errors, "Edit examination"), 400
        exam_model.update_exam(exam_id, clean)
        _audit("update", "examination", exam_id, clean["name"])
        flash("Examination updated.", "success")
        return redirect(url_for("admin.exams"))
    form = {k: ("" if exam[k] is None else exam[k]) for k in exam.keys()}
    return _exam_form(exam, form, {}, "Edit examination")


@bp.route("/exams/<int:exam_id>/delete", methods=["POST"])
def exam_delete(exam_id):
    exam = exam_model.get_exam(exam_id) or abort(404)
    exam_model.delete_exam(exam_id)
    _audit("delete", "examination", exam_id, exam["name"])
    flash(f"Removed {exam['name']}. Its notes were kept as general notes.", "info")
    return redirect(url_for("admin.exams"))


# ------------------------------------------------------------ eligibility rules
@bp.route("/exams/<int:exam_id>/rules/new", methods=["GET", "POST"])
def rule_new(exam_id):
    exam = exam_model.get_exam(exam_id) or abort(404)
    if request.method == "POST":
        clean, errors = validate_rule(request.form)
        if errors:
            return render_template("admin/rule_form.html", exam=exam, rule=None, form=request.form,
                                   errors=errors, title="Add eligibility rule"), 400
        rule_id = rule_model.create_rule(exam_id, clean)
        _audit("create", "eligibility_rule", rule_id, f"exam {exam_id}")
        flash("Eligibility rule added.", "success")
        return redirect(url_for("admin.exam_edit", exam_id=exam_id))
    return render_template("admin/rule_form.html", exam=exam, rule=None, form={}, errors={},
                           title="Add eligibility rule")


@bp.route("/rules/<int:rule_id>/edit", methods=["GET", "POST"])
def rule_edit(rule_id):
    rule = rule_model.get_rule(rule_id) or abort(404)
    exam = exam_model.get_exam(rule["exam_id"])
    if request.method == "POST":
        clean, errors = validate_rule(request.form)
        if errors:
            return render_template("admin/rule_form.html", exam=exam, rule=rule, form=request.form,
                                   errors=errors, title="Edit eligibility rule"), 400
        rule_model.update_rule(rule_id, clean)
        _audit("update", "eligibility_rule", rule_id, f"exam {exam['id']}")
        flash("Eligibility rule updated.", "success")
        return redirect(url_for("admin.exam_edit", exam_id=exam["id"]))
    form = {k: ("" if rule[k] is None else rule[k]) for k in rule.keys()}
    return render_template("admin/rule_form.html", exam=exam, rule=rule, form=form, errors={},
                           title="Edit eligibility rule")


@bp.route("/rules/<int:rule_id>/delete", methods=["POST"])
def rule_delete(rule_id):
    rule = rule_model.get_rule(rule_id) or abort(404)
    rule_model.delete_rule(rule_id)
    _audit("delete", "eligibility_rule", rule_id, f"exam {rule['exam_id']}")
    flash("Eligibility rule removed.", "info")
    return redirect(url_for("admin.exam_edit", exam_id=rule["exam_id"]))


# ---------------------------------------------------------------------- notes
def _note_form(note, form, errors, title):
    return render_template("admin/note_form.html", note=note, form=form, errors=errors, title=title,
                           exams=exam_model.choices())


def _valid_exam_ids():
    return {row["id"] for row in exam_model.choices()}


@bp.route("/notes")
def notes():
    return render_template("admin/notes.html", notes=note_model.list_notes(published_only=False))


@bp.route("/notes/new", methods=["GET", "POST"])
def note_new():
    if request.method == "POST":
        clean, errors = validate_note(request.form, _valid_exam_ids())
        stored = original = None
        upload = request.files.get("file")
        if upload and upload.filename and not errors:
            try:
                stored, original = uploads.save_note_file(upload)
            except uploads.UploadError as exc:
                errors["file"] = str(exc)
        if errors:
            return _note_form(None, request.form, errors, "Add note"), 400
        note_id = note_model.create_note(clean, stored, original)
        _audit("create", "note", note_id, clean["title"])
        flash("Note added." if stored else "Note added without a file. Upload one so students can open it.", "success")
        return redirect(url_for("admin.notes"))
    return _note_form(None, {"access": "free", "is_published": "1"}, {}, "Add note")


@bp.route("/notes/<int:note_id>/edit", methods=["GET", "POST"])
def note_edit(note_id):
    note = note_model.get_note(note_id) or abort(404)
    if request.method == "POST":
        clean, errors = validate_note(request.form, _valid_exam_ids())
        stored = original = None
        upload = request.files.get("file")
        replacing = bool(upload and upload.filename)
        if replacing and not errors:
            try:
                stored, original = uploads.save_note_file(upload)
            except uploads.UploadError as exc:
                errors["file"] = str(exc)
        if errors:
            return _note_form(note, request.form, errors, "Edit note"), 400
        note_model.update_note(note_id, clean, stored, original, replace_file=replacing)
        if replacing:
            uploads.delete_note_file(note["file_path"])
        _audit("update", "note", note_id, clean["title"])
        flash("Note updated.", "success")
        return redirect(url_for("admin.notes"))
    form = {k: ("" if note[k] is None else note[k]) for k in note.keys()}
    form["access"] = "free" if note["is_free"] else "paid"
    form["price"] = "" if note["is_free"] else f"{note['price_paise'] / 100:.2f}"
    return _note_form(note, form, {}, "Edit note")


@bp.route("/notes/<int:note_id>/delete", methods=["POST"])
def note_delete(note_id):
    note = note_model.get_note(note_id) or abort(404)
    if note_model.has_orders(note_id):
        # Keep purchase records and buyers' access intact: hide instead of delete.
        note_model.unpublish(note_id)
        _audit("unpublish", "note", note_id, note["title"])
        flash("This note has purchase records, so it was hidden from the catalogue instead of deleted.", "info")
    else:
        note_model.delete_note(note_id)
        uploads.delete_note_file(note["file_path"])
        _audit("delete", "note", note_id, note["title"])
        flash("Note removed.", "info")
    return redirect(url_for("admin.notes"))


# ------------------------------------------------------------ orders & audit
@bp.route("/orders")
def orders():
    return render_template("admin/orders.html", orders=order_model.all_orders())


@bp.route("/audit")
def audit():
    return render_template("admin/audit.html", entries=audit_model.recent())
