"""CRUD for page_content table."""
from app.db.connection import get_conn


def get_all_content(lang: str = "en") -> dict[str, str]:
    """Return all key→value for the given language, fallback to 'en'."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT [key], value FROM page_content WHERE lang=?", (lang,)
        ).fetchall()
        result = {r["key"]: r["value"] for r in rows}
        if lang != "en":
            # fill missing keys with English fallback
            en_rows = conn.execute(
                "SELECT [key], value FROM page_content WHERE lang='en'"
            ).fetchall()
            for r in en_rows:
                result.setdefault(r["key"], r["value"])
        return result


def get_content(key: str, lang: str = "en", default: str = "") -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM page_content WHERE [key]=? AND lang=?", (key, lang)
        ).fetchone()
        return row["value"] if row else default


def set_content(key: str, lang: str, value: str) -> None:
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT 1 FROM page_content WHERE [key]=? AND lang=?", (key, lang)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE page_content SET value=?, updated_at=GETDATE() WHERE [key]=? AND lang=?",
                (value, key, lang),
            )
        else:
            conn.execute(
                "INSERT INTO page_content ([key], lang, value) VALUES (?,?,?)",
                (key, lang, value),
            )


def get_all_langs_for_key(key: str) -> dict[str, str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT lang, value FROM page_content WHERE [key]=?", (key,)
        ).fetchall()
        return {r["lang"]: r["value"] for r in rows}
