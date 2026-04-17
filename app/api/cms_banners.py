"""CMS Banners API."""
from fastapi import APIRouter, HTTPException, Request

from app.db.repositories.cms_banners import (
    create_banner, delete_banner, get_all_banners, update_banner,
)

router = APIRouter(prefix="/api/cms")


@router.get("/banners")
async def api_list_banners():
    return get_all_banners()


@router.post("/banners")
async def api_create_banner(request: Request):
    d = await request.json()
    text = (d.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text is required")
    bid = create_banner(
        text=text,
        link_text=(d.get("link_text") or "").strip(),
        link_url=(d.get("link_url") or "").strip(),
        style=d.get("style") or "info",
        pages=d.get("pages") or "*",
        is_active=bool(d.get("is_active", True)),
        starts_at=d.get("starts_at") or None,
        ends_at=d.get("ends_at") or None,
    )
    return {"ok": True, "id": bid}


@router.put("/banners/{bid}")
async def api_update_banner(bid: int, request: Request):
    d = await request.json()
    text = (d.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text is required")
    update_banner(
        bid=bid,
        text=text,
        link_text=(d.get("link_text") or "").strip(),
        link_url=(d.get("link_url") or "").strip(),
        style=d.get("style") or "info",
        pages=d.get("pages") or "*",
        is_active=bool(d.get("is_active", True)),
        starts_at=d.get("starts_at") or None,
        ends_at=d.get("ends_at") or None,
    )
    return {"ok": True}


@router.delete("/banners/{bid}")
async def api_delete_banner(bid: int):
    delete_banner(bid)
    return {"ok": True}
