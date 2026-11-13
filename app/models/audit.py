from ..db import execute, query_all


def log(admin_id, action, entity, entity_id=None, detail=None):
    execute(
        "INSERT INTO audit_log (admin_id, action, entity, entity_id, detail) VALUES (?, ?, ?, ?, ?)",
        (admin_id, action, entity, entity_id, (detail or "")[:300]),
    )


def recent(limit=200):
    return query_all(
        "SELECT a.*, u.full_name AS admin_name FROM audit_log a LEFT JOIN users u ON u.id = a.admin_id "
        "ORDER BY a.id DESC LIMIT ?", (limit,))
