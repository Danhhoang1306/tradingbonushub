"""FAQ item repository."""
from app.db.connection import get_conn


def get_faq_items(active_only: bool = True, broker_id: int | None = None) -> list[dict]:
    """Return FAQ items ordered by display_order.
    - broker_id=None → all items
    - broker_id=0    → generic items only (broker_id IS NULL)
    - broker_id=N    → broker-specific items for broker N
    """
    with get_conn() as conn:
        if broker_id is None:
            where = "WHERE is_active=1" if active_only else "WHERE 1=1"
            rows = conn.execute(
                f"SELECT * FROM faq_items {where} ORDER BY display_order, id"
            ).fetchall()
        elif broker_id == 0:
            where = "AND is_active=1" if active_only else ""
            rows = conn.execute(
                f"SELECT * FROM faq_items WHERE broker_id IS NULL {where} ORDER BY display_order, id"
            ).fetchall()
        else:
            where = "AND is_active=1" if active_only else ""
            rows = conn.execute(
                f"SELECT * FROM faq_items WHERE broker_id=? {where} ORDER BY display_order, id",
                (broker_id,),
            ).fetchall()
    return [dict(r) for r in rows]


def get_faq_item(fid: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM faq_items WHERE id=?", (fid,)).fetchone()
    return dict(row) if row else None


def create_faq_item(question: str, answer: str, broker_id: int | None,
                    display_order: int = 0, is_active: bool = True,
                    question_en: str | None = None, answer_en: str | None = None) -> int:
    with get_conn() as conn:
        row = conn.execute(
            """INSERT INTO faq_items (question, answer, broker_id, display_order, is_active, question_en, answer_en)
               OUTPUT INSERTED.id VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (question, answer, broker_id, display_order, 1 if is_active else 0,
             question_en, answer_en),
        ).fetchone()
    return row["id"]


def update_faq_item(fid: int, question: str, answer: str, broker_id: int | None,
                    display_order: int, is_active: bool,
                    question_en: str | None = None, answer_en: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            """UPDATE faq_items
               SET question=?, answer=?, broker_id=?, display_order=?, is_active=?,
                   question_en=?, answer_en=?
               WHERE id=?""",
            (question, answer, broker_id, display_order, 1 if is_active else 0,
             question_en, answer_en, fid),
        )


def delete_faq_item(fid: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM faq_items WHERE id=?", (fid,))
