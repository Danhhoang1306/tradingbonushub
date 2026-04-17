"""Campaign CRUD — SQL Server."""
from app.db.connection import get_conn


def get_all_campaigns():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT c.id, c.name, c.template_id, c.subject, c.status,
                   c.total, c.sent, c.failed, c.created_at, c.scheduled_at,
                   t.name                          AS template_name,
                   COUNT(DISTINCT o.tracking_id)   AS unique_opens,
                   COUNT(DISTINCT cl.tracking_id)  AS unique_clicks
            FROM campaigns c
            LEFT JOIN templates t  ON t.id = c.template_id
            LEFT JOIN emails    e  ON e.campaign_id = c.id
            LEFT JOIN opens     o  ON o.tracking_id = e.id
            LEFT JOIN clicks    cl ON cl.tracking_id = e.id
            GROUP BY c.id, c.name, c.template_id, c.subject, c.status,
                     c.total, c.sent, c.failed, c.created_at, c.scheduled_at, t.name
            ORDER BY c.created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_campaign(campaign_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        return dict(row) if row else None


def create_campaign(name, template_id, subject=""):
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO campaigns (name, template_id, subject) OUTPUT INSERTED.id VALUES (?, ?, ?)",
            (name, template_id, subject),
        ).fetchone()
        return row["id"] if row else None


_ALLOWED_STATUS_COLS = frozenset({"status", "total", "sent", "failed"})


def update_campaign_status(campaign_id, status, total=None, sent=None, failed=None):
    with get_conn() as conn:
        parts, vals = ["status = ?"], [status]
        for col, val in (("total", total), ("sent", sent), ("failed", failed)):
            if val is not None:
                assert col in _ALLOWED_STATUS_COLS
                parts.append(f"{col} = ?")
                vals.append(val)
        vals.append(campaign_id)
        conn.execute(f"UPDATE campaigns SET {', '.join(parts)} WHERE id = ?", vals)


def increment_campaign_sent(campaign_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE campaigns SET sent = sent + 1 WHERE id = ?", (campaign_id,)
        )


def increment_campaign_failed(campaign_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE campaigns SET failed = failed + 1 WHERE id = ?", (campaign_id,)
        )


def rename_campaign(campaign_id, name):
    with get_conn() as conn:
        conn.execute("UPDATE campaigns SET name = ? WHERE id = ?", (name, campaign_id))


def delete_campaign(campaign_id):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM clicks WHERE tracking_id IN "
            "(SELECT id FROM emails WHERE campaign_id = ?)",
            (campaign_id,),
        )
        conn.execute(
            "DELETE FROM opens WHERE tracking_id IN "
            "(SELECT id FROM emails WHERE campaign_id = ?)",
            (campaign_id,),
        )
        conn.execute("DELETE FROM emails WHERE campaign_id = ?", (campaign_id,))
        conn.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))


def get_campaign_emails(campaign_id):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT e.id, e.recipient_name, e.recipient_email,
                   e.subject, e.created_at,
                   COUNT(DISTINCT o.id)  AS open_count,
                   MAX(o.opened_at)      AS last_opened,
                   COUNT(DISTINCT cl.id) AS click_count,
                   MAX(cl.clicked_at)    AS last_clicked
            FROM emails e
            LEFT JOIN opens  o  ON o.tracking_id  = e.id
            LEFT JOIN clicks cl ON cl.tracking_id = e.id
            WHERE e.campaign_id = ?
            GROUP BY e.id, e.recipient_name, e.recipient_email,
                     e.subject, e.created_at
            ORDER BY e.created_at DESC
        """, (campaign_id,)).fetchall()
        return [dict(r) for r in rows]
