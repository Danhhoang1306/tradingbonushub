"""Scheduling API — program scheduling, campaign scheduling, CMS auto-publish."""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app.db.connection import get_conn
from app.utils.audit import log_action

router = APIRouter(prefix="/api/scheduling", tags=["scheduling"])


def _require_admin(request: Request) -> str:
    user = request.session.get("user")
    if not user:
        raise HTTPException(403, "Admin required")
    return user


# ── Program Scheduling ───────────────────────────────────────────────────────

@router.put("/programs/{pid}/schedule")
async def api_schedule_program(pid: int, request: Request):
    """Set start/end dates for a program."""
    admin = _require_admin(request)
    data = await request.json()
    starts_at = data.get("starts_at")  # ISO string or None
    ends_at = data.get("ends_at")      # ISO string or None

    with get_conn() as conn:
        prog = conn.execute("SELECT id, name FROM programs WHERE id=?", (pid,)).fetchone()
        if not prog:
            raise HTTPException(404, "Program not found")

        conn.execute(
            "UPDATE programs SET starts_at=?, ends_at=? WHERE id=?",
            (starts_at, ends_at, pid),
        )

    log_action(admin, "program.schedule", entity_type="program", entity_id=str(pid),
               detail={"starts_at": starts_at, "ends_at": ends_at})
    return {"ok": True}


@router.get("/programs/scheduled")
async def api_get_scheduled_programs(request: Request):
    """List programs with scheduling info."""
    _require_admin(request)
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT id, name, type, is_active, starts_at, ends_at, display_order,
                   CASE
                       WHEN is_active=0 THEN 'inactive'
                       WHEN starts_at IS NOT NULL AND starts_at > GETDATE() THEN 'scheduled'
                       WHEN ends_at IS NOT NULL AND ends_at < GETDATE() THEN 'expired'
                       ELSE 'active'
                   END AS schedule_status
            FROM programs
            ORDER BY display_order, id
        """).fetchall()
    return [dict(r) for r in rows]


# ── Campaign Scheduling ──────────────────────────────────────────────────────

@router.put("/campaigns/{cid}/schedule")
async def api_schedule_campaign(cid: int, request: Request):
    """Schedule a campaign to send at a specific time."""
    admin = _require_admin(request)
    data = await request.json()
    scheduled_at = data.get("scheduled_at")

    with get_conn() as conn:
        camp = conn.execute("SELECT id, status FROM campaigns WHERE id=?", (cid,)).fetchone()
        if not camp:
            raise HTTPException(404, "Campaign not found")
        if camp["status"] not in ("draft", "scheduled"):
            raise HTTPException(400, f"Cannot schedule: status is '{camp['status']}'")

        new_status = "scheduled" if scheduled_at else "draft"
        conn.execute(
            "UPDATE campaigns SET scheduled_at=?, status=? WHERE id=?",
            (scheduled_at, new_status, cid),
        )

    log_action(admin, "campaign.schedule", entity_type="campaign", entity_id=str(cid),
               detail={"scheduled_at": scheduled_at})
    return {"ok": True, "status": new_status}


# ── CMS Auto-Publish ─────────────────────────────────────────────────────────

@router.put("/articles/{aid}/schedule")
async def api_schedule_article(aid: int, request: Request):
    """Schedule an article to auto-publish at a given time."""
    admin = _require_admin(request)
    data = await request.json()
    scheduled_at = data.get("scheduled_at")

    with get_conn() as conn:
        art = conn.execute("SELECT id, status FROM cms_articles WHERE id=?", (aid,)).fetchone()
        if not art:
            raise HTTPException(404, "Article not found")

        new_status = "scheduled" if scheduled_at else art["status"]
        conn.execute(
            "UPDATE cms_articles SET scheduled_at=?, status=? WHERE id=?",
            (scheduled_at, new_status, aid),
        )

    log_action(admin, "article.schedule", entity_type="cms_article", entity_id=str(aid),
               detail={"scheduled_at": scheduled_at})
    return {"ok": True}


# ── Scheduled Tasks Processor ─────────────────────────────────────────────────

def process_scheduled_programs():
    """Auto-activate/deactivate programs based on schedule. Called periodically."""
    now = datetime.now()
    with get_conn() as conn:
        # Activate programs whose start date has passed
        activated = conn.execute(
            "UPDATE programs SET is_active=1 "
            "WHERE is_active=0 AND starts_at IS NOT NULL AND starts_at <= ? "
            "AND (ends_at IS NULL OR ends_at > ?)",
            (now.isoformat(), now.isoformat()),
        ).rowcount

        # Deactivate programs whose end date has passed
        deactivated = conn.execute(
            "UPDATE programs SET is_active=0 "
            "WHERE is_active=1 AND ends_at IS NOT NULL AND ends_at <= ?",
            (now.isoformat(),),
        ).rowcount

    return {"activated": activated, "deactivated": deactivated}


def process_scheduled_articles():
    """Auto-publish articles whose scheduled_at has passed. Called periodically."""
    now = datetime.now()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id FROM cms_articles "
            "WHERE status='scheduled' AND scheduled_at IS NOT NULL AND scheduled_at <= ?",
            (now.isoformat(),),
        ).fetchall()

        for r in rows:
            conn.execute(
                "UPDATE cms_articles SET status='published', published_at=GETDATE() WHERE id=?",
                (r["id"],),
            )

    return len(rows)


def process_scheduled_campaigns():
    """Enqueue campaigns whose scheduled_at has passed. Called periodically."""
    now = datetime.now()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id FROM campaigns "
            "WHERE status='scheduled' AND scheduled_at IS NOT NULL AND scheduled_at <= ?",
            (now.isoformat(),),
        ).fetchall()

        for r in rows:
            conn.execute(
                "UPDATE campaigns SET status='draft' WHERE id=?",  # job_worker picks up draft
                (r["id"],),
            )

    return len(rows)
