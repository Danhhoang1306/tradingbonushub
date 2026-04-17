"""Campaign CRUD and bulk send API."""
import asyncio
import json

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.config import limiter
from app.db.repositories.campaigns import (
    create_campaign, delete_campaign, get_all_campaigns, get_campaign,
    get_campaign_emails, rename_campaign,
)
from app.db.repositories.job_queue import enqueue_job
from app.db.repositories import leads as lead_repo
from app.db.repositories.templates import get_template
from app.services import mailer as mailer_service
from app.utils.audit import log_action
from app.utils.file_parser import parse_file

router = APIRouter(prefix="/api")


@router.get("/campaigns")
async def list_campaigns():
    return get_all_campaigns()


@router.get("/campaigns/{cid}")
async def api_get_campaign(cid: int):
    camp = get_campaign(cid)
    if not camp:
        raise HTTPException(404, "Campaign not found")
    emails = get_campaign_emails(cid)
    return {"campaign": camp, "emails": emails}


@router.get("/campaigns/{cid}/status")
async def campaign_status(cid: int):
    camp = get_campaign(cid)
    if not camp:
        raise HTTPException(404)
    return {k: camp[k] for k in ("id", "status", "total", "sent", "failed")}


@router.put("/campaigns/{cid}/name")
async def api_rename_campaign(cid: int, payload: dict):
    camp = get_campaign(cid)
    if not camp:
        raise HTTPException(404, "Campaign not found")
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Name is required")
    rename_campaign(cid, name)
    return {"ok": True}


@router.delete("/campaigns/{cid}")
async def api_delete_campaign(request: Request, cid: int):
    camp = get_campaign(cid)
    if not camp:
        raise HTTPException(404, "Campaign not found")
    if camp["status"] == "sending":
        raise HTTPException(400, "Campaign is sending — stop it before deleting")
    delete_campaign(cid)
    log_action(request.session.get("user", ""), "campaign.delete",
               entity_type="campaign", entity_id=str(cid))
    return {"ok": True}


@router.post("/campaigns/{cid}/stop")
async def api_stop_campaign(cid: int):
    camp = get_campaign(cid)
    if not camp:
        raise HTTPException(404, "Campaign not found")
    if camp["status"] != "sending":
        raise HTTPException(400, "Campaign is not sending")
    mailer_service.cancel_campaign(cid)
    return {"ok": True}


@router.post("/campaigns", status_code=201)
@limiter.limit("5/minute")
async def api_create_campaign(
    request: Request,
    name: str = Form(...),
    template_id: int = Form(...),
    subject: str = Form("Notification from TradingBonusHub"),
    base_url: str = Form("https://tradingbonushub.com"),
    email_column: str = Form(...),
    name_column: str = Form(""),
    mapping_json: str = Form("{}"),
    data_file: UploadFile = File(...),
):
    tmpl = get_template(template_id)
    if not tmpl:
        raise HTTPException(400, "Template not found")

    try:
        mapping = json.loads(mapping_json)
    except Exception:
        raise HTTPException(400, "Invalid mapping_json")

    content = await data_file.read()
    from app.utils.file_validation import check_upload_size, MAX_UPLOAD_DATA
    check_upload_size(content, MAX_UPLOAD_DATA, "Data file")
    rows = await asyncio.to_thread(parse_file, content, data_file.filename or "")
    if not rows:
        raise HTTPException(400, "File has no valid data")

    cid = create_campaign(name, template_id, subject)
    enqueue_job("campaign", {
        "campaign_id": cid,
        "template_id": template_id,
        "rows": rows,
        "base_url": base_url,
        "email_column": email_column,
        "mapping": mapping,
        "name_column": name_column,
        "subject": subject,
    })
    log_action(request.session.get("user", ""), "campaign.create",
               entity_type="campaign", entity_id=str(cid),
               detail={"name": name, "total": len(rows)})
    return {"id": cid, "total": len(rows)}


@router.post("/campaigns/from-leads", status_code=201)
@limiter.limit("5/minute")
async def api_create_campaign_from_leads(request: Request, payload: dict):
    """Create a campaign from leads stored in the DB.

    payload: {
        name, template_id, subject, base_url,
        mapping: { "[Placeholder]": "lead_field", ... },
        filters: { country?, source?, search?, lead_ids?: [int], exclude_campaign_id?: int }
    }
    """
    name = (payload.get("name") or "").strip()
    template_id = payload.get("template_id")
    subject = payload.get("subject", "Notification from TradingBonusHub")
    base_url = payload.get("base_url", "https://tradingbonushub.com")
    mapping = payload.get("mapping") or {}
    filters = payload.get("filters") or {}

    if not name:
        raise HTTPException(400, "Campaign name is required")
    tmpl = get_template(template_id)
    if not tmpl:
        raise HTTPException(400, "Template not found")

    # Fetch leads based on filters (auto-excludes unsubscribed customers)
    leads_list = await asyncio.to_thread(
        lead_repo.get_leads_for_campaign,
        lead_ids=filters.get("lead_ids"),
        country=filters.get("country"),
        source=filters.get("source"),
        search=filters.get("search"),
        exclude_campaign_id=filters.get("exclude_campaign_id"),
    )
    if not leads_list:
        raise HTTPException(400, "No leads match the given filters (or all are unsubscribed)")

    # Check overlap: how many lead emails also exist as registered customers
    lead_emails = [l["email"] for l in leads_list]
    overlap_count = await asyncio.to_thread(_count_email_overlap, lead_emails)

    # Convert leads to row dicts for the mailer (merge extra_data into top-level)
    rows = []
    lead_id_list = []
    for lead in leads_list:
        row = {
            "email": lead["email"],
            "name": lead["name"],
            "country": lead["country"],
            "mobile": lead["mobile"],
            "user_id": lead["user_id"],
            "sales": lead["sales"],
            "affid": lead["affid"],
            "leads_type": lead["leads_type"],
        }
        # Merge extra_data fields
        try:
            extra = json.loads(lead.get("extra_data") or "{}")
            row.update(extra)
        except (json.JSONDecodeError, TypeError):
            pass
        row["__lead_id__"] = lead["id"]
        rows.append(row)
        lead_id_list.append(lead["id"])

    cid = create_campaign(name, template_id, subject)
    enqueue_job("campaign", {
        "campaign_id": cid,
        "template_id": template_id,
        "rows": rows,
        "base_url": base_url,
        "email_column": "email",
        "mapping": mapping,
        "name_column": "name",
        "subject": subject,
        "from_leads": True,
        "lead_ids": lead_id_list,
    })
    log_action(request.session.get("user", ""), "campaign.create_from_leads",
               entity_type="campaign", entity_id=str(cid),
               detail={"name": name, "total": len(rows), "filters": filters})
    return {
        "id": cid,
        "total": len(rows),
        "overlap_with_customers": overlap_count,
    }


def _count_email_overlap(emails: list[str]) -> int:
    """Count how many lead emails also exist as registered customers."""
    if not emails:
        return 0
    from app.db.connection import get_conn
    # Check against customers.login_email (portal accounts)
    ph = ",".join("?" * len(emails))
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT COUNT(DISTINCT login_email) AS cnt FROM customers "
            f"WHERE login_email IN ({ph})",
            emails,
        ).fetchone()
        return row["cnt"] if row else 0
