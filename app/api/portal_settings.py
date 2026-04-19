"""Portal settings API."""
from fastapi import APIRouter, Request

from app.db.repositories.portal_settings import get_portal_settings, save_portal_settings
from app.utils.audit import log_action

router = APIRouter(prefix="/api")

_ALLOWED_KEYS = {
    "site_name", "primary_color", "dark_color", "accent_color",
    "support_email", "footer_text", "tab1_name", "tab2_name", "tab3_name",
    "welcome_subtitle", "login_notice", "portal_notice",
    "telegram_url", "chatbox_url",
    "telegram_bot_token", "telegram_chat_id",
    # Marketing & tracking
    "gtm_id", "ga4_id", "fb_pixel_id", "ms_clarity_id",
    "search_console_meta", "og_image_url",
    # Legal pages
    "privacy_url", "terms_url",
    # Social
    "facebook_url", "youtube_url",
    # Sticky promo bar
    "sticky_enabled", "sticky_text_vi", "sticky_text_en",
    "sticky_cta_vi", "sticky_cta_en",
    "sticky_bg", "sticky_link",
}


@router.get("/portal-settings")
async def api_get_portal_settings():
    return get_portal_settings()


@router.post("/portal-settings")
async def api_save_portal_settings(request: Request):
    data = await request.json()
    clean = {k: v for k, v in data.items() if k in _ALLOWED_KEYS}
    save_portal_settings(clean)
    _SKIP_LOG = {"footer_text", "telegram_bot_token"}
    log_action(request.session.get("user", ""), "portal_settings.save",
               detail={k: v for k, v in clean.items() if k not in _SKIP_LOG})
    return {"ok": True}

