from ..db import execute, query_all, query_one


def create_user(full_name, email, password_hash, role="student", current_standard=None):
    return execute(
        "INSERT INTO users (full_name, email, password_hash, role, current_standard) VALUES (?, ?, ?, ?, ?)",
        (full_name, email.strip().lower(), password_hash, role, current_standard),
    )


def get_by_id(user_id):
    return query_one("SELECT * FROM users WHERE id = ?", (user_id,))


def get_by_email(email):
    return query_one("SELECT * FROM users WHERE email = ?", ((email or "").strip().lower(),))


def set_standard(user_id, standard):
    execute("UPDATE users SET current_standard = ? WHERE id = ?", (standard, user_id))


def count(role=None):
    if role:
        return query_one("SELECT COUNT(*) AS n FROM users WHERE role = ?", (role,))["n"]
    return query_one("SELECT COUNT(*) AS n FROM users")["n"]


def list_students():
    return query_all("SELECT id, full_name, email, current_standard, created_at FROM users WHERE role = 'student' ORDER BY id DESC")
