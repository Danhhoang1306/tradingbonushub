"""Media files repository."""
from app.db.connection import get_conn


def create_media(filename: str, original_name: str, url: str,
                 mime_type: str, size_bytes: int, uploaded_by: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            """INSERT INTO media_files (filename, original_name, url, mime_type, size_bytes, uploaded_by)
               OUTPUT INSERTED.id VALUES (?, ?, ?, ?, ?, ?)""",
            (filename, original_name, url, mime_type, size_bytes, uploaded_by),
        ).fetchone()
    return row["id"]


def get_all_media(limit: int = 100, offset: int = 0) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM media_files
               ORDER BY created_at DESC
               OFFSET ? ROWS FETCH NEXT ? ROWS ONLY""",
            (offset, limit),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) AS cnt FROM media_files").fetchone()["cnt"]
    return {"items": [dict(r) for r in rows], "total": total}


def get_media(mid: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM media_files WHERE id=?", (mid,)).fetchone()
    return dict(row) if row else None


def update_media_alt(mid: int, alt_text: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE media_files SET alt_text=? WHERE id=?", (alt_text, mid))


def delete_media(mid: int) -> dict | None:
    """Return the record before deleting (to allow caller to delete file)."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM media_files WHERE id=?", (mid,)).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM media_files WHERE id=?", (mid,))
    return dict(row)
