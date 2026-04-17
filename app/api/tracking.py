"""Tracking pixel and click-redirect endpoints."""
import asyncio
from urllib.parse import urlparse

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from app.config import PIXEL_GIF, limiter
from app.services.tracking import decode_click_url, log_click_async, log_open_async

logger = structlog.get_logger(__name__)
router = APIRouter()


def _get_client_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _safe_log_open(tracking_id: str, ip: str, ua: str) -> None:
    try:
        await log_open_async(tracking_id, ip, ua)
    except Exception as exc:
        logger.warning("tracking.log_open_failed", tracking_id=tracking_id, error=str(exc))


@router.get("/track/{tracking_id}")
@limiter.limit("60/minute")
async def track_open(tracking_id: str, request: Request):
    asyncio.create_task(_safe_log_open(
        tracking_id,
        _get_client_ip(request),
        request.headers.get("User-Agent", ""),
    ))
    return Response(
        content=PIXEL_GIF,
        media_type="image/gif",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


@router.get("/click/{tracking_id}")
@limiter.limit("60/minute")
async def track_click(tracking_id: str, request: Request,
                      u: str = "", l: str = ""):
    """Record click then redirect to destination URL.

    u = base64url(destination_url)
    l = base64url(link_label)   [optional]
    """
    destination = decode_click_url(u) if u else ""
    link_label  = decode_click_url(l) if l else ""

    if destination:
        # Validate destination to prevent open redirect attacks
        parsed = urlparse(destination)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            logger.warning("tracking.click_invalid_scheme",
                           tracking_id=tracking_id, url=destination[:80])
            return Response(status_code=400, content="Invalid redirect URL")

        asyncio.create_task(log_click_async(
            tracking_id,
            _get_client_ip(request),
            request.headers.get("User-Agent", ""),
            destination,
            link_label,
        ))
        return RedirectResponse(url=destination, status_code=302)

    # Fallback if URL is broken
    logger.warning("tracking.click_bad_url", tracking_id=tracking_id, raw_u=u[:80])
    return Response(status_code=400, content="Invalid click link")
