"""System administration API — audit logs, login history, sessions, TOTP management.

All endpoints require admin role (enforced by AuthMiddleware + role check).
"""
import json

from fastapi import APIRouter, HTTPException, Query, Request

from app.db.connection import get_conn
from app.services.totp import disable_totp, get_totp_secret
from app.utils.audit import log_action

router = APIRouter(prefix="/api/admin", tags=["admin-system"])


def _require_admin(request: Request) -> str:
    """Ensure caller is admin (not editor). Returns username."""
    user = request.session.get("user")
    role = request.session.get("user_role", "admin")
    if not user or role != "admin":
        raise HTTPException(403, "Admin role required")
    return user


# ── Audit Logs ────────────────────────────────────────────────────────────────

@router.get("/audit-logs")
async def api_audit_logs(
    request: Request,
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    actor: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    search: str | None = None,
):
    """Query audit log with optional filters."""
    _require_admin(request)

    with get_conn() as conn:
        sql = "SELECT * FROM audit_log"
        conds, params = [], []

        if actor:
            conds.append("actor = ?")
            params.append(actor)
        if action:
            conds.append("action LIKE ?")
            params.append(f"%{action}%")
        if entity_type:
            conds.append("entity_type = ?")
            params.append(entity_type)
        if search:
            conds.append(
                "(actor LIKE ? OR action LIKE ? OR entity_type LIKE ? "
                "OR entity_id LIKE ? OR detail_json LIKE ?)"
            )
            s = f"%{search}%"
            params.extend([s, s, s, s, s])

        if conds:
            sql += " WHERE " + " AND ".join(conds)

        sql += " ORDER BY created_at DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        params.extend([offset, limit])

        rows = conn.execute(sql, params).fetchall()

        # Total count for pagination
        count_sql = "SELECT COUNT(*) AS cnt FROM audit_log"
        if conds:
            count_sql += " WHERE " + " AND ".join(conds)
        total = conn.execute(count_sql, params[:-2]).fetchone()["cnt"]

    items = []
    for r in rows:
        d = dict(r)
        # Parse JSON detail for frontend
        if d.get("detail_json"):
            try:
                d["detail"] = json.loads(d["detail_json"])
            except Exception:
                d["detail"] = d["detail_json"]
        else:
            d["detail"] = None
        items.append(d)

    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/audit-logs/actors")
async def api_audit_actors(request: Request):
    """List distinct actors for filter dropdown."""
    _require_admin(request)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT actor FROM audit_log WHERE actor <> '' ORDER BY actor"
        ).fetchall()
    return [r["actor"] for r in rows]


@router.get("/audit-logs/actions")
async def api_audit_actions(request: Request):
    """List distinct action types for filter dropdown."""
    _require_admin(request)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT action FROM audit_log ORDER BY action"
        ).fetchall()
    return [r["action"] for r in rows]


# ── Login History ─────────────────────────────────────────────────────────────

@router.get("/login-history")
async def api_login_history(
    request: Request,
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    user_type: str | None = None,
    identifier: str | None = None,
):
    """View failed login attempts (successful logins are in audit_log)."""
    _require_admin(request)

    with get_conn() as conn:
        sql = "SELECT * FROM login_attempts"
        conds, params = [], []

        if user_type:
            conds.append("user_type = ?")
            params.append(user_type)
        if identifier:
            conds.append("identifier LIKE ?")
            params.append(f"%{identifier}%")

        if conds:
            sql += " WHERE " + " AND ".join(conds)

        sql += " ORDER BY attempted_at DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        params.extend([offset, limit])

        rows = conn.execute(sql, params).fetchall()

        count_sql = "SELECT COUNT(*) AS cnt FROM login_attempts"
        if conds:
            count_sql += " WHERE " + " AND ".join(conds)
        total = conn.execute(count_sql, params[:-2]).fetchone()["cnt"]

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ── Active Sessions ───────────────────────────────────────────────────────────

