"""Navigation items repository."""
from app.db.connection import get_conn


def get_nav_items(menu: str | None = None) -> list[dict]:
    with get_conn() as conn:
        if menu:
            rows = conn.execute(
                "SELECT * FROM nav_items WHERE menu=? ORDER BY display_order, id",
                (menu,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM nav_items ORDER BY menu, display_order, id"
            ).fetchall()
    return [dict(r) for r in rows]


def create_nav_item(menu: str, label: str, url: str, target: str,
                    parent_id: int | None, display_order: int,
                    is_active: bool) -> int:
    with get_conn() as conn:
        row = conn.execute(
            """INSERT INTO nav_items (menu, label, url, target, parent_id, display_order, is_active)
               OUTPUT INSERTED.id VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (menu, label, url, target, parent_id, display_order, 1 if is_active else 0),
        ).fetchone()
    return row["id"]


def update_nav_item(nid: int, menu: str, label: str, url: str, target: str,
                    parent_id: int | None, display_order: int,
                    is_active: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            """UPDATE nav_items
               SET menu=?, label=?, url=?, target=?, parent_id=?,
                   display_order=?, is_active=?
               WHERE id=?""",
            (menu, label, url, target, parent_id, display_order,
             1 if is_active else 0, nid),
        )


def delete_nav_item(nid: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM nav_items WHERE id=?", (nid,))


def reorder_nav_items(items: list[dict]) -> None:
    """Bulk update display_order. items = [{"id": N, "display_order": M}]."""
    with get_conn() as conn:
        for item in items:
            conn.execute(
                "UPDATE nav_items SET display_order=? WHERE id=?",
                (item["display_order"], item["id"]),
            )
