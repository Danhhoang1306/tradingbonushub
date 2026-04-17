"""Leads CRUD: import, query, and campaign send tracking."""
import json

from app.db.connection import get_conn


# ── Lead imports ─────────────────────────────────────────────────────────────

def create_import(file_name: str, imported_by: str = "") -> int:
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO lead_imports (file_name, imported_by) "
            "OUTPUT INSERTED.id VALUES (?, ?)",
            (file_name, imported_by),
        ).fetchone()
        return row["id"]


def update_import_stats(import_id: int, total: int, new: int,
                        updated: int, skipped: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE lead_imports SET total_rows=?, new_rows=?, "
            "updated_rows=?, skipped_rows=? WHERE id=?",
            (total, new, updated, skipped, import_id),
        )


def get_all_imports() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM lead_imports ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ── Leads CRUD ───────────────────────────────────────────────────────────────

def upsert_lead(email: str, name: str = "", country: str = "",
                mobile: str = "", user_id: str = "", sales: str = "",
                affid: str = "", leads_type: str = "", source: str = "",
                extra_data: dict | None = None,
                import_id: int | None = None) -> tuple[int, bool]:
    """Insert or update a lead by email. Returns (lead_id, is_new)."""
    extra_json = json.dumps(extra_data or {}, ensure_ascii=False)
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM leads WHERE email=?", (email,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE leads SET name=COALESCE(NULLIF(?,''),name), "
                "country=COALESCE(NULLIF(?,''),country), "
                "mobile=COALESCE(NULLIF(?,''),mobile), "
                "user_id=COALESCE(NULLIF(?,''),user_id), "
                "sales=COALESCE(NULLIF(?,''),sales), "
                "affid=COALESCE(NULLIF(?,''),affid), "
                "leads_type=COALESCE(NULLIF(?,''),leads_type), "
                "source=COALESCE(NULLIF(?,''),source), "
                "extra_data=?, import_id=COALESCE(?,import_id), "
                "updated_at=GETDATE() WHERE id=?",
                (name, country, mobile, user_id, sales, affid,
                 leads_type, source, extra_json, import_id, existing["id"]),
            )
            return existing["id"], False
        row = conn.execute(
            "INSERT INTO leads (email,name,country,mobile,user_id,sales,"
            "affid,leads_type,source,extra_data,import_id) "
            "OUTPUT INSERTED.id VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (email, name, country, mobile, user_id, sales,
             affid, leads_type, source, extra_json, import_id),
        ).fetchone()
        return row["id"], True


