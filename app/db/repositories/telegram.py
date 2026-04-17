"""Telegram bot DB operations."""
import secrets
from app.db.connection import get_conn


def get_telegram_session(login_email: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT chat_id FROM telegram_sessions WHERE login_email = ?",
            (login_email,),
        ).fetchone()
        return dict(row) if row else None


def upsert_telegram_session(login_email: str, chat_id: int):
    with get_conn() as conn:
        conn.execute(
            """
            MERGE telegram_sessions AS t
            USING (VALUES (?, ?)) AS s(e, c) ON t.login_email = s.e
            WHEN MATCHED THEN UPDATE SET chat_id = s.c, created_at = GETDATE()
            WHEN NOT MATCHED THEN INSERT (login_email, chat_id) VALUES (s.e, s.c)
            """,
            (login_email, chat_id),
        )


def get_session_by_chat_id(chat_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT login_email FROM telegram_sessions WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        return dict(row) if row else None


def create_link_token(login_email: str) -> str:
    """Create (or refresh) a 24h deep-link token for this customer."""
    token = secrets.token_urlsafe(16)
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM telegram_link_tokens WHERE login_email = ?", (login_email,)
        )
        conn.execute(
            """INSERT INTO telegram_link_tokens (token, login_email, expires_at)
               VALUES (?, ?, DATEADD(HOUR, 24, GETDATE()))""",
            (token, login_email),
        )
    return token


def get_link_token(token: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT login_email FROM telegram_link_tokens "
            "WHERE token = ? AND expires_at > GETDATE()",
            (token,),
        ).fetchone()
        return dict(row) if row else None


def delete_link_token(token: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM telegram_link_tokens WHERE token = ?", (token,))


def save_message_map(admin_message_id: int, customer_chat_id: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO telegram_message_map (admin_message_id, customer_chat_id) "
            "VALUES (?, ?)",
            (admin_message_id, customer_chat_id),
        )


def get_customer_by_admin_message(admin_message_id: int) -> int | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT customer_chat_id FROM telegram_message_map "
            "WHERE admin_message_id = ?",
            (admin_message_id,),
        ).fetchone()
        return row["customer_chat_id"] if row else None
