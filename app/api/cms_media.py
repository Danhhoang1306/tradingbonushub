"""CMS Media Library API."""
import structlog
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from app.config import limiter
from app.db.repositories.cms_media import (
    create_media, delete_media, get_all_media, get_media, update_media_alt,
)
from app.services.cms_image import delete_upload, save_upload
from app.utils.file_validation import validate_file_type

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/cms")

ALLOWED_MIME = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "image/svg+xml", "application/pdf",
}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


@router.get("/media")
async def api_list_media(limit: int = 60, offset: int = 0):
    return get_all_media(limit, offset)


@router.post("/media")
@limiter.limit("20/minute")
async def api_upload_media(request: Request, file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(415, f"Unsupported file type: {file.content_type}")

    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(413, "File too large (max 10 MB)")

    # Validate magic bytes to prevent MIME spoofing
    if not validate_file_type(data, file.content_type):
        raise HTTPException(
            415, "File content does not match declared file type."
        )

    uploader = request.session.get("user", "unknown")
    try:
        filename, url, size = save_upload(data, file.filename or "upload", file.content_type)
    except Exception as exc:
        logger.error("cms_media.upload_failed", error=str(exc))
        raise HTTPException(500, "Error saving file")

    mid = create_media(filename, file.filename or "", url, file.content_type, size, uploader)
    logger.info("cms_media.uploaded", id=mid, url=url, uploader=uploader)
    return {"ok": True, "id": mid, "url": url, "filename": filename}


@router.put("/media/{mid}")
async def api_update_media(mid: int, request: Request):
    item = get_media(mid)
    if not item:
        raise HTTPException(404, "File not found")
    data = await request.json()
    update_media_alt(mid, (data.get("alt_text") or "").strip())
    return {"ok": True}


@router.delete("/media/{mid}")
async def api_delete_media(mid: int):
    item = delete_media(mid)
    if not item:
        raise HTTPException(404, "File not found")
    delete_upload(item["url"])
    logger.info("cms_media.deleted", id=mid, url=item["url"])
    return {"ok": True}
