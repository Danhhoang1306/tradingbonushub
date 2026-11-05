"""Gửi email. SMTP_BACKEND=console chỉ ghi log (dùng khi dev/test), smtp thì gửi thật."""
import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.config import config

log = logging.getLogger("app.mailer")

# Bộ nhớ email đã "gửi" ở chế độ console, để test kiểm tra.
outbox: list[EmailMessage] = []


def build(to: str, subject: str, text: str, unsubscribe_url: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = config.from_email or "no-reply@localhost"
    msg["To"] = to
    msg["Subject"] = subject
    if unsubscribe_url:
        msg["List-Unsubscribe"] = f"<{unsubscribe_url}>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
        text = f"{text}\n\n---\nHủy nhận email: {unsubscribe_url}"
    msg.set_content(text)
    return msg


def _connect() -> smtplib.SMTP:
    if config.smtp_port == 465:
        server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=20, context=ssl.create_default_context())
    else:
        server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=20)
        server.starttls(context=ssl.create_default_context())
    if config.smtp_user:
        server.login(config.smtp_user, config.smtp_pass)
    return server


def send_many(messages: list[EmailMessage]) -> int:
    """Gửi cả lô qua một kết nối SMTP. Trả về số email gửi thành công; email đã gửi có `msg.delivered = True`."""
    if config.smtp_backend != "smtp":
        for msg in messages:
            outbox.append(msg)
            msg.delivered = True
            log.info("[console email] to=%s subject=%s\n%s", msg["To"], msg["Subject"], msg.get_content())
        return len(messages)
    sent = 0
    try:
        with _connect() as server:
            for msg in messages:
                try:
                    server.send_message(msg)
                    msg.delivered = True
                    sent += 1
                except smtplib.SMTPRecipientsRefused:
                    log.warning("SMTP từ chối người nhận %s", msg["To"])
    except (OSError, smtplib.SMTPException):
        log.exception("SMTP gửi thất bại sau %s/%s email", sent, len(messages))
    return sent


def send_email(to: str, subject: str, text: str, unsubscribe_url: str | None = None) -> bool:
    return send_many([build(to, subject, text, unsubscribe_url)]) == 1
