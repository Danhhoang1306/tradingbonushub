"""Telegram relay bot service."""
import httpx
import structlog

from app.db.repositories.portal_settings import get_portal_settings
from app.db.repositories.telegram import (
    delete_link_token,
    get_customer_by_admin_message,
    get_link_token,
    get_session_by_chat_id,
    save_message_map,
    upsert_telegram_session,
)

logger = structlog.get_logger(__name__)

_TG_API = "https://api.telegram.org/bot{token}/{method}"


def _cfg():
    ps = get_portal_settings()
    return ps.get("telegram_bot_token", ""), ps.get("telegram_admin_chat_id", "")


async def _call(method: str, token: str, **payload) -> dict | None:
    url = _TG_API.format(token=token, method=method)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json=payload)
            data = r.json()
            if data.get("ok"):
                return data["result"]
            logger.warning("telegram.api_error", method=method, desc=data.get("description"))
    except Exception as exc:
        logger.warning("telegram.request_failed", method=method, error=str(exc))
    return None


async def send_message(chat_id: int, text: str) -> dict | None:
    token, _ = _cfg()
    if not token:
        return None
    return await _call("sendMessage", token, chat_id=chat_id, text=text, parse_mode="HTML")


async def notify_admin(text: str) -> bool:
    """Send a one-way notification to the admin notification chat.

    Reads `admin_notify_chat_id` from portal settings; falls back to
    `telegram_admin_chat_id` (the customer-support relay group) if the
    dedicated notify chat is not configured, so upgrades don't silently
    stop delivering notifications.
    """
    token, support_chat_id = _cfg()
    if not token:
        return False
    ps = get_portal_settings()
    notify_chat_id = (ps.get("admin_notify_chat_id") or "").strip() or support_chat_id
    if not notify_chat_id:
        return False
    result = await _call(
        "sendMessage", token,
        chat_id=int(notify_chat_id), text=text, parse_mode="HTML",
        disable_web_page_preview=True,
    )
    return result is not None


async def set_webhook(site_url: str, secret_token: str = "") -> bool:
    """Register the webhook URL with Telegram. Call once after setup."""
    token, _ = _cfg()
    if not token:
        return False
    kwargs = {"url": f"{site_url.rstrip('/')}/api/telegram/webhook"}
    if secret_token:
        kwargs["secret_token"] = secret_token
    result = await _call("setWebhook", token, **kwargs)
    return result is not None


async def handle_update(update: dict):
    """Route an incoming Telegram update."""
    token, admin_chat_id = _cfg()
    if not token:
        return

    message = update.get("message")
    if not message:
        return

    chat_id: int = message["chat"]["id"]
    text: str = message.get("text", "")
    reply_to = message.get("reply_to_message")

    # ── /start TOKEN — customer linking ──────────────────────────────────────
    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        link_token = parts[1].strip() if len(parts) > 1 else ""
        if link_token:
            row = get_link_token(link_token)
            if row:
                login_email = row["login_email"]
                upsert_telegram_session(login_email, chat_id)
                delete_link_token(link_token)
                await send_message(
                    chat_id,
                    f"✅ Hello! Account <b>{login_email}</b> has been connected.\n\n"
                    "You can message us directly here. Our support team will respond as soon as possible.",
                )
                if admin_chat_id:
                    await send_message(
                        int(admin_chat_id),
                        f"🔔 <b>New customer connected via Telegram</b>\nEmail: <code>{login_email}</code>",
                    )
                return
        await send_message(
            chat_id,
            "⚠️ Link has expired. Please log in to the customer portal and click the Telegram button again.",
        )
        return

    # ── Reply from admin group → forward to customer ─────────────────────────
    if admin_chat_id and str(chat_id) == str(admin_chat_id):
        if reply_to and text:
            customer_chat_id = get_customer_by_admin_message(reply_to["message_id"])
            if customer_chat_id:
                await send_message(
                    customer_chat_id,
                    f"💬 <b>Support:</b> {text}",
                )
            else:
                await send_message(chat_id, "⚠️ Could not find customer for this message.")
        return

    # ── Message from customer → forward to admin ─────────────────────────────
    session = get_session_by_chat_id(chat_id)
    if not session:
        await send_message(
            chat_id,
            "⚠️ Account not connected. Please log in to the customer portal and click the Telegram button.",
        )
        return

    if not admin_chat_id:
        await send_message(chat_id, "⚠️ Support system not configured. Please contact us via email.")
        return

    result = await _call(
        "sendMessage", token,
        chat_id=int(admin_chat_id),
        text=f"💬 <b>{session['login_email']}</b>\n{text}",
        parse_mode="HTML",
    )
    if result:
        save_message_map(result["message_id"], chat_id)