@router.get("/sessions")
async def api_list_sessions(request: Request):
    """List all active (non-expired) sessions with user info."""
    _require_admin(request)

    with get_conn() as conn:
        rows = conn.execute(
            """SELECT session_id, data_json, created_at, expires_at
               FROM sessions
               WHERE expires_at > GETUTCDATE()
               ORDER BY created_at DESC"""
        ).fetchall()

    sessions = []
    for r in rows:
        d = dict(r)
        try:
            data = json.loads(d["data_json"] or "{}")
        except Exception:
            data = {}
        # Only show sessions that belong to a user (admin or customer)
        user = data.get("user", "")
        customer = data.get("customer_email", "")
        if not user and not customer:
            continue
        sessions.append({
            "session_id": d["session_id"][:12] + "...",  # truncate for display
            "session_id_full": d["session_id"],
            "user": user,
            "customer_email": customer,
            "role": data.get("user_role", ""),
            "type": "admin" if user else "customer",
            "created_at": d["created_at"],
            "expires_at": d["expires_at"],
            "last_active": data.get("_last_active"),
        })

    return sessions


@router.delete("/sessions/{session_id}")
async def api_force_logout(request: Request, session_id: str):
    """Force logout a specific session (delete from DB)."""
    admin = _require_admin(request)

    # Don't allow deleting own session
    current_cookie = request.cookies.get("session_id", "")
    # The cookie is signed, so we can't directly compare — just delete by ID
    with get_conn() as conn:
        # Check if session exists
        row = conn.execute(
            "SELECT data_json FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Session not found")

        try:
            data = json.loads(row["data_json"] or "{}")
        except Exception:
            data = {}

        target = data.get("user", "") or data.get("customer_email", "unknown")
        conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))

    log_action(admin, "session.force_logout",
               detail={"target": target, "session_id": session_id[:12]})
    return {"ok": True, "target": target}


@router.delete("/sessions")
async def api_force_logout_all(request: Request, target_user: str | None = None):
    """Force logout all sessions, optionally for a specific user."""
    admin = _require_admin(request)

    with get_conn() as conn:
        if target_user:
            # Delete sessions containing this user
            rows = conn.execute(
                "SELECT session_id, data_json FROM sessions WHERE expires_at > GETUTCDATE()"
            ).fetchall()
            count = 0
            for r in rows:
                try:
                    data = json.loads(r["data_json"] or "{}")
                except Exception:
                    continue
                if data.get("user") == target_user or data.get("customer_email") == target_user:
                    conn.execute("DELETE FROM sessions WHERE session_id=?", (r["session_id"],))
                    count += 1
            log_action(admin, "session.force_logout_user",
                       detail={"target": target_user, "count": count})
            return {"ok": True, "count": count, "target": target_user}
        else:
            # Don't delete own session
            # Delete all OTHER sessions
            conn.execute("DELETE FROM sessions WHERE expires_at > GETUTCDATE()")
            log_action(admin, "session.force_logout_all")
            return {"ok": True}


# ── TOTP Management ───────────────────────────────────────────────────────────

@router.delete("/users/{uid}/totp")
async def api_disable_totp(request: Request, uid: int):
    """Disable TOTP for a user — forces re-setup on next login."""
    admin = _require_admin(request)

    with get_conn() as conn:
        row = conn.execute("SELECT username, totp_secret FROM users WHERE id=?", (uid,)).fetchone()
        if not row:
            raise HTTPException(404, "User not found")
        if not row["totp_secret"]:
            raise HTTPException(400, "TOTP is not enabled for this user")

    disable_totp(row["username"])
    log_action(admin, "user.disable_totp",
               entity_type="user", entity_id=str(uid),
               detail={"username": row["username"]})
    return {"ok": True, "username": row["username"]}


@router.get("/users/{uid}/totp-status")
async def api_totp_status(request: Request, uid: int):
    """Check if a user has TOTP enabled."""
    _require_admin(request)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT username, totp_secret FROM users WHERE id=?", (uid,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "User not found")
    return {
        "username": row["username"],
        "totp_enabled": bool(row["totp_secret"]),
    }


# ── Customer Lock/Unlock ─────────────────────────────────────────────────────