def get_lead(lead_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        return dict(row) if row else None


def get_lead_by_email(email: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM leads WHERE email=?", (email,)).fetchone()
        return dict(row) if row else None


def delete_lead(lead_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM leads WHERE id=?", (lead_id,))


def count_leads(search: str | None = None, country: str | None = None,
                source: str | None = None) -> int:
    with get_conn() as conn:
        where, params = _build_filter(search, country, source)
        row = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM leads{where}", params
        ).fetchone()
        return row["cnt"]


def get_leads(limit: int = 100, offset: int = 0,
              search: str | None = None, country: str | None = None,
              source: str | None = None) -> list[dict]:
    with get_conn() as conn:
        where, params = _build_filter(search, country, source)
        rows = conn.execute(
            f"SELECT * FROM leads{where} ORDER BY created_at DESC "
            f"OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
            [*params, offset, limit],
        ).fetchall()
        return [dict(r) for r in rows]


def get_leads_for_campaign(lead_ids: list[int] | None = None,
                           country: str | None = None,
                           source: str | None = None,
                           search: str | None = None,
                           exclude_campaign_id: int | None = None) -> list[dict]:
    """Get leads for campaign sending.

    Automatically excludes:
    - Leads whose email exists in customers table with unsubscribed=1
    - Leads already successfully sent in exclude_campaign_id (if provided)
    """
    with get_conn() as conn:
        conditions = [
            # Exclude leads whose email matches an unsubscribed customer
            "NOT EXISTS ("
            "  SELECT 1 FROM customers c"
            "  WHERE c.login_email = l.email AND c.unsubscribed = 1"
            ")",
        ]
        params = []

        if lead_ids:
            ph = ",".join("?" * len(lead_ids))
            conditions.append(f"l.id IN ({ph})")
            params.extend(lead_ids)
        if country:
            conditions.append("l.country LIKE ?")
            params.append(f"%{country}%")
        if source:
            conditions.append("l.source LIKE ?")
            params.append(f"%{source}%")
        if search:
            conditions.append(
                "(l.email LIKE ? OR l.name LIKE ? OR l.user_id LIKE ?)"
            )
            q = f"%{search}%"
            params.extend([q, q, q])
        if exclude_campaign_id:
            conditions.append(
                "NOT EXISTS (SELECT 1 FROM lead_campaign_status lcs "
                "WHERE lcs.lead_id=l.id AND lcs.campaign_id=? AND lcs.status='sent')"
            )
            params.append(exclude_campaign_id)

        where = " WHERE " + " AND ".join(conditions)
        rows = conn.execute(
            f"SELECT l.* FROM leads l{where} ORDER BY l.id",
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def get_distinct_countries() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT country FROM leads WHERE country != '' ORDER BY country"
        ).fetchall()
        return [r["country"] for r in rows]


def get_distinct_sources() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT source FROM leads WHERE source != '' ORDER BY source"
        ).fetchall()
        return [r["source"] for r in rows]


def _build_filter(search: str | None, country: str | None,
                  source: str | None) -> tuple[str, list]:
    conditions = []
    params = []
    if search:
        conditions.append(
            "(email LIKE ? OR name LIKE ? OR user_id LIKE ? OR mobile LIKE ?)"
        )
        q = f"%{search}%"
        params.extend([q, q, q, q])
    if country:
        conditions.append("country = ?")
        params.append(country)
    if source:
        conditions.append("source = ?")
        params.append(source)
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    return where, params


# ── Campaign send tracking ───────────────────────────────────────────────────

def set_lead_campaign_status(lead_id: int, campaign_id: int,
                             status: str, error_msg: str | None = None) -> None:
    """Insert or update send status for a lead in a campaign."""
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM lead_campaign_status WHERE lead_id=? AND campaign_id=?",
            (lead_id, campaign_id),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE lead_campaign_status SET status=?, error_msg=?, "
                "sent_at=CASE WHEN ?='sent' THEN GETDATE() ELSE sent_at END "
                "WHERE id=?",
                (status, error_msg, status, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO lead_campaign_status (lead_id,campaign_id,status,error_msg,sent_at) "
                "VALUES (?,?,?,?,CASE WHEN ?='sent' THEN GETDATE() ELSE NULL END)",
                (lead_id, campaign_id, status, error_msg, status),
            )


def get_campaign_lead_statuses(campaign_id: int) -> list[dict]:
    """Get all lead send statuses for a campaign."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT lcs.*, l.email, l.name, l.country "
            "FROM lead_campaign_status lcs "
            "JOIN leads l ON l.id = lcs.lead_id "
            "WHERE lcs.campaign_id=? "
            "ORDER BY lcs.id",
            (campaign_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_lead_send_history(lead_id: int) -> list[dict]:
    """Get all campaigns a lead has been sent to."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT lcs.*, c.name AS campaign_name, c.subject, c.status AS campaign_status "
            "FROM lead_campaign_status lcs "
            "JOIN campaigns c ON c.id = lcs.campaign_id "
            "WHERE lcs.lead_id=? "
            "ORDER BY lcs.sent_at DESC",
            (lead_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_failed_leads_for_campaign(campaign_id: int) -> list[dict]:
    """Get leads that failed in a specific campaign — for retry."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT l.* FROM leads l "
            "JOIN lead_campaign_status lcs ON lcs.lead_id = l.id "
            "WHERE lcs.campaign_id=? AND lcs.status='failed' "
            "ORDER BY l.id",
            (campaign_id,),
        ).fetchall()
        return [dict(r) for r in rows]
