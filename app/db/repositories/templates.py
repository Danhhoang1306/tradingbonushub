"""Email template CRUD."""
from app.db.connection import get_conn


def get_all_templates():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, created_at, updated_at FROM templates ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_template(template_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        ).fetchone()
        return dict(row) if row else None


def create_template(name, html_content):
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO templates (name, html_content) OUTPUT INSERTED.id VALUES (?, ?)",
            (name, html_content),
        ).fetchone()
        return row["id"] if row else None


def update_template(template_id, name, html_content):
    with get_conn() as conn:
        conn.execute(
            """UPDATE templates SET name=?, html_content=?,
               updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (name, html_content, template_id),
        )


def delete_template(template_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
