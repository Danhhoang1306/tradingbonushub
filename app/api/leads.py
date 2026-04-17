"""Imported Leads: import, manage, and campaign send tracking API.

All endpoints use the /api/imported-leads prefix to avoid collision with
the existing /api/leads endpoint in customers.py (which queries customer_accounts).
"""
import asyncio
import json
import re

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.config import limiter
from app.db.repositories import leads as lead_repo
from app.utils.audit import log_action
from app.utils.file_parser import parse_file_with_custom_headers

router = APIRouter(prefix="/api/imported-leads")

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

# Values that are meaningless / placeholder — treat as empty
_JUNK_VALUES = {"", "-", "—", "0", "none", "null", "n/a", "na", "nil", ".", ".."}


def _clean(val: str) -> str:
    """Return empty string if the value is meaningless junk."""
    v = (val or "").strip()
    return "" if v.lower() in _JUNK_VALUES else v


# Normalised aliases → canonical field names
_FIELD_ALIASES = {
    "email":      ["email", "e-mail", "mail", "email address"],
    "name":       ["name", "full name", "client name", "client name (en)",
                   "client name (ipt)", "họ tên", "tên"],
    "country":    ["country", "contry", "quốc gia", "quoc gia"],
    "mobile":     ["mobile", "phone", "điện thoại", "dien thoai", "số điện thoại"],
    "user_id":    ["user id", "userid", "uid", "user_id", "use id"],
    "sales":      ["sales", "sales person", "nhân viên"],
    "affid":      ["affid", "aff id", "affiliate id"],
    "leads_type": ["leads type", "lead type", "loại lead"],
}

def _build_field_map(columns: list[str]) -> dict[str, str]:
    """Map actual column names to canonical field names using aliases."""
    result = {}
    for col in columns:
        col_lower = col.strip().lower()
        for field, aliases in _FIELD_ALIASES.items():
            if col_lower in aliases:
                result[field] = col
                break
    return result


# ── List / search ────────────────────────────────────────────────────────────

@router.get("")
async def api_list_leads(
    limit: int = 100, offset: int = 0,
    search: str = "", country: str = "", source: str = "",
):
    """List leads from the leads table (imported data)."""
    limit = min(max(limit, 1), 1000)
    s = search.strip() or None
    c = country.strip() or None
    src = source.strip() or None
    rows = await asyncio.to_thread(lead_repo.get_leads, limit, offset, s, c, src)
    total = await asyncio.to_thread(lead_repo.count_leads, s, c, src)

    # Attach last campaign send status for each lead
    lead_ids = [r["id"] for r in rows]
    last_statuses = await asyncio.to_thread(_get_last_campaign_statuses, lead_ids) if lead_ids else {}

    for r in rows:
        for dtf in ("created_at", "updated_at"):
            if r.get(dtf):
                r[dtf] = str(r[dtf])
        info = last_statuses.get(r["id"])
        r["_last_campaign"] = info["campaign_name"] if info else ""
        r["_last_status"] = info["status"] if info else ""
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


