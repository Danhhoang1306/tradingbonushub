"""Promo bar templates API."""
from fastapi import APIRouter, HTTPException, Request

from app.db.repositories.promo_bar import (
    create_promo_bar, delete_promo_bar, get_all_promo_bars,
    get_promo_bar, update_promo_bar,
)

router = APIRouter(prefix="/api")


@router.get("/promo-bar")
async def api_list_promo_bars():
    return get_all_promo_bars()


@router.get("/promo-bar/{bar_id}")
async def api_get_promo_bar(bar_id: int):
    b = get_promo_bar(bar_id)
    if not b:
        raise HTTPException(404, "Template not found")
    return b


@router.post("/promo-bar")
async def api_create_promo_bar(request: Request):
    data = await request.json()
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Template name is required")
    bar_id = create_promo_bar(
        name=name,
        html=data.get("html", ""),
        css=data.get("css", ""),
        is_active=bool(data.get("is_active", False)),
    )
    return {"id": bar_id}


@router.put("/promo-bar/{bar_id}")
async def api_update_promo_bar(bar_id: int, request: Request):
    if not get_promo_bar(bar_id):
        raise HTTPException(404, "Template not found")
    data = await request.json()
    update_promo_bar(
        bar_id,
        name=(data.get("name") or "").strip(),
        html=data.get("html", ""),
        css=data.get("css", ""),
        is_active=bool(data.get("is_active", False)),
    )
    return {"ok": True}


@router.delete("/promo-bar/{bar_id}")
async def api_delete_promo_bar(bar_id: int):
    if not get_promo_bar(bar_id):
        raise HTTPException(404, "Template not found")
    delete_promo_bar(bar_id)
    return {"ok": True}
