"""Email tracking CRUD — SQL Server."""
from app.db.connection import get_conn


def create_email(tracking_id, recipient_name, recipient_email,
                 html_content, campaign_id=None, subject=""):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO emails
               (id, recipient_name, recipient_email, subject, html_content, campaign_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (tracking_id, recipient_name, recipient_email,
             subject, html_content, campaign_id),
        )


def log_open(tracking_id, ip, user_agent, device_type, os_name, email_client):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO opens
               (tracking_id, ip_address, user_agent, device_type, os, email_client)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (tracking_id, ip, user_agent, device_type, os_name, email_client),
        )


def get_all_emails(limit: int = 200, offset: int = 0):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT e.id, e.recipient_name, e.recipient_email,
                   e.subject, e.created_at, e.campaign_id,
                   COUNT(o.id)       AS open_count,
                   MAX(o.opened_at)  AS last_opened
            FROM emails e
            LEFT JOIN opens o ON o.tracking_id = e.id
            GROUP BY e.id, e.recipient_name, e.recipient_email,
                     e.subject, e.created_at, e.campaign_id
            ORDER BY e.created_at DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """, (offset, limit)).fetchall()
        return [dict(r) for r in rows]


def count_emails() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM emails").fetchone()
        return row["cnt"] if row else 0


def get_email_detail(tracking_id):
    with get_conn() as conn:
        email = conn.execute(
            "SELECT * FROM emails WHERE id = ?", (tracking_id,)
        ).fetchone()
        if not email:
            return None, []
        opens = conn.execute(
            """SELECT id, opened_at, ip_address, user_agent, device_type, os, email_client
               FROM opens WHERE tracking_id = ? ORDER BY opened_at DESC""",
            (tracking_id,),
        ).fetchall()
        return dict(email), [dict(o) for o in opens]


def tracking_id_exists(tracking_id) -> bool:
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM emails WHERE id = ?", (tracking_id,)
        ).fetchone() is not None


def log_click(tracking_id, ip, user_agent, device_type, os_name,
              destination_url, link_label=None):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO clicks
               (tracking_id, ip_address, user_agent, device_type, os,
                destination_url, link_label)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (tracking_id, ip, user_agent, device_type, os_name,
             destination_url, link_label),
        )


def get_clicks(tracking_id):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, clicked_at, ip_address, user_agent,
                      device_type, os, destination_url, link_label
               FROM clicks WHERE tracking_id = ? ORDER BY clicked_at DESC""",
            (tracking_id,),
        ).fetchall()
        return [dict(r) for r in rows]
