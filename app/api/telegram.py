"""Telegram admin-notifier test endpoint."""
from fastapi import APIRouter, HTTPException, Request

from app.services.telegram_bot import test_send

router = APIRouter(prefix="/api/telegram")


@router.post("/test")
async def api_telegram_test(request: Request):
    """Send a test message to verify the admin-entered token + chat_id."""
    if not request.session.get("user"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    data = await request.json()
    token = (data.get("token") or "").strip()
    chat_id = (data.get("chat_id") or "").strip()
    if not token or not chat_id:
        raise HTTPException(status_code=400, detail="Missing token or chat_id")
    ok, desc = await test_send(token, chat_id)
    return {"ok": ok, "detail": desc}
