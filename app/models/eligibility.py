from ..db import execute, query_all, query_one

FIELDS = ["min_standard", "max_standard", "criteria_text", "source_note"]


def rules_for_exam(exam_id):
    return query_all(
        "SELECT * FROM eligibility_rules WHERE exam_id = ? ORDER BY min_standard, id", (exam_id,)
    )


def rules_by_exam(exam_ids):
    """One query for many exams -> {exam_id: [rule rows]}."""
    grouped = {exam_id: [] for exam_id in exam_ids}
    if not exam_ids:
        return grouped
    marks = ",".join("?" * len(exam_ids))
    for row in query_all(
        f"SELECT * FROM eligibility_rules WHERE exam_id IN ({marks}) ORDER BY min_standard, id",
        list(exam_ids),
    ):
        grouped[row["exam_id"]].append(row)
    return grouped


def get_rule(rule_id):
    return query_one("SELECT * FROM eligibility_rules WHERE id = ?", (rule_id,))


def create_rule(exam_id, data):
    return execute(
        "INSERT INTO eligibility_rules (exam_id, min_standard, max_standard, criteria_text, source_note) "
        "VALUES (?, ?, ?, ?, ?)",
        [exam_id] + [data[f] for f in FIELDS],
    )


def update_rule(rule_id, data):
    execute(
        "UPDATE eligibility_rules SET min_standard = ?, max_standard = ?, criteria_text = ?, "
        "source_note = ?, updated_at = datetime('now') WHERE id = ?",
        [data[f] for f in FIELDS] + [rule_id],
    )


def delete_rule(rule_id):
    execute("DELETE FROM eligibility_rules WHERE id = ?", (rule_id,))


def count():
    return query_one("SELECT COUNT(*) AS n FROM eligibility_rules")["n"]
