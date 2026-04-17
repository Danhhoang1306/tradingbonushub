"""Email tracking and single send API."""
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse

from app.config import limiter
from app.db.repositories.customers import get_all_customers
from app.db.repositories.emails import (count_emails, create_email, get_all_emails,
                                         get_clicks, get_email_detail)
from app.db.repositories.smtp import get_smtp_config
from app.services.mailer import send_one
from app.services.tracking import inject_click_links, inject_pixel, inject_signature, sign_email

router = APIRouter(prefix="/api")


@router.get("/emails")
async def list_emails(limit: int = 200, offset: int = 0):
    limit = min(max(limit, 1), 500)
    rows = get_all_emails(limit=limit, offset=offset)
    total = count_emails()
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/emails/{tracking_id}")
async def email_detail(tracking_id: str):
    email, opens = get_email_detail(tracking_id)
    if not email:
        raise HTTPException(404, "Email not found")
    clicks = get_clicks(tracking_id)
    return {"email": email, "opens": opens, "clicks": clicks}


@router.get("/customers-search")
async def customers_search(q: str = ""):
    all_c = get_all_customers(limit=1000, offset=0)
    q_lower = q.lower()
    results = [
        c for c in all_c
        if q_lower in (c.get("login_email") or "").lower()
        or q_lower in (c.get("name") or "").lower()
    ]
    # Add 'email' alias for frontend compatibility (compose.html uses c.email)
    for c in results:
        c["email"] = c.get("login_email") or ""
    return results[:10]


@router.post("/compose-preview")
async def compose_preview(payload: dict):
    html_body = payload.get("html_body", "")
    dummy_ticket = payload.get("dummy_ticket", "PREVIEW")
    html = inject_signature(html_body, dummy_ticket)
    return {"html": html}


@router.post("/send-single")
@limiter.limit("20/minute")
async def send_single(
    request: Request,
    recipient_email: str = Form(...),
    recipient_name: str = Form(""),
    subject: str = Form(...),
    html_body: str = Form(...),
    base_url: str = Form("https://tradingbonushub.com"),
    files: list[UploadFile] = File(default=[]),
):
    cfg = get_smtp_config()
    if not cfg.get("host") or cfg.get("host") == "localhost":
        raise HTTPException(400, "SMTP not configured")
    html, tracking_id = sign_email(html_body)
    html = inject_click_links(html, tracking_id, base_url)
    html = inject_pixel(html, tracking_id, base_url)
    create_email(tracking_id, recipient_name or recipient_email, recipient_email,
                 html, subject=subject)
    attachments = []
    for f in files:
        if f.filename:
            data = await f.read()
            attachments.append((f.filename, data, f.content_type or "application/octet-stream"))
    try:
        await send_one(cfg, recipient_email, recipient_name, subject, html,
                       attachments=attachments or None, skip_signature=True)
    except Exception as e:
        from app.services.mailer import _friendly_error
        raise HTTPException(500, _friendly_error(e))
    return {"success": True, "tracking_id": tracking_id}


@router.post("/send-test")
async def api_send_test(request: Request):
    data = await request.json()
    template_id = data.get("template_id")
    to_email = (data.get("to_email") or "").strip()
    subject = (data.get("subject") or "Test email").strip()
    row_data = data.get("row_data") or {}
    mapping = data.get("mapping") or {}

    if not to_email:
        raise HTTPException(400, "Missing recipient email")

    from app.db.repositories.templates import get_template
    from app.utils.placeholder import render_dynamic

    t = get_template(template_id)
    if not t:
        raise HTTPException(404, "Template not found")

    cfg = get_smtp_config()
    if not cfg.get("host"):
        raise HTTPException(400, "SMTP not configured")

    rendered = render_dynamic(t["html_content"], row_data, mapping)
    try:
        await send_one(cfg, to_email, "", subject, rendered)
    except Exception as e:
        from app.services.mailer import _friendly_error
        raise HTTPException(500, _friendly_error(e))
    return {"ok": True}
