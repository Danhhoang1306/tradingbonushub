"""Admin user CRUD — SQL Server."""
from app.db.connection import get_conn


def get_all_users():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, username, role, "
            "CASE WHEN totp_secret IS NOT NULL THEN 1 ELSE 0 END AS totp_enabled, "
            "created_at FROM users ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]


def get_user(username):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None


def get_user_role(username: str) -> str:
    """Return user's role ('admin' or 'editor'). Defaults to 'admin' if not set."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT role FROM users WHERE username = ?", (username,)
        ).fetchone()
    if not row:
        return "admin"
    return row["role"] or "admin"


def create_user(username, password_hash, role: str = "admin"):
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO users (username, password_hash, role) OUTPUT INSERTED.id VALUES (?, ?, ?)",
            (username, password_hash, role),
        ).fetchone()
        return row["id"] if row else None


def update_user_role(user_id: int, role: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))


def delete_user(user_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def update_password(user_id, password_hash):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id),
        )


def count_users():
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
        return row["cnt"] if row else 0
