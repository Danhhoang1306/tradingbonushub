"""Gmail OAuth 2.0 sender — uses Gmail API to send email from the user's account."""
import asyncio
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.db.repositories.portal_settings import get_portal_settings

logger = structlog.get_logger(__name__)

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

TRANSFER_SUBJECT = "Change account owner"
TRANSFER_SUPPORT_EMAIL = "danhhoangsmk@gmail.com"  # fallback (dev)

# Per-broker transfer email config: to, subject, body builder
BROKER_TRANSFER_CONFIG: dict = {
    "vantage": {
        "to": "vietnam.support@vantagemarkets.com",
        "subject": "Change account owner",
        "build_body": lambda ib: (
            f"Hi team,\n\nPlease transfer my account to under IB {ib}\n\nThank you.",
            f"<p>Hi team,</p><p>Please transfer my account to under IB <strong>{ib}</strong></p><p>Thank you.</p>",
        ),
    },
    "ultima": {
        "to": "vietnam.cs@ultimamarkets.com",
        "subject": "Change account owner",
        "build_body": lambda ib: (
            f"Dear team,\n\nPlease transfer me to under {ib}.\n\nThank you.",
            f"<p>Dear team,</p><p>Please transfer me to under <strong>{ib}</strong>.</p><p>Thank you.</p>",
        ),
    },
    "dupoin": {
        "to": "support@dupoin.com",
        "subject": "Change account owner",
        "build_body": lambda ib: (
            f"Hi Support,\n\nPlease transfer my account to under IB {ib}.\n\nThank you.",
            f"<p>Hi Support,</p><p>Please transfer my account to under IB <strong>{ib}</strong>.</p><p>Thank you.</p>",
        ),
    },
}


def _build_transfer_body(ib_number: str, broker_slug: str = "vantage") -> tuple:
    cfg = BROKER_TRANSFER_CONFIG.get(broker_slug) or BROKER_TRANSFER_CONFIG["vantage"]
    return cfg["build_body"](ib_number)


def make_flow(client_id: str, client_secret: str, redirect_uri: str) -> Flow:
    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=GMAIL_SCOPES)
    flow.redirect_uri = redirect_uri
    return flow


def _get_google_email_sync(creds: Credentials) -> str:
    service = build("oauth2", "v2", credentials=creds)
    info = service.userinfo().get().execute()
    return info.get("email", "")


def _send_gmail_sync(
    refresh_token: str,
    client_id: str,
    client_secret: str,
    from_email: str,
    to: str,
    subject: str,
    body_plain: str,
    body_html: str,
) -> None:
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=GMAIL_SCOPES,
    )
    creds.refresh(GoogleRequest())

    service = build("gmail", "v1", credentials=creds)

    msg = MIMEMultipart("alternative")
    msg["From"] = from_email
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body_plain, "plain", "utf-8"))
    msg.attach(MIMEText(body_html,  "html",  "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


async def send_transfer_email(
    refresh_token: str, client_id: str, client_secret: str, from_email: str,
    ib_number: str = "",
    broker_slug: str = "vantage",
) -> None:
    """Async wrapper — send IB transfer email from the customer's Gmail account.

    Broker-specific To/Subject/Body are looked up from BROKER_TRANSFER_CONFIG.
    Falls back to vantage config if broker_slug is unknown.
    """
    # Use provided ib_number; fallback to portal_settings for backward compat
    if not ib_number:
        ps = get_portal_settings()
        ib_number = ps.get("transfer_ib_number") or ""

    cfg = BROKER_TRANSFER_CONFIG.get(broker_slug) or BROKER_TRANSFER_CONFIG["vantage"]
    to      = cfg["to"]
    subject = cfg["subject"]
    body_plain, body_html = cfg["build_body"](ib_number)

    logger.info("gmail.transfer_sending", from_email=from_email,
                to=to, ib_number=ib_number, broker=broker_slug)
    await asyncio.to_thread(
        _send_gmail_sync,
        refresh_token,
        client_id,
        client_secret,
        from_email,
        to,
        subject,
        body_plain,
        body_html,
    )
