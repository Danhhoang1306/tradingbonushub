"""Telegram webhook + utility endpoints."""
import hashlib
import hmac

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.db.repositories.portal_settings import get_portal_settings
from app.db.repositories.telegram import (
    create_link_token,
    get_telegram_session,
)
from app.services.telegram_bot import handle_update, set_webhook

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/telegram")


def _get_webhook_secret() -> str:
    """Derive webhook secret from bot token for Telegram's secret_token verification."""
    ps = get_portal_settings()
    token = ps.get("telegram_bot_token", "")
    if not token:
        return ""
    # Use HMAC-SHA256 of the bot token as the webhook secret
    return hmac.new(b"WebAppData", token.encode(), hashlib.sha256).hexdigest()[:64]


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """Telegram calls this endpoint for every update.

    Validates the X-Telegram-Bot-Api-Secret-Token header to ensure the
    request actually comes from Telegram (set via setWebhook secret_token).
    """
    # Verify webhook secret if configured
    expected = _get_webhook_secret()
    if expected:
        received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(received, expected):
            logger.warning("telegram_webhook.unauthorized",
                           ip=request.client.host if request.client else "")
            return JSONResponse({"ok": False}, status_code=403)

    try:
        update = await request.json()
        await handle_update(update)
    except Exception as exc:
        logger.warning("telegram_webhook.error", error=str(exc))
    return {"ok": True}


@router.get("/link")
async def get_telegram_link(request: Request):
    """Return a deep-link URL for the logged-in customer."""
    email = request.session.get("customer_email", "")
    if not email:
        return JSONResponse({"ok": False, "detail": "Not logged in"}, status_code=401)

    ps = get_portal_settings()
    bot_name = ps.get("telegram_bot_name", "")

    if not bot_name:
        # Fallback to generic URL if bot not configured
        url = ps.get("telegram_url", "")
        return {"ok": bool(url), "url": url, "linked": False}

    linked = get_telegram_session(email) is not None
    if linked:
        # Already linked — open the bot directly (no start param needed)
        return {"ok": True, "url": f"https://t.me/{bot_name}", "linked": True}

    token = create_link_token(email)
    return {"ok": True, "url": f"https://t.me/{bot_name}?start={token}", "linked": False}


@router.post("/set-webhook")
async def api_set_webhook(request: Request):
    """Register webhook URL with Telegram (call once after bot setup)."""
    if not request.session.get("user"):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    body = await request.json()
    site_url = body.get("site_url", "https://tradingbonushub.com")
    secret = _get_webhook_secret()
    ok = await set_webhook(site_url, secret_token=secret)
    return {"ok": ok}
