"""Banners repository."""
from app.db.connection import get_conn


def get_all_banners() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM banners ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_active_banners(page: str = "*") -> list[dict]:
    """Return banners currently active and matching the given page."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM banners
               WHERE is_active=1
                 AND (starts_at IS NULL OR starts_at <= GETDATE())
                 AND (ends_at   IS NULL OR ends_at   >= GETDATE())
               ORDER BY created_at DESC""",
        ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        pages = d.get("pages") or "*"
        if pages == "*" or page == "*" or page in pages:
            result.append(d)
    return result


def create_banner(text: str, link_text: str, link_url: str,
                  style: str, pages: str, is_active: bool,
                  starts_at, ends_at) -> int:
    with get_conn() as conn:
        row = conn.execute(
            """INSERT INTO banners (text, link_text, link_url, style, pages, is_active, starts_at, ends_at)
               OUTPUT INSERTED.id VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (text, link_text, link_url, style, pages,
             1 if is_active else 0, starts_at, ends_at),
        ).fetchone()
    return row["id"]


def update_banner(bid: int, text: str, link_text: str, link_url: str,
                  style: str, pages: str, is_active: bool,
                  starts_at, ends_at) -> None:
    with get_conn() as conn:
        conn.execute(
            """UPDATE banners
               SET text=?, link_text=?, link_url=?, style=?, pages=?,
                   is_active=?, starts_at=?, ends_at=?
               WHERE id=?""",
            (text, link_text, link_url, style, pages,
             1 if is_active else 0, starts_at, ends_at, bid),
        )


def delete_banner(bid: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM banners WHERE id=?", (bid,))