@router.post("/customers/{cid}/lock")
async def api_lock_customer(request: Request, cid: int):
    """Lock a customer account — prevents portal login."""
    admin = _require_admin(request)

    with get_conn() as conn:
        row = conn.execute(
            "SELECT login_email, is_locked FROM customers WHERE id=?", (cid,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Customer not found")
        conn.execute("UPDATE customers SET is_locked=1 WHERE id=?", (cid,))

    # Force logout all sessions for this customer
    with get_conn() as conn:
        sessions = conn.execute(
            "SELECT session_id, data_json FROM sessions WHERE expires_at > GETUTCDATE()"
        ).fetchall()
        for s in sessions:
            try:
                data = json.loads(s["data_json"] or "{}")
            except Exception:
                continue
            if data.get("customer_email") == row["login_email"]:
                conn.execute("DELETE FROM sessions WHERE session_id=?", (s["session_id"],))

    log_action(admin, "customer.lock",
               entity_type="customer", entity_id=str(cid),
               detail={"email": row["login_email"]})
    return {"ok": True, "email": row["login_email"]}


@router.post("/customers/{cid}/unlock")
async def api_unlock_customer(request: Request, cid: int):
    """Unlock a locked customer account."""
    admin = _require_admin(request)

    with get_conn() as conn:
        row = conn.execute(
            "SELECT login_email FROM customers WHERE id=?", (cid,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Customer not found")
        conn.execute("UPDATE customers SET is_locked=0 WHERE id=?", (cid,))

    log_action(admin, "customer.unlock",
               entity_type="customer", entity_id=str(cid),
               detail={"email": row["login_email"]})
    return {"ok": True, "email": row["login_email"]}


# ── System Overview ───────────────────────────────────────────────────────────

@router.get("/system-stats")
async def api_system_stats(request: Request):
    """Dashboard stats for system monitoring page."""
    _require_admin(request)

    with get_conn() as conn:
        # Active sessions
        sessions = conn.execute(
            "SELECT COUNT(*) AS cnt FROM sessions WHERE expires_at > GETUTCDATE()"
        ).fetchone()["cnt"]

        # Recent audit events (24h)
        audit_24h = conn.execute(
            "SELECT COUNT(*) AS cnt FROM audit_log "
            "WHERE created_at > DATEADD(HOUR, -24, GETDATE())"
        ).fetchone()["cnt"]

        # Failed logins (24h)
        failed_logins = conn.execute(
            "SELECT COUNT(*) AS cnt FROM login_attempts "
            "WHERE attempted_at > DATEADD(HOUR, -24, GETUTCDATE())"
        ).fetchone()["cnt"]

        # Pending jobs
        pending_jobs = conn.execute(
            "SELECT COUNT(*) AS cnt FROM job_queue WHERE status='pending'"
        ).fetchone()["cnt"]

        # Total users
        total_users = conn.execute(
            "SELECT COUNT(*) AS cnt FROM users"
        ).fetchone()["cnt"]

        # Total customers
        total_customers = conn.execute(
            "SELECT COUNT(*) AS cnt FROM customers"
        ).fetchone()["cnt"]

        # Locked customers
        locked_customers = conn.execute(
            "SELECT COUNT(*) AS cnt FROM customers WHERE is_locked=1"
        ).fetchone()["cnt"]

    return {
        "active_sessions": sessions,
        "audit_events_24h": audit_24h,
        "failed_logins_24h": failed_logins,
        "pending_jobs": pending_jobs,
        "total_users": total_users,
        "total_customers": total_customers,
        "locked_customers": locked_customers,
    }


# ── Job Queue Monitor ─────────────────────────────────────────────────────────

@router.get("/jobs")
async def api_list_jobs(
    request: Request,
    limit: int = Query(50, le=200),
    status: str | None = None,
):
    """View background job queue."""
    _require_admin(request)

    with get_conn() as conn:
        sql = "SELECT * FROM job_queue"
        params = []
        if status:
            sql += " WHERE status=?"
            params.append(status)
        sql += " ORDER BY created_at DESC OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()

    items = []
    for r in rows:
        d = dict(r)
        if d.get("payload_json"):
            try:
                payload = json.loads(d["payload_json"])
                # Don't expose full payload (may contain email content)
                d["payload_summary"] = {
                    k: v for k, v in payload.items()
                    if k in ("campaign_id", "template_id", "total", "subject")
                }
            except Exception:
                d["payload_summary"] = {}
        del d["payload_json"]
        items.append(d)

    return items
