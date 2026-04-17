"""FAQ management API — admin only."""
from fastapi import APIRouter, HTTPException, Request

from app.db.repositories.faq import (
    create_faq_item, delete_faq_item, get_faq_item,
    get_faq_items, update_faq_item,
)

router = APIRouter(prefix="/api")


@router.get("/faq")
async def api_list_faq():
    return get_faq_items(active_only=False)


@router.post("/faq")
async def api_create_faq(request: Request):
    data = await request.json()
    q = (data.get("question") or "").strip()
    a = (data.get("answer") or "").strip()
    if not q or not a:
        raise HTTPException(400, "question and answer are required")
    broker_id = data.get("broker_id")
    broker_id = int(broker_id) if broker_id else None
    display_order = int(data.get("display_order") or 0)
    is_active = bool(data.get("is_active", True))
    question_en = (data.get("question_en") or "").strip() or None
    answer_en = (data.get("answer_en") or "").strip() or None
    fid = create_faq_item(q, a, broker_id, display_order, is_active,
                          question_en=question_en, answer_en=answer_en)
    return {"ok": True, "id": fid}


@router.put("/faq/{fid}")
async def api_update_faq(fid: int, request: Request):
    item = get_faq_item(fid)
    if not item:
        raise HTTPException(404, "FAQ not found")
    data = await request.json()
    q = (data.get("question") or "").strip()
    a = (data.get("answer") or "").strip()
    if not q or not a:
        raise HTTPException(400, "question and answer are required")
    broker_id = data.get("broker_id")
    broker_id = int(broker_id) if broker_id else None
    display_order = int(data.get("display_order") or 0)
    is_active = bool(data.get("is_active", True))
    question_en = (data.get("question_en") or "").strip() or None
    answer_en = (data.get("answer_en") or "").strip() or None
    update_faq_item(fid, q, a, broker_id, display_order, is_active,
                    question_en=question_en, answer_en=answer_en)
    return {"ok": True}


@router.delete("/faq/{fid}")
async def api_delete_faq(fid: int):
    item = get_faq_item(fid)
    if not item:
        raise HTTPException(404, "FAQ not found")
    delete_faq_item(fid)
    return {"ok": True}
