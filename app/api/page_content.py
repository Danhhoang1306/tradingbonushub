"""API for page content management (GET / PUT)."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db.repositories.page_content import get_all_content, set_content

router = APIRouter()


class ContentItem(BaseModel):
    key: str
    lang: str
    value: str


def _require_admin(request: Request) -> None:
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=403, detail="Access denied")


@router.get("/api/page-content")
def api_get_page_content(lang: str = "en"):
    """Return all page content for the given language."""
    data = get_all_content(lang)
    return {"lang": lang, "content": data}


@router.put("/api/page-content")
async def api_put_page_content(request: Request, item: ContentItem):
    """Upsert a single content key (admin only)."""
    _require_admin(request)
    set_content(item.key, item.lang, item.value)
    return {"ok": True}


@router.put("/api/page-content/bulk")
async def api_bulk_put_page_content(request: Request, items: list[ContentItem]):
    """Upsert multiple content keys at once (admin only)."""
    _require_admin(request)
    for item in items:
        set_content(item.key, item.lang, item.value)
    return {"ok": True, "saved": len(items)}
