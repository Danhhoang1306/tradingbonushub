"""SMTP email sending and bulk campaign runner."""
import asyncio
import smtplib
import ssl
import uuid
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

from app.db.repositories import campaigns as campaign_repo
from app.db.repositories import emails as email_repo
from app.db.repositories import leads as lead_repo
from app.db.repositories.smtp import get_smtp_config
from app.services.tracking import inject_click_links, inject_pixel, sign_email
from app.utils.placeholder import render_dynamic

logger = structlog.get_logger(__name__)

_SMTP_TIMEOUT = 10  # seconds

# ── Cancellation ──────────────────────────────────────────────────────────────

def cancel_campaign(campaign_id: int) -> None:
    """Signal a running campaign to stop — persisted in DB, works across workers."""
    campaign_repo.update_campaign_status(campaign_id, "stopping")


# ── SMTP error messages ───────────────────────────────────────────────────────

def _friendly_error(e: Exception) -> str:
    msg = str(e)
    if "534" in msg or "Application-specific password" in msg:
        return "Gmail requires an App Password (do not use your regular password). Create one at: myaccount.google.com/apppasswords"
    if "535" in msg or "Username and Password not accepted" in msg:
        return "Wrong username or password. For Gmail, use an App Password."
    if "Connection refused" in msg or "111" in msg:
        return f"Cannot connect to server ({msg}). Check host/port."
    if "timed out" in msg.lower():
        return f"Connection timed out after {_SMTP_TIMEOUT}s. Check host/port or firewall."
    if "STARTTLS" in msg:
        return "Server does not support STARTTLS. Try using SSL (port 465) instead of TLS (port 587)."
    if "certificate" in msg.lower() or "ssl" in msg.lower():
        return f"SSL/TLS error: {msg}"
    return msg


# ── SMTP core ─────────────────────────────────────────────────────────────────

def _smtp_send(cfg: dict, msg) -> None:
    """Synchronous SMTP send — runs inside asyncio.to_thread()."""
    host = cfg.get("host", "localhost")
    port = int(cfg.get("port", 25))
    username = cfg.get("username", "")
    password = cfg.get("password", "")
    use_ssl = bool(cfg.get("use_ssl"))
    use_tls = bool(cfg.get("use_tls"))

    if use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context, timeout=_SMTP_TIMEOUT) as smtp:
            if username:
                smtp.login(username, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=_SMTP_TIMEOUT) as smtp:
            if use_tls:
                context = ssl.create_default_context()
                smtp.starttls(context=context)
            if username:
                smtp.login(username, password)
            smtp.send_message(msg)


class _SmtpCampaignSender:
    """Persistent SMTP session for bulk sends — opens once, reconnects on transient errors."""

    def __init__(self, cfg: dict) -> None:
        self._cfg = cfg
        self._smtp: smtplib.SMTP | smtplib.SMTP_SSL | None = None

    def _connect(self) -> None:
        host     = self._cfg.get("host", "localhost")
        port     = int(self._cfg.get("port", 25))
        username = self._cfg.get("username", "")
        password = self._cfg.get("password", "")
        use_ssl  = bool(self._cfg.get("use_ssl"))
        use_tls  = bool(self._cfg.get("use_tls"))

        if use_ssl:
            ctx = ssl.create_default_context()
            self._smtp = smtplib.SMTP_SSL(host, port, context=ctx, timeout=_SMTP_TIMEOUT)
        else:
            self._smtp = smtplib.SMTP(host, port, timeout=_SMTP_TIMEOUT)
            if use_tls:
                ctx = ssl.create_default_context()
                self._smtp.starttls(context=ctx)
        if username:
            self._smtp.login(username, password)

    def send(self, msg) -> None:
        """Send a message, reconnecting once if the TCP connection was dropped."""
        if self._smtp is None:
            self._connect()
        try:
            self._smtp.send_message(msg)
        except (smtplib.SMTPServerDisconnected, ConnectionResetError, ConnectionAbortedError):
            # TCP connection dropped — reconnect once then retry
            # (Do NOT reconnect on SMTPRecipientsRefused or other protocol errors)
            self._smtp = None
            self._connect()
            self._smtp.send_message(msg)

    def close(self) -> None:
        if self._smtp is not None:
            try:
                self._smtp.quit()
            except Exception:
                pass
            self._smtp = None


