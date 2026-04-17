"""Email template CRUD API."""
import asyncio

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.db.repositories.templates import (
    create_template, delete_template, get_all_templates, get_template, update_template,
)
from app.utils.audit import log_action
from app.utils.file_parser import get_columns, parse_file
from app.utils.placeholder import extract_placeholders

router = APIRouter(prefix="/api")


class TemplateCreate(BaseModel):
    name: str
    html_content: str


@router.get("/templates")
async def list_templates():
    return get_all_templates()


@router.post("/templates", status_code=201)
async def api_create_template(request: Request, payload: TemplateCreate):
    tid = create_template(payload.name, payload.html_content)
    log_action(request.session.get("user", ""), "template.create",
               entity_type="template", entity_id=str(tid),
               detail={"name": payload.name})
    return {"id": tid}


@router.get("/templates/{tid}")
async def api_get_template(tid: int):
    t = get_template(tid)
    if not t:
        raise HTTPException(404, "Template not found")
    return t


@router.get("/templates/{tid}/placeholders")
async def api_get_placeholders(tid: int):
    t = get_template(tid)
    if not t:
        raise HTTPException(404, "Template not found")
    return {"placeholders": extract_placeholders(t["html_content"])}


@router.put("/templates/{tid}")
async def api_update_template(request: Request, tid: int, payload: TemplateCreate):
    if not get_template(tid):
        raise HTTPException(404, "Template not found")
    update_template(tid, payload.name, payload.html_content)
    log_action(request.session.get("user", ""), "template.update",
               entity_type="template", entity_id=str(tid),
               detail={"name": payload.name})
    return {"ok": True}


@router.delete("/templates/{tid}")
async def api_delete_template(request: Request, tid: int):
    t = get_template(tid)
    if not t:
        raise HTTPException(404, "Template not found")
    try:
        delete_template(tid)
    except Exception as exc:
        msg = str(exc)
        if "FK_campaigns_template" in msg or "FOREIGN KEY" in msg or "REFERENCE" in msg:
            raise HTTPException(
                400,
                "Template is used by one or more campaigns — "
                "delete or change the template in those campaigns first."
            )
        raise HTTPException(500, "Error deleting template. Please try again.")
    log_action(request.session.get("user", ""), "template.delete",
               entity_type="template", entity_id=str(tid))
    return {"ok": True}


@router.post("/parse-file")
async def api_parse_file(file: UploadFile = File(...)):
    content = await file.read()
    rows = await asyncio.to_thread(parse_file, content, file.filename or "")
    if not rows:
        raise HTTPException(400, "File has no data")
    columns = get_columns(rows)
    preview = rows[:5]
    return {"columns": columns, "preview": preview, "total": len(rows)}
