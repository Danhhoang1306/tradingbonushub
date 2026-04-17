"""Promo bar templates CRUD — SQL Server."""
from app.db.connection import get_conn


def get_all_promo_bars() -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM promo_bar_templates ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_promo_bar(bar_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM promo_bar_templates WHERE id=?", (bar_id,)
        ).fetchone()
        return dict(row) if row else None


def get_active_promo_bar() -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT TOP 1 * FROM promo_bar_templates WHERE is_active=1 ORDER BY updated_at DESC"
        ).fetchone()
        return dict(row) if row else None


def create_promo_bar(name: str, html: str = "", css: str = "", is_active: bool = False) -> int:
    with get_conn() as conn:
        if is_active:
            conn.execute("UPDATE promo_bar_templates SET is_active=0 WHERE is_active=1")
        row = conn.execute(
            "INSERT INTO promo_bar_templates (name, html, css, is_active) "
            "OUTPUT INSERTED.id VALUES (?,?,?,?)",
            (name, html, css, int(is_active)),
        ).fetchone()
        return row["id"]


def update_promo_bar(bar_id: int, name: str, html: str, css: str, is_active: bool) -> None:
    with get_conn() as conn:
        if is_active:
            conn.execute(
                "UPDATE promo_bar_templates SET is_active=0 WHERE is_active=1 AND id<>?",
                (bar_id,),
            )
        conn.execute(
            "UPDATE promo_bar_templates SET name=?, html=?, css=?, is_active=?, updated_at=GETDATE() "
            "WHERE id=?",
            (name, html, css, int(is_active), bar_id),
        )


def delete_promo_bar(bar_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM promo_bar_templates WHERE id=?", (bar_id,))
