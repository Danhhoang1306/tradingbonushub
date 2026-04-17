"""CMS Navigation API."""
from fastapi import APIRouter, HTTPException, Request

from app.db.repositories.cms_navigation import (
    create_nav_item, delete_nav_item, get_nav_items,
    reorder_nav_items, update_nav_item,
)

router = APIRouter(prefix="/api/cms")


@router.get("/nav")
async def api_list_nav(menu: str | None = None):
    return get_nav_items(menu)


@router.post("/nav")
async def api_create_nav(request: Request):
    d = await request.json()
    label = (d.get("label") or "").strip()
    url = (d.get("url") or "").strip()
    if not label or not url:
        raise HTTPException(400, "label and url are required")
    nid = create_nav_item(
        menu=d.get("menu") or "public_header",
        label=label, url=url,
        target=d.get("target") or "_self",
        parent_id=d.get("parent_id") or None,
        display_order=int(d.get("display_order") or 0),
        is_active=bool(d.get("is_active", True)),
    )
    return {"ok": True, "id": nid}


@router.put("/nav/{nid}")
async def api_update_nav(nid: int, request: Request):
    d = await request.json()
    label = (d.get("label") or "").strip()
    url = (d.get("url") or "").strip()
    if not label or not url:
        raise HTTPException(400, "label and url are required")
    update_nav_item(
        nid=nid,
        menu=d.get("menu") or "public_header",
        label=label, url=url,
        target=d.get("target") or "_self",
        parent_id=d.get("parent_id") or None,
        display_order=int(d.get("display_order") or 0),
        is_active=bool(d.get("is_active", True)),
    )
    return {"ok": True}


@router.delete("/nav/{nid}")
async def api_delete_nav(nid: int):
    delete_nav_item(nid)
    return {"ok": True}


@router.put("/nav/reorder")
async def api_reorder_nav(request: Request):
    items = await request.json()
    reorder_nav_items(items)
    return {"ok": True}
