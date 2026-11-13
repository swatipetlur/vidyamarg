"""Safe storage of note files outside the web-served static folder."""
import os
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

ZIP_MAGIC = b"PK\x03\x04"
OLE_MAGIC = b"\xd0\xcf\x11\xe0"
MAGIC = {
    "pdf": (b"%PDF",),
    "docx": (ZIP_MAGIC,), "pptx": (ZIP_MAGIC,), "xlsx": (ZIP_MAGIC,), "odt": (ZIP_MAGIC,),
    "doc": (OLE_MAGIC,), "ppt": (OLE_MAGIC,), "xls": (OLE_MAGIC,),
}


class UploadError(ValueError):
    pass


def _upload_dir():
    path = Path(current_app.config["UPLOAD_DIR"])
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_note_file(storage):
    """Validate and store an uploaded file. Returns (stored_name, original_name)."""
    original = secure_filename(storage.filename or "")
    if not original or "." not in original:
        raise UploadError("Choose a file with a valid name and extension.")
    ext = original.rsplit(".", 1)[1].lower()
    allowed = current_app.config["ALLOWED_NOTE_EXTENSIONS"]
    if ext not in allowed:
        raise UploadError("Unsupported file type. Allowed: " + ", ".join(sorted(allowed)) + ".")

    head = storage.stream.read(8)
    storage.stream.seek(0)
    if not head:
        raise UploadError("The uploaded file is empty.")
    signatures = MAGIC.get(ext)
    if signatures and not any(head.startswith(sig) for sig in signatures):
        raise UploadError(f"The file does not look like a real .{ext} file.")

    stored = f"{uuid.uuid4().hex}.{ext}"
    storage.save(_upload_dir() / stored)
    return stored, original


def delete_note_file(stored_name):
    if not stored_name:
        return
    target = _upload_dir() / os.path.basename(stored_name)
    try:
        target.unlink()
    except FileNotFoundError:
        pass


def file_exists(stored_name):
    return bool(stored_name) and (_upload_dir() / os.path.basename(stored_name)).is_file()


def upload_dir():
    return str(_upload_dir())
