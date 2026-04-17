"""Notification rules management API — admin controls for event-driven alerts."""
import json

from fastapi import APIRouter, HTTPException, Request

from app.db.connection import get_conn
from app.utils.audit import log_action

router = APIRouter(prefix="/api/admin/notifications", tags=["notifications"])

EVENT_TYPES = [
    "enrollment.new",
    "enrollment.approved",
    "withdrawal.new",
    "withdrawal.approved",
    "withdrawal.completed",
    "customer.registered",
    "customer.verified",
    "rebate.imported",
    "rebate.exported",
    "campaign.completed",
    "promo.expiring",
    "promo.expired",
]

CHANNELS = ["email", "telegram"]


def _require_admin(request: Request) -> str:
    user = request.session.get("user")
    if not user:
        raise HTTPException(403, "Admin required")
    return user


@router.get("/rules")
async def api_list_rules(request: Request):
    _require_admin(request)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM notification_rules ORDER BY event_type, channel"
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["config"] = json.loads(d["config_json"])
        except (json.JSONDecodeError, TypeError):
            d["config"] = {}
        result.append(d)
    return result


@router.get("/event-types")
async def api_event_types(request: Request):
    _require_admin(request)
    return EVENT_TYPES


@router.put("/rules/{rule_id}")
async def api_update_rule(rule_id: int, request: Request):
    admin = _require_admin(request)
    data = await request.json()

    with get_conn() as conn:
        rule = conn.execute("SELECT * FROM notification_rules WHERE id=?", (rule_id,)).fetchone()
        if not rule:
            raise HTTPException(404, "Rule not found")

        is_enabled = data.get("is_enabled", rule["is_enabled"])
        config = data.get("config")
        config_json = json.dumps(config) if config is not None else rule["config_json"]

        conn.execute(
            "UPDATE notification_rules SET is_enabled=?, config_json=? WHERE id=?",
            (int(is_enabled), config_json, rule_id),
        )

    log_action(admin, "notification_rule.update", entity_type="notification_rule",
               entity_id=str(rule_id),
               detail={"event_type": rule["event_type"], "channel": rule["channel"],
                        "is_enabled": bool(is_enabled)})
    return {"ok": True}


@router.post("/rules")
async def api_create_rule(request: Request):
    admin = _require_admin(request)
    data = await request.json()
    event_type = (data.get("event_type") or "").strip()
    channel = (data.get("channel") or "email").strip()
    is_enabled = data.get("is_enabled", True)
    config = data.get("config", {})

    if event_type not in EVENT_TYPES:
        raise HTTPException(400, f"Invalid event type: {event_type}")
    if channel not in CHANNELS:
        raise HTTPException(400, f"Invalid channel: {channel}")

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM notification_rules WHERE event_type=? AND channel=?",
            (event_type, channel),
        ).fetchone()
        if existing:
            raise HTTPException(400, "Rule already exists for this event/channel combination")

        row = conn.execute(
            "INSERT INTO notification_rules (event_type, channel, is_enabled, config_json) "
            "OUTPUT INSERTED.id VALUES (?, ?, ?, ?)",
            (event_type, channel, int(is_enabled), json.dumps(config)),
        ).fetchone()

    log_action(admin, "notification_rule.create", entity_type="notification_rule",
               entity_id=str(row["id"]))
    return {"ok": True, "id": row["id"]}


@router.delete("/rules/{rule_id}")
async def api_delete_rule(rule_id: int, request: Request):
    admin = _require_admin(request)
    with get_conn() as conn:
        rule = conn.execute("SELECT * FROM notification_rules WHERE id=?", (rule_id,)).fetchone()
        if not rule:
            raise HTTPException(404, "Rule not found")
        conn.execute("DELETE FROM notification_rules WHERE id=?", (rule_id,))

    log_action(admin, "notification_rule.delete", entity_type="notification_rule",
               entity_id=str(rule_id))
    return {"ok": True}
