"""Google OAuth configuration API."""
from fastapi import APIRouter, Request

from app.db.repositories.smtp import get_google_oauth_config, save_google_oauth_config

router = APIRouter(prefix="/api")


@router.get("/google-oauth-config")
async def api_get_google_oauth():
    cfg = get_google_oauth_config()
    return {
        "client_id": cfg.get("client_id", ""),
        "site_url": cfg.get("site_url", ""),
        # client_secret never returned to frontend
    }


@router.post("/google-oauth-config")
async def api_save_google_oauth(request: Request):
    data = await request.json()
    client_id = (data.get("client_id") or "").strip()
    client_secret = (data.get("client_secret") or "").strip()
    site_url = (data.get("site_url") or "").strip()
    if not client_secret:
        existing = get_google_oauth_config()
        client_secret = existing.get("client_secret", "")
    save_google_oauth_config(client_id, client_secret, site_url)
    return {"ok": True}
