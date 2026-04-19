"""Telegram admin notifier — one-way HTML message to a single chat."""
import httpx
import structlog

from app.db.repositories.portal_settings import get_portal_settings

logger = structlog.get_logger(__name__)

_TG_API = "https://api.telegram.org/bot{token}/sendMessage"


async def _send(token: str, chat_id: str, text: str) -> tuple[bool, str]:
    url = _TG_API.format(token=token)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })
            data = r.json()
            if data.get("ok"):
                return True, "ok"
            return False, data.get("description") or "Unknown Telegram error"
    except Exception as exc:
        return False, f"Request failed: {exc}"


async def notify(text: str) -> bool:
    """Send a notification to the configured admin chat. No-op if unconfigured."""
    ps = get_portal_settings()
    token = (ps.get("telegram_bot_token") or "").strip()
    chat_id = (ps.get("telegram_chat_id") or "").strip()
    if not token or not chat_id:
        logger.info("telegram.notify_skipped", reason="not_configured")
        return False
    ok, desc = await _send(token, chat_id, text)
    if ok:
        logger.info("telegram.notify_sent", chat_id=chat_id)
    else:
        logger.warning("telegram.notify_failed", chat_id=chat_id, reason=desc)
    return ok


async def test_send(token: str, chat_id: str) -> tuple[bool, str]:
    """Verify token+chat_id by sending a test message. Returns (ok, description)."""
    text = (
        "✅ <b>TradingBonusHub</b> — Telegram test message\n"
        "If you can read this, your bot token and chat ID are configured correctly."
    )
    return await _send(token, chat_id, text)
