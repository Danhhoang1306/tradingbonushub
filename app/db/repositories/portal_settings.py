"""Portal settings CRUD."""
from app.db.connection import get_conn


def get_portal_settings() -> dict:
    with get_conn() as conn:
        try:
            rows = conn.execute("SELECT [key], value FROM portal_settings").fetchall()
            return {r["key"]: r["value"] for r in rows}
        except Exception:
            return {}


def save_portal_settings(data: dict):
    with get_conn() as conn:
        conn.executemany(
            """
            MERGE portal_settings AS t
            USING (VALUES (?, ?)) AS s(k, v) ON t.[key] = s.k
            WHEN MATCHED     THEN UPDATE SET value = s.v
            WHEN NOT MATCHED THEN INSERT ([key], value) VALUES (s.k, s.v);
            """,
            [(k, str(v)) for k, v in data.items()],
        )
