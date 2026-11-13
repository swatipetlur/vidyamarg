from ..db import execute, query_all, query_one

FIELDS = [
    "exam_id", "subject", "topic", "title", "description",
    "is_free", "price_paise", "is_published", "is_sample",
]


def _like(text):
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def list_notes(*, published_only=True, exam_id=None, subject=None, q=None, access=None):
    sql = (
        "SELECT n.*, e.name AS exam_name FROM notes n "
        "LEFT JOIN examinations e ON e.id = n.exam_id WHERE 1 = 1"
    )
    params = []
    if published_only:
        sql += " AND n.is_published = 1"
    if exam_id == 0:
        sql += " AND n.exam_id IS NULL"
    elif exam_id:
        sql += " AND n.exam_id = ?"
        params.append(exam_id)
    if subject:
        sql += " AND n.subject = ?"
        params.append(subject)
    if access == "free":
        sql += " AND n.is_free = 1"
    elif access == "paid":
        sql += " AND n.is_free = 0"
    if q:
        sql += " AND (n.title LIKE ? ESCAPE '\\' OR n.description LIKE ? ESCAPE '\\' OR n.topic LIKE ? ESCAPE '\\')"
        params += [_like(q)] * 3
    sql += " ORDER BY (e.name IS NULL), e.name COLLATE NOCASE, n.subject COLLATE NOCASE, n.title COLLATE NOCASE"
    return query_all(sql, params)


def notes_for_exam(exam_id, published_only=True):
    return list_notes(published_only=published_only, exam_id=exam_id)


def subjects():
    return [r["subject"] for r in query_all(
        "SELECT DISTINCT subject FROM notes WHERE is_published = 1 ORDER BY subject COLLATE NOCASE")]


def get_note(note_id):
    return query_one(
        "SELECT n.*, e.name AS exam_name FROM notes n "
        "LEFT JOIN examinations e ON e.id = n.exam_id WHERE n.id = ?", (note_id,))


def create_note(data, file_path=None, original_filename=None):
    cols = FIELDS + ["file_path", "original_filename"]
    marks = ", ".join("?" * len(cols))
    values = [data[f] for f in FIELDS] + [file_path, original_filename]
    return execute(f"INSERT INTO notes ({', '.join(cols)}) VALUES ({marks})", values)


def update_note(note_id, data, file_path=None, original_filename=None, replace_file=False):
    sets = ", ".join(f"{f} = ?" for f in FIELDS)
    values = [data[f] for f in FIELDS]
    if replace_file:
        sets += ", file_path = ?, original_filename = ?"
        values += [file_path, original_filename]
    execute(f"UPDATE notes SET {sets}, updated_at = datetime('now') WHERE id = ?", values + [note_id])


def delete_note(note_id):
    execute("DELETE FROM notes WHERE id = ?", (note_id,))


def unpublish(note_id):
    execute("UPDATE notes SET is_published = 0, updated_at = datetime('now') WHERE id = ?", (note_id,))


def has_orders(note_id):
    return query_one("SELECT 1 AS x FROM orders WHERE note_id = ? LIMIT 1", (note_id,)) is not None


def count():
    return query_one("SELECT COUNT(*) AS n FROM notes")["n"]
