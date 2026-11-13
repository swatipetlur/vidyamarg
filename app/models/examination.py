from ..db import execute, query_all, query_one

CATEGORIES = ["Olympiad", "Scholarship", "Talent Search", "Aptitude", "Other"]
BOARDS = ["All", "CBSE", "ICSE", "State Board"]
MEDIUMS = ["All", "English", "Marathi", "Hindi", "Other"]

FIELDS = [
    "name", "conducting_body", "description", "category", "board", "medium",
    "exam_date", "registration_start", "registration_end", "fee_info",
    "official_url", "link_last_checked", "is_sample", "is_published",
]


def _like(text):
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def list_exams(*, published_only=True, q=None, category=None, board=None, medium=None, ids=None):
    sql = "SELECT * FROM examinations WHERE 1 = 1"
    params = []
    if published_only:
        sql += " AND is_published = 1"
    if q:
        sql += (" AND (name LIKE ? ESCAPE '\\' OR conducting_body LIKE ? ESCAPE '\\'"
                " OR description LIKE ? ESCAPE '\\')")
        params += [_like(q)] * 3
    if category:
        sql += " AND category = ?"
        params.append(category)
    if board and board != "All":
        sql += " AND (board = 'All' OR board = ?)"
        params.append(board)
    if medium and medium != "All":
        sql += " AND (medium = 'All' OR medium = ?)"
        params.append(medium)
    if ids is not None:
        if not ids:
            return []
        sql += " AND id IN (%s)" % ",".join("?" * len(ids))
        params += list(ids)
    sql += " ORDER BY name COLLATE NOCASE"
    return query_all(sql, params)


def get_exam(exam_id):
    return query_one("SELECT * FROM examinations WHERE id = ?", (exam_id,))


def create_exam(data):
    cols = ", ".join(FIELDS)
    marks = ", ".join("?" * len(FIELDS))
    return execute(f"INSERT INTO examinations ({cols}) VALUES ({marks})", [data[f] for f in FIELDS])


def update_exam(exam_id, data):
    assignments = ", ".join(f"{f} = ?" for f in FIELDS)
    execute(
        f"UPDATE examinations SET {assignments}, updated_at = datetime('now') WHERE id = ?",
        [data[f] for f in FIELDS] + [exam_id],
    )


def delete_exam(exam_id):
    execute("DELETE FROM examinations WHERE id = ?", (exam_id,))


def count():
    return query_one("SELECT COUNT(*) AS n FROM examinations")["n"]


def choices():
    """(id, name) pairs for dropdowns in the admin panel."""
    return query_all("SELECT id, name FROM examinations ORDER BY name COLLATE NOCASE")
