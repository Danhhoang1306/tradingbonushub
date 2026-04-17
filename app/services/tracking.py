"""Email open/click tracking: pixel injection, click link injection, async logging."""
import asyncio
import base64
import functools
import os
import re
import uuid

import structlog

from app.db.repositories import emails as email_repo
from app.utils.device import parse_ua

logger = structlog.get_logger(__name__)


# ── Pixel injection ───────────────────────────────────────────────────────────

def inject_pixel(html: str, tracking_id: str, base_url: str) -> str:
    pixel_url = f"{base_url.rstrip('/')}/track/{tracking_id}"
    pixel = (
        f'<img src="{pixel_url}" width="1" height="1" '
        f'style="display:none;width:1px;height:1px;" alt="" />'
    )
    if "</body>" in html:
        return html.replace("</body>", f"{pixel}\n</body>")
    return html + pixel


# ── Signature injection ───────────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def _load_signature() -> str:
    """Read signature template once and cache it."""
    sig_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "email_templates",
        "tradingbonushub-signature.html",
    )
    try:
        with open(sig_path, encoding="utf-8") as f:
            raw = f.read()
    except FileNotFoundError:
        logger.warning("signature_template_missing", path=sig_path)
        return ""
    start = raw.find("<!-- ===== BEGIN SIGNATURE")
    end   = raw.find("<!-- ===== END SIGNATURE")
    if start != -1 and end != -1:
        return raw[start:end].strip()
    return raw


def inject_signature(html: str, ticket_id: str) -> str:
    sig = _load_signature().replace("[ticket]", ticket_id)
    if "<!-- [SIGNATURE] -->" in html:
        return html.replace("<!-- [SIGNATURE] -->", sig)
    if "</body>" in html:
        return html.replace("</body>", f"{sig}\n</body>")
    return html + sig


def sign_email(html: str, ticket_id: str | None = None) -> tuple[str, str]:
    """Assign a ticket and inject signature. Returns (signed_html, ticket_id).

    Pass ticket_id when the caller already owns a tracking UUID (e.g. campaign,
    send_single). Omit it for transactional emails — a fresh UUID will be created.
    """
    ticket_id = ticket_id or str(uuid.uuid4())
    return inject_signature(html, ticket_id), ticket_id


# ── Click link injection ──────────────────────────────────────────────────────

_SKIP_SCHEMES = re.compile(r'^(mailto:|tel:|#|javascript:)', re.I)

def _encode_url(url: str) -> str:
    return base64.urlsafe_b64encode(url.encode()).decode()

def decode_click_url(encoded: str) -> str:
    try:
        return base64.urlsafe_b64decode(encoded.encode()).decode()
    except Exception:
        return ""

def inject_click_links(html: str, tracking_id: str, base_url: str) -> str:
    """Replace every <a href="..."> with a tracked redirect URL.

    Skips mailto:, tel:, #anchors, and already-tracked links.
    Captures the button/link text as link_label for reporting.
    """
    base = base_url.rstrip("/")
    click_base = f"{base}/click/{tracking_id}"

    def _replace(m: re.Match) -> str:
        before   = m.group(1)   # everything before href value
        orig_url = m.group(2)   # the href value
        after    = m.group(3)   # everything after href value up to >
        inner    = m.group(4)   # content between <a ...> and </a>

        if _SKIP_SCHEMES.match(orig_url):
            return m.group(0)
        if f"/click/{tracking_id}" in orig_url:
            return m.group(0)   # already wrapped

        # Build label from inner text (strip HTML tags)
        label = re.sub(r'<[^>]+>', '', inner).strip()[:200]
        label_enc = base64.urlsafe_b64encode(label.encode()).decode() if label else ""

        encoded = _encode_url(orig_url)
        new_url  = f"{click_base}?u={encoded}"
        if label_enc:
            new_url += f"&l={label_enc}"
        return f"{before}{new_url}{after}{inner}</a>"

    # Match <a ... href="..." ...>...</a>  (non-greedy, handles multiline)
    pattern = re.compile(
        r'(<a\b[^>]*\bhref=["\'])([^"\']+)(["\'][^>]*>)(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    return pattern.sub(_replace, html)


# ── Async open logging ────────────────────────────────────────────────────────

async def log_open_async(tracking_id: str, ip: str, raw_ua: str) -> None:
    """Fire-and-forget: log a pixel open without blocking the pixel response."""
    try:
        exists = await asyncio.to_thread(email_repo.tracking_id_exists, tracking_id)
        if exists:
            device_type, os_name, email_client = await asyncio.to_thread(parse_ua, raw_ua)
            await asyncio.to_thread(
                email_repo.log_open,
                tracking_id, ip, raw_ua, device_type, os_name, email_client,
            )
            logger.debug("tracking.open_logged", tracking_id=tracking_id, ip=ip)
    except Exception as e:
        logger.error("tracking.log_failed", tracking_id=tracking_id, error=str(e))


# ── Async click logging ───────────────────────────────────────────────────────

async def log_click_async(tracking_id: str, ip: str, raw_ua: str,
                          destination_url: str, link_label: str) -> None:
    """Fire-and-forget: log a link click without blocking the redirect."""
    try:
        exists = await asyncio.to_thread(email_repo.tracking_id_exists, tracking_id)
        if exists:
            device_type, os_name, _ = await asyncio.to_thread(parse_ua, raw_ua)
            await asyncio.to_thread(
                email_repo.log_click,
                tracking_id, ip, raw_ua, device_type, os_name,
                destination_url, link_label or None,
            )
            logger.debug("tracking.click_logged", tracking_id=tracking_id,
                         url=destination_url[:80])
    except Exception as e:
        logger.error("tracking.click_log_failed", tracking_id=tracking_id, error=str(e))
