from flask import (Blueprint, abort, current_app, flash, g, redirect, render_template,
                   request, send_from_directory, url_for)

from ..models import examination as exam_model
from ..models import note as note_model
from ..services import uploads
from ..services.note_access import access_for_notes, can_user_access
from ..utils import parse_standard

bp = Blueprint("notes", __name__, url_prefix="/notes")


@bp.route("/")
def catalogue():
    exam_raw = request.args.get("exam_id", "")
    exam_id = int(exam_raw) if exam_raw.isdigit() else None
    subject = (request.args.get("subject") or "").strip()[:100] or None
    q = (request.args.get("q") or "").strip()[:100] or None
    access = request.args.get("access") if request.args.get("access") in ("free", "paid") else None

    notes = note_model.list_notes(exam_id=exam_id, subject=subject, q=q, access=access)
    decisions = access_for_notes(g.user, notes)

    # Group: examination -> subject -> notes
    grouped = {}
    for note in notes:
        exam_key = note["exam_name"] or "General notes"
        grouped.setdefault(exam_key, {}).setdefault(note["subject"], []).append(note)

    return render_template(
        "notes/catalogue.html", grouped=grouped, decisions=decisions, total=len(notes),
        exams=exam_model.list_exams(), subjects=note_model.subjects(),
        exam_id=exam_id, subject=subject, q=q or "", access=access,
    )


@bp.route("/<int:note_id>")
def detail(note_id):
    note = note_model.get_note(note_id)
    decision = can_user_access(g.user, note)
    if note is None or decision.code == "unavailable":
        abort(404)
    return render_template("notes/detail.html", note=note, decision=decision,
                           file_ready=uploads.file_exists(note["file_path"]))


@bp.route("/<int:note_id>/download")
def download(note_id):
    note = note_model.get_note(note_id)
    decision = can_user_access(g.user, note)
    if note is None or decision.code == "unavailable":
        abort(404)
    if not decision.allowed:
        if decision.code == "login_required":
            flash(decision.message, "info")
            return redirect(url_for("auth.login", next=url_for("notes.detail", note_id=note_id)))
        abort(403, description=decision.message)
    if not uploads.file_exists(note["file_path"]):
        flash("The file for this note is not available right now. Please try again later.", "error")
        return redirect(url_for("notes.detail", note_id=note_id))

    response = send_from_directory(
        current_app.config["UPLOAD_DIR"], note["file_path"], as_attachment=True,
        download_name=note["original_filename"] or note["file_path"],
    )
    response.headers["Cache-Control"] = "private, no-store"
    return response