def _smtp_test(cfg: dict) -> None:
    """Synchronous connection test — runs inside asyncio.to_thread()."""
    host = cfg.get("host", "localhost")
    port = int(cfg.get("port", 25))
    username = cfg.get("username", "")
    password = cfg.get("password", "")
    use_ssl = bool(cfg.get("use_ssl"))
    use_tls = bool(cfg.get("use_tls"))

    if use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context, timeout=_SMTP_TIMEOUT) as smtp:
            if username:
                smtp.login(username, password)
    else:
        with smtplib.SMTP(host, port, timeout=_SMTP_TIMEOUT) as smtp:
            if use_tls:
                context = ssl.create_default_context()
                smtp.starttls(context=context)
            if username:
                smtp.login(username, password)


async def test_smtp(cfg: dict) -> tuple[bool, str]:
    try:
        await asyncio.to_thread(_smtp_test, cfg)
        logger.info("smtp.test_ok", host=cfg.get("host"))
        return True, "Connection successful!"
    except Exception as e:
        logger.warning("smtp.test_failed", host=cfg.get("host"), error=str(e))
        return False, _friendly_error(e)


# ── Public send API ───────────────────────────────────────────────────────────

async def send_one(cfg: dict, to_email: str, to_name: str,
                   subject: str, html_body: str,
                   attachments: list | None = None,
                   skip_signature: bool = False) -> None:
    """attachments: list of (filename, bytes, mime_type) or None.
    skip_signature: set True for internal/admin emails that don't need a company signature."""
    from_name  = cfg.get("from_name", "")
    from_email = cfg.get("from_email", "") or cfg.get("username", "noreply@localhost")

    if not skip_signature:
        try:
            html_body, ticket_id = sign_email(html_body)
            email_repo.create_email(ticket_id, to_name or to_email, to_email,
                                    html_body, subject=subject)
        except Exception:
            pass  # Signature file missing or DB error — send without storing

    if attachments:
        msg = MIMEMultipart("mixed")
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(alt)
        for fname, data, mime_type in attachments:
            maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
            part = MIMEBase(maintype, subtype)
            part.set_payload(data)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=fname)
            msg.attach(part)
    else:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    msg["From"]    = f"{from_name} <{from_email}>" if from_name else from_email
    msg["To"]      = f"{to_name} <{to_email}>" if to_name else to_email
    msg["Subject"] = subject

    await asyncio.to_thread(_smtp_send, cfg, msg)


# ── Bulk send (background task) ───────────────────────────────────────────────