def _get_last_campaign_statuses(lead_ids: list[int]) -> dict:
    """Return {lead_id: {campaign_name, status}} for the most recent campaign per lead."""
    if not lead_ids:
        return {}
    from app.db.connection import get_conn
    ph = ",".join("?" * len(lead_ids))
    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT lcs.lead_id, c.name AS campaign_name, lcs.status
                FROM lead_campaign_status lcs
                JOIN campaigns c ON c.id = lcs.campaign_id
                WHERE lcs.lead_id IN ({ph})
                  AND lcs.id = (
                    SELECT MAX(lcs2.id) FROM lead_campaign_status lcs2
                    WHERE lcs2.lead_id = lcs.lead_id
                  )""",
            lead_ids,
        ).fetchall()
    return {r["lead_id"]: dict(r) for r in rows}


# ── Filters (static endpoints BEFORE path params to avoid route ambiguity) ───

@router.get("/filters")
async def api_lead_filters():
    """Return distinct countries and sources for filter dropdowns."""
    countries = await asyncio.to_thread(lead_repo.get_distinct_countries)
    sources = await asyncio.to_thread(lead_repo.get_distinct_sources)
    return {"countries": countries, "sources": sources}


@router.get("/imports")
async def api_list_imports():
    rows = await asyncio.to_thread(lead_repo.get_all_imports)
    for r in rows:
        if r.get("created_at"):
            r["created_at"] = str(r["created_at"])
    return rows


@router.get("/campaign-status/{campaign_id}")
async def api_campaign_lead_statuses(campaign_id: int):
    """Get send status for all leads in a campaign."""
    rows = await asyncio.to_thread(lead_repo.get_campaign_lead_statuses, campaign_id)
    for r in rows:
        if r.get("sent_at"):
            r["sent_at"] = str(r["sent_at"])
    return rows


@router.get("/failed/{campaign_id}")
async def api_failed_leads(campaign_id: int):
    """Get leads that failed in a campaign — for retry."""
    rows = await asyncio.to_thread(lead_repo.get_failed_leads_for_campaign, campaign_id)
    for r in rows:
        for dtf in ("created_at", "updated_at"):
            if r.get(dtf):
                r[dtf] = str(r[dtf])
    return rows


# ── Single lead (path-param endpoints AFTER static ones) ─────────────────────

@router.get("/{lead_id}")
async def api_get_lead(lead_id: int):
    lead = await asyncio.to_thread(lead_repo.get_lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    for dtf in ("created_at", "updated_at"):
        if lead.get(dtf):
            lead[dtf] = str(lead[dtf])
    history = await asyncio.to_thread(lead_repo.get_lead_send_history, lead_id)
    for h in history:
        for dtf in ("sent_at",):
            if h.get(dtf):
                h[dtf] = str(h[dtf])
    return {"lead": lead, "campaign_history": history}


@router.delete("/{lead_id}")
async def api_delete_lead(request: Request, lead_id: int):
    lead = await asyncio.to_thread(lead_repo.get_lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    await asyncio.to_thread(lead_repo.delete_lead, lead_id)
    log_action(request.session.get("user", ""), "lead.delete",
               entity_type="lead", entity_id=str(lead_id))
    return {"ok": True}


# ── Import ───────────────────────────────────────────────────────────────────

@router.post("/import", status_code=201)
@limiter.limit("10/minute")
async def api_import_leads(
    request: Request,
    data_file: UploadFile = File(...),
    use_custom_headers: bool = Form(True),
):
    """Import leads from Excel/CSV.

    use_custom_headers=True: Row 1 = default headers, Row 2 = custom headers, data from Row 3.
    use_custom_headers=False: standard parse (Row 1 = headers, data from Row 2).
    """
    content = await data_file.read()
    from app.utils.file_validation import check_upload_size, MAX_UPLOAD_DATA
    check_upload_size(content, MAX_UPLOAD_DATA, "Data file")
    filename = data_file.filename or "unknown"

    if use_custom_headers:
        rows = await asyncio.to_thread(
            parse_file_with_custom_headers, content, filename
        )
    else:
        from app.utils.file_parser import parse_file
        rows = await asyncio.to_thread(parse_file, content, filename)

    if not rows:
        raise HTTPException(400, "File has no valid data")

    # Auto-detect column mapping
    columns = list(rows[0].keys())
    field_map = _build_field_map(columns)

    if "email" not in field_map:
        raise HTTPException(400,
            f"Cannot find email column. Columns found: {columns}")

    actor = request.session.get("user", "")
    import_id = await asyncio.to_thread(lead_repo.create_import, filename, actor)

    new_count = 0
    updated_count = 0
    skipped_count = 0

    for row in rows:
        email = (row.get(field_map["email"]) or "").strip().lower()
        if not email or not _EMAIL_RE.match(email):
            skipped_count += 1
            continue

        # Build known fields from mapping — skip junk values like "-", "0"
        kwargs = {"email": email, "import_id": import_id, "source": filename}
        for field in ("name", "country", "mobile", "user_id", "sales",
                       "affid", "leads_type"):
            if field in field_map:
                kwargs[field] = _clean(row.get(field_map[field]) or "")

        # Extra data: only keep columns with meaningful values
        mapped_cols = set(field_map.values())
        extra = {k: v for k, v in row.items()
                 if k not in mapped_cols and _clean(v)}
        kwargs["extra_data"] = extra

        _, is_new = await asyncio.to_thread(lead_repo.upsert_lead, **kwargs)
        if is_new:
            new_count += 1
        else:
            updated_count += 1

    await asyncio.to_thread(
        lead_repo.update_import_stats, import_id,
        len(rows), new_count, updated_count, skipped_count,
    )

    log_action(actor, "lead.import", entity_type="lead_import",
               entity_id=str(import_id),
               detail={"file": filename, "total": len(rows),
                       "new": new_count, "updated": updated_count,
                       "skipped": skipped_count})

    return {
        "ok": True,
        "import_id": import_id,
        "total": len(rows),
        "new": new_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "columns_detected": columns,
        "field_mapping": {k: v for k, v in field_map.items()},
    }
