"""Customer Segmentation API — create segments, evaluate rules, list members."""
import json

from fastapi import APIRouter, HTTPException, Query, Request

from app.db.connection import get_conn
from app.utils.audit import log_action

router = APIRouter(prefix="/api/segments", tags=["segments"])


def _require_admin(request: Request) -> str:
    user = request.session.get("user")
    if not user:
        raise HTTPException(403, "Admin required")
    return user


# ── Segment CRUD ─────────────────────────────────────────────────────────────

@router.get("")
async def api_list_segments(request: Request):
    _require_admin(request)
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT s.*,
                   (SELECT COUNT(*) FROM customer_segment_members csm
                    WHERE csm.segment_id = s.id) AS member_count
            FROM customer_segments s
            ORDER BY s.name
        """).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["rules"] = json.loads(d["rules_json"])
        except (json.JSONDecodeError, TypeError):
            d["rules"] = {}
        result.append(d)
    return result


@router.get("/{sid}")
async def api_get_segment(sid: int, request: Request):
    _require_admin(request)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM customer_segments WHERE id=?", (sid,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Segment not found")
        d = dict(row)
        try:
            d["rules"] = json.loads(d["rules_json"])
        except (json.JSONDecodeError, TypeError):
            d["rules"] = {}
    return d


@router.post("")
async def api_create_segment(request: Request):
    """Create a customer segment.

    Rules JSON structure:
    {
        "conditions": [
            {"field": "country", "op": "eq", "value": "VN"},
            {"field": "days_since_register", "op": "gte", "value": 30},
            {"field": "has_active_account", "op": "eq", "value": true},
            {"field": "total_volume", "op": "gte", "value": 100},
            {"field": "last_login_days", "op": "gte", "value": 60},
            {"field": "broker", "op": "eq", "value": "vantage"},
            {"field": "program_type", "op": "eq", "value": "backcom"},
            {"field": "wallet_balance", "op": "gte", "value": 50}
        ],
        "match": "all"  // "all" or "any"
    }
    """
    admin = _require_admin(request)
    data = await request.json()
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()
    rules = data.get("rules", {})
    is_dynamic = data.get("is_dynamic", True)

    if not name:
        raise HTTPException(400, "Segment name is required")

    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO customer_segments (name, description, rules_json, is_dynamic) "
            "OUTPUT INSERTED.id VALUES (?, ?, ?, ?)",
            (name, description, json.dumps(rules), int(is_dynamic)),
        ).fetchone()
        sid = row["id"]

    # If dynamic, evaluate rules immediately
    if is_dynamic and rules.get("conditions"):
        _evaluate_segment(sid, rules)

    log_action(admin, "segment.create", entity_type="segment", entity_id=str(sid),
               detail={"name": name})
    return {"ok": True, "id": sid}


@router.put("/{sid}")
async def api_update_segment(sid: int, request: Request):
    admin = _require_admin(request)
    data = await request.json()

    with get_conn() as conn:
        seg = conn.execute("SELECT * FROM customer_segments WHERE id=?", (sid,)).fetchone()
        if not seg:
            raise HTTPException(404, "Segment not found")

        name = (data.get("name") or seg["name"]).strip()
        description = (data.get("description") or "").strip()
        rules = data.get("rules")
        is_dynamic = data.get("is_dynamic", seg["is_dynamic"])

        rules_json = json.dumps(rules) if rules is not None else seg["rules_json"]

        conn.execute(
            "UPDATE customer_segments SET name=?, description=?, rules_json=?, "
            "is_dynamic=?, updated_at=GETDATE() WHERE id=?",
            (name, description, rules_json, int(is_dynamic), sid),
        )

    # Re-evaluate if dynamic
    if is_dynamic and rules:
        _evaluate_segment(sid, rules)

    log_action(admin, "segment.update", entity_type="segment", entity_id=str(sid))
    return {"ok": True}


@router.delete("/{sid}")
async def api_delete_segment(sid: int, request: Request):
    admin = _require_admin(request)
    with get_conn() as conn:
        seg = conn.execute("SELECT name FROM customer_segments WHERE id=?", (sid,)).fetchone()
        if not seg:
            raise HTTPException(404, "Segment not found")
        conn.execute("DELETE FROM customer_segment_members WHERE segment_id=?", (sid,))
        conn.execute("DELETE FROM customer_segments WHERE id=?", (sid,))

    log_action(admin, "segment.delete", entity_type="segment", entity_id=str(sid),
               detail={"name": seg["name"]})
    return {"ok": True}


@router.get("/{sid}/members")
async def api_segment_members(sid: int, request: Request,
                               limit: int = Query(50, le=500),
                               offset: int = Query(0, ge=0)):
    """List customers in a segment."""
    _require_admin(request)
    with get_conn() as conn:
        seg = conn.execute("SELECT name FROM customer_segments WHERE id=?", (sid,)).fetchone()
        if not seg:
            raise HTTPException(404, "Segment not found")

        rows = conn.execute("""
            SELECT c.id, c.login_email, c.name, c.created_at, c.last_login_at,
                   csm.added_at,
                   (SELECT COUNT(*) FROM customer_accounts ca
                    WHERE ca.customer_id=c.id AND ca.client_status='active') AS active_accounts
            FROM customer_segment_members csm
            JOIN customers c ON c.id = csm.customer_id
            WHERE csm.segment_id = ?
            ORDER BY csm.added_at DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """, (sid, offset, limit)).fetchall()

        total = conn.execute(
            "SELECT COUNT(*) AS cnt FROM customer_segment_members WHERE segment_id=?",
            (sid,),
        ).fetchone()["cnt"]

    return {"items": [dict(r) for r in rows], "total": total}


@router.post("/{sid}/refresh")
async def api_refresh_segment(sid: int, request: Request):
    """Re-evaluate segment rules and update members."""
    admin = _require_admin(request)
    with get_conn() as conn:
        seg = conn.execute("SELECT * FROM customer_segments WHERE id=?", (sid,)).fetchone()
        if not seg:
            raise HTTPException(404, "Segment not found")
        if not seg["is_dynamic"]:
            raise HTTPException(400, "Only dynamic segments can be refreshed")

        try:
            rules = json.loads(seg["rules_json"])
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(400, "Invalid segment rules")

    count = _evaluate_segment(sid, rules)
    return {"ok": True, "member_count": count}


@router.post("/{sid}/add-members")
async def api_add_members(sid: int, request: Request):
    """Manually add customers to a static segment."""
    admin = _require_admin(request)
    data = await request.json()
    customer_ids = data.get("customer_ids", [])

    with get_conn() as conn:
        seg = conn.execute("SELECT name FROM customer_segments WHERE id=?", (sid,)).fetchone()
        if not seg:
            raise HTTPException(404, "Segment not found")

        added = 0
        for cid in customer_ids:
            try:
                conn.execute(
                    "INSERT INTO customer_segment_members (segment_id, customer_id) VALUES (?, ?)",
                    (sid, cid),
                )
                added += 1
            except Exception:
                pass  # Already exists

    return {"ok": True, "added": added}


# ── Rule Evaluation Engine ────────────────────────────────────────────────────

def _evaluate_segment(segment_id: int, rules: dict) -> int:
    """Evaluate rules and populate segment members. Returns member count."""
    conditions = rules.get("conditions", [])
    match_mode = rules.get("match", "all")  # "all" or "any"

    if not conditions:
        return 0

    # Build SQL WHERE clause from conditions
    where_parts = []
    params = []

    for cond in conditions:
        field = cond.get("field", "")
        op = cond.get("op", "eq")
        value = cond.get("value")

        sql_cond = _build_condition(field, op, value, params)
        if sql_cond:
            where_parts.append(sql_cond)

    if not where_parts:
        return 0

    joiner = " AND " if match_mode == "all" else " OR "
    where_clause = joiner.join(where_parts)

    with get_conn() as conn:
        # Clear existing members
        conn.execute(
            "DELETE FROM customer_segment_members WHERE segment_id=?",
            (segment_id,),
        )

        # Find matching customers
        sql = f"""
            INSERT INTO customer_segment_members (segment_id, customer_id)
            SELECT ?, c.id
            FROM customers c
            LEFT JOIN customer_accounts ca ON ca.customer_id = c.id
            LEFT JOIN customer_wallets cw ON cw.customer_id = c.id
            LEFT JOIN (
                SELECT ca2.customer_id, SUM(CAST(rr.total_volume AS FLOAT)) AS total_volume
                FROM customer_accounts ca2
                JOIN rebate_records rr ON rr.customer_account_id = ca2.id
                GROUP BY ca2.customer_id
            ) rv ON rv.customer_id = c.id
            WHERE ({where_clause})
            GROUP BY c.id
        """
        try:
            conn.execute(sql, [segment_id] + params)
        except Exception:
            # Fallback: simpler query without volume joins
            simple_sql = f"""
                INSERT INTO customer_segment_members (segment_id, customer_id)
                SELECT ?, c.id FROM customers c WHERE ({where_clause})
            """
            conn.execute(simple_sql, [segment_id] + params)

        count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM customer_segment_members WHERE segment_id=?",
            (segment_id,),
        ).fetchone()["cnt"]

    return count


def _build_condition(field: str, op: str, value, params: list) -> str | None:
    """Convert a rule condition to SQL. Returns SQL fragment or None."""
    op_map = {"eq": "=", "neq": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<=",
              "like": "LIKE", "in": "IN"}

    if field == "country":
        params.append(value if op != "like" else f"%{value}%")
        return f"c.id IN (SELECT customer_id FROM customer_accounts WHERE country {op_map.get(op, '=')} ?)"

    if field == "days_since_register":
        params.append(int(value))
        sql_op = op_map.get(op, ">=")
        return f"DATEDIFF(DAY, c.created_at, GETDATE()) {sql_op} ?"

    if field == "has_active_account":
        if value:
            return "EXISTS (SELECT 1 FROM customer_accounts ca WHERE ca.customer_id=c.id AND ca.client_status='active')"
        return "NOT EXISTS (SELECT 1 FROM customer_accounts ca WHERE ca.customer_id=c.id AND ca.client_status='active')"

    if field == "total_volume":
        params.append(float(value))
        sql_op = op_map.get(op, ">=")
        return f"ISNULL(rv.total_volume, 0) {sql_op} ?"

    if field == "last_login_days":
        params.append(int(value))
        sql_op = op_map.get(op, ">=")
        return f"(c.last_login_at IS NULL OR DATEDIFF(DAY, c.last_login_at, GETDATE()) {sql_op} ?)"

    if field == "broker":
        params.append(value)
        return "c.id IN (SELECT ca.customer_id FROM customer_accounts ca JOIN brokers b ON b.id=ca.broker_id WHERE b.slug=?)"

    if field == "program_type":
        params.append(value)
        return "c.id IN (SELECT ca.customer_id FROM customer_accounts ca JOIN programs p ON p.id=ca.program_id WHERE p.type=?)"

    if field == "wallet_balance":
        params.append(float(value))
        sql_op = op_map.get(op, ">=")
        return f"ISNULL(cw.balance, 0) {sql_op} ?"

    if field == "is_verified":
        return f"c.is_verified = {1 if value else 0}"

    if field == "unsubscribed":
        return f"c.unsubscribed = {1 if value else 0}"

    return None
