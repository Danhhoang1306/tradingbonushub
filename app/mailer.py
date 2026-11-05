"""Gửi email. SMTP_BACKEND=console chỉ ghi log (dùng khi dev/test), smtp thì gửi thật."""
import logging
import smtplib
import ssl
import threading
from contextlib import contextmanager
from email.message import EmailMessage

from app.config import config

log = logging.getLogger("app.mailer")

# Bộ nhớ email đã "gửi" ở chế độ console, để test kiểm tra.
outbox: list[EmailMessage] = []
_local = threading.local()


def can_deliver() -> bool:
    """Production với backend console: email chỉ vào log, không tới được người nhận."""
    return not (config.is_production and config.smtp_backend == "console")


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


@contextmanager
def shared_connection():
    """Các lần send_many trong khối này dùng chung một kết nối SMTP (gửi chiến dịch theo lô, không đăng nhập lại mỗi lô)."""
    server = None
    if config.smtp_backend == "smtp":
        try:
            server = _connect()
        except (OSError, smtplib.SMTPException):
            log.exception("Không mở được kết nối SMTP")
    _local.server = server
    try:
        yield
    finally:
        _local.server = None
        if server is not None:
            try:
                server.quit()
            except (OSError, smtplib.SMTPException):
                pass


def _send_all(server, messages: list[EmailMessage]) -> int:
    sent = 0
    for msg in messages:
        try:
            server.send_message(msg)
            msg.delivered = True
            sent += 1
        except smtplib.SMTPRecipientsRefused:
            log.warning("SMTP từ chối người nhận %s", msg["To"])
    return sent


def send_many(messages: list[EmailMessage]) -> int:
    """Gửi cả lô qua một kết nối SMTP. Trả về số email gửi thành công; email đã gửi có `msg.delivered = True`."""
    if config.smtp_backend != "smtp":
        for msg in messages:
            outbox.append(msg)
            msg.delivered = True
            log.info("[console email] to=%s subject=%s\n%s", msg["To"], msg["Subject"], msg.get_content())
        return len(messages)
    try:
        shared = getattr(_local, "server", None)
        if shared is not None:
            return _send_all(shared, messages)
        with _connect() as server:
            return _send_all(server, messages)
    except (OSError, smtplib.SMTPException):
        log.exception("SMTP gửi thất bại, lô %s email", len(messages))
    return sum(1 for m in messages if getattr(m, "delivered", False))


def send_email(to: str, subject: str, text: str, unsubscribe_url: str | None = None) -> bool:
    return send_many([build(to, subject, text, unsubscribe_url)]) == 1
