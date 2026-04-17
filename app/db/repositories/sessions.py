"""Server-side session storage backed by SQL Server."""
import json
from datetime import datetime, timedelta, timezone

from app.db.connection import get_conn
from app.config import SESSION_MAX_AGE


def create_session(session_id: str, data: dict, ttl_seconds: int = SESSION_MAX_AGE) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, data_json, expires_at) VALUES (?, ?, ?)",
            (session_id, json.dumps(data, ensure_ascii=False), expires_at.isoformat()),
        )


def get_session(session_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT data_json, expires_at FROM sessions WHERE session_id=?",
            (session_id,),
        ).fetchone()
        if not row:
            return None
        expires = row["expires_at"]
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
            return None
        try:
            return json.loads(row["data_json"] or "{}")
        except Exception:
            return {}


def update_session(session_id: str, data: dict, ttl_seconds: int = SESSION_MAX_AGE) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET data_json=?, expires_at=? WHERE session_id=?",
            (json.dumps(data, ensure_ascii=False), expires_at.isoformat(), session_id),
        )


def delete_session(session_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))


def cleanup_expired() -> int:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE expires_at < GETUTCDATE()")
        return cur.rowcount