async def _run_campaign_core(
    campaign_id: int,
    rows: list[dict],
    template_html: str,
    base_url: str,
    email_column: str,
    mapping: dict,
    name_column: str = "",
    subject: str = "Notification from TradingBonusHub",
    from_leads: bool = False,
) -> None:
    """Core campaign send logic — shared by run_campaign() and execute_campaign_job()."""
    logger.info("campaign.started", campaign_id=campaign_id, total=len(rows))
    campaign_repo.update_campaign_status(
        campaign_id, "sending", total=len(rows), sent=0, failed=0
    )
    cfg = get_smtp_config()
    from_name  = cfg.get("from_name", "")
    from_email = cfg.get("from_email", "") or cfg.get("username", "noreply@localhost")

    # Open one persistent SMTP session for the entire campaign (avoids TLS handshake per email)
    sender = _SmtpCampaignSender(cfg)
    _crashed = False
    try:
        for row in rows:
            current = campaign_repo.get_campaign(campaign_id)
            if current and current["status"] == "stopping":
                campaign_repo.update_campaign_status(campaign_id, "stopped")
                logger.info("campaign.stopped", campaign_id=campaign_id)
                return

            to_email = row.get(email_column, "").strip()
            if not to_email:
                # Skip rows with no email — don't count as failure
                continue

            to_name = row.get(name_column, "") if name_column else ""
            tracking_id = str(uuid.uuid4())

            rendered = render_dynamic(template_html, row, mapping)
            rendered, _ = sign_email(rendered, tracking_id)
            rendered = inject_click_links(rendered, tracking_id, base_url)
            html_with_pixel = inject_pixel(rendered, tracking_id, base_url)

            # Extract order_id/amount from mapping (best-effort heuristic)
            order_id = ""
            amount = ""
            for ph, col in mapping.items():
                ph_clean = ph.lower()
                if not order_id and any(k in ph_clean for k in
                                        ["đơn", "order", "mã", " id", "_id", "id_", "code"]):
                    order_id = str(row.get(col, ""))
                if not amount and any(k in ph_clean for k in
                                      ["tiền", "tien", "amount", "giá", "gia", "hoa hồng", "commission"]):
                    amount = str(row.get(col, ""))
            vals = list(mapping.values())
            if not order_id and len(vals) > 0:
                order_id = str(row.get(vals[0], ""))
            if not amount and len(vals) > 1:
                amount = str(row.get(vals[1], ""))

            # Build MIME message and send via persistent session
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(html_with_pixel, "html", "utf-8"))
            msg["From"]    = f"{from_name} <{from_email}>" if from_name else from_email
            msg["To"]      = f"{to_name} <{to_email}>" if to_name else to_email
            msg["Subject"] = subject

            lead_id = row.get("__lead_id__") if from_leads else None

            try:
                await asyncio.to_thread(sender.send, msg)
                # Only persist email record after successful SMTP send to avoid
                # duplicate sends if the task is retried after a partial failure.
                email_repo.create_email(
                    tracking_id,
                    to_name or to_email,
                    to_email,
                    html_with_pixel,
                    campaign_id=campaign_id,
                    subject=subject,
                )
                campaign_repo.increment_campaign_sent(campaign_id)
                if lead_id:
                    lead_repo.set_lead_campaign_status(lead_id, campaign_id, "sent")
                logger.debug("campaign.email_sent", campaign_id=campaign_id, to=to_email)
            except Exception as exc:
                logger.error("campaign.email_failed", campaign_id=campaign_id,
                             to=to_email, error=str(exc), exc_info=True)
                campaign_repo.increment_campaign_failed(campaign_id)
                if lead_id:
                    lead_repo.set_lead_campaign_status(
                        lead_id, campaign_id, "failed", str(exc)[:500]
                    )

            await asyncio.sleep(0.1)
    except Exception as exc:
        # Unhandled exception in the main loop (e.g. DB error, template error)
        # Mark campaign as failed so it doesn't stay stuck in "sending" forever
        _crashed = True
        logger.error("campaign.crashed", campaign_id=campaign_id, error=str(exc), exc_info=True)
        campaign_repo.update_campaign_status(campaign_id, "failed")
    finally:
        await asyncio.to_thread(sender.close)

    if _crashed:
        return

    camp = campaign_repo.get_campaign(campaign_id)
    # If campaign was externally stopped/cancelled, don't override that status
    if camp and camp["status"] in ("stopped", "stopping"):
        return
    final = "done" if (camp and camp["failed"] == 0) else "done_with_errors"
    campaign_repo.update_campaign_status(campaign_id, final)
    logger.info("campaign.finished", campaign_id=campaign_id, status=final)


async def run_campaign(
    campaign_id: int,
    rows: list[dict],
    template_html: str,
    base_url: str,
    email_column: str,
    mapping: dict,
    name_column: str = "",
    subject: str = "Notification from TradingBonusHub",
    from_leads: bool = False,
) -> None:
    """Legacy direct-call wrapper — kept for backward compatibility."""
    await _run_campaign_core(
        campaign_id, rows, template_html, base_url,
        email_column, mapping, name_column, subject, from_leads,
    )


async def execute_campaign_job(payload: dict) -> None:
    """Entry point called by job_worker — deserialises payload from job_queue."""
    from app.db.repositories.templates import get_template
    tmpl = get_template(payload["template_id"])
    if not tmpl:
        raise ValueError(f"Template {payload['template_id']} not found")
    await _run_campaign_core(
        campaign_id=payload["campaign_id"],
        rows=payload["rows"],
        template_html=tmpl["html_content"],
        base_url=payload["base_url"],
        email_column=payload["email_column"],
        mapping=payload["mapping"],
        name_column=payload.get("name_column", ""),
        subject=payload.get("subject", "Notification from TradingBonusHub"),
        from_leads=payload.get("from_leads", False),
    )
