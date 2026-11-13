from ..db import execute, query_all, query_one


def add(user_id, exam_id):
    execute("INSERT OR IGNORE INTO bookmarks (user_id, exam_id) VALUES (?, ?)", (user_id, exam_id))


def remove(user_id, exam_id):
    execute("DELETE FROM bookmarks WHERE user_id = ? AND exam_id = ?", (user_id, exam_id))


def is_bookmarked(user_id, exam_id):
    return query_one("SELECT 1 AS x FROM bookmarks WHERE user_id = ? AND exam_id = ?", (user_id, exam_id)) is not None


def exam_ids_for(user_id):
    return {r["exam_id"] for r in query_all("SELECT exam_id FROM bookmarks WHERE user_id = ?", (user_id,))}


def exams_for(user_id):
    return query_all(
        "SELECT e.* FROM bookmarks b JOIN examinations e ON e.id = b.exam_id "
        "WHERE b.user_id = ? AND e.is_published = 1 ORDER BY b.created_at DESC", (user_id,))
