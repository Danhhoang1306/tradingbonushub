"""Email notification helpers (background tasks)."""
from datetime import datetime

import structlog

from app.db.repositories.portal_settings import get_portal_settings
from app.db.repositories.smtp import get_smtp_config, get_google_oauth_config
from app.services.mailer import send_one

logger = structlog.get_logger(__name__)


def _site_url() -> str:
    """Return configured site URL (from Google OAuth config) with fallback."""
    cfg = get_google_oauth_config()
    return (cfg.get("site_url") or "https://tradingbonushub.com").rstrip("/")


async def notify_new_registration(name: str, email: str) -> None:
    """Notify support when a new customer registers."""
    cfg = get_smtp_config()
    if not cfg.get("host") or cfg.get("host") == "localhost":
        return
    ps = get_portal_settings()
    support_email = ps.get("support_email") or "support@tradingbonushub.com"
    html = (
        f"<p>A new customer has registered on the portal.</p>"
        f"<ul>"
        f"<li><b>Name:</b> {name}</li>"
        f"<li><b>Email:</b> {email}</li>"
        f"<li><b>Time:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</li>"
        f"</ul>"
        f'<p><a href="{_site_url()}/admin/customers">View customer list</a></p>'
    )
    try:
        await send_one(cfg, support_email, "", f"[New Registration] {name} — {email}", html, skip_signature=True)
    except Exception as e:
        logger.error("notify.registration_failed", email=email, error=str(e))


async def send_verification_email(cfg: dict, customer_email: str, verify_link: str) -> None:
    """Send email verification link to newly registered customer."""
    if not cfg.get("host") or cfg.get("host") == "localhost":
        return
    ps = get_portal_settings()
    site_name = ps.get("site_name", "TradingBonusHub")
    html = (
        f"<p>Hello,</p>"
        f"<p>Thank you for registering an account at <strong>{site_name}</strong>.</p>"
        f"<p>Please click the link below to verify your email address and activate your account:</p>"
        f'<p><a href="{verify_link}" style="background:#c8972a;color:#fff;padding:10px 20px;'
        f'text-decoration:none;border-radius:4px;">Verify Email</a></p>'
        f"<p>Or copy this link: {verify_link}</p>"
        f"<p>This link does not expire. "
        f"If you did not register this account, please ignore this email.</p>"
        f"<p>Best regards,<br>{site_name}</p>"
    )
    try:
        await send_one(cfg, customer_email, "", f"[{site_name}] Email Verification", html)
        logger.info("notify.verification_sent", email=customer_email)
    except Exception as e:
        logger.error("notify.verification_failed", email=customer_email, error=str(e))


async def send_reset_email(cfg: dict, customer_email: str, link: str) -> None:
    """Send password-reset link without blocking the response."""
    html = (
        f"<p>You have requested a password reset.</p>"
        f'<p><a href="{link}">Click here to reset your password</a></p>'
        f"<p>This link is valid for <strong>1 hour</strong>. "
        f"If you did not request this, please ignore this email.</p>"
    )
    try:
        await send_one(cfg, customer_email, "", "Password Reset", html)
    except Exception as e:
        logger.error("notify.reset_failed", email=customer_email, error=str(e))


async def send_customer_welcome_email(cfg: dict, email: str,
                                      temp_pw: str, portal_url: str) -> None:
    """Send welcome email with temporary password to a newly created customer."""
    html = f"""
<p>Hello,</p>
<p>We would like to inform you that the partner transfer process for your account has been completed successfully.</p>
<p>You can now check your commission rebate history at the link below:<br>
<a href="{portal_url}">{portal_url}</a></p>
<p><strong>Login credentials:</strong><br>
Username: <strong>{email}</strong><br>
Password: <strong>{temp_pw}</strong></p>
<p>For security reasons, please change your password after your first login.</p>
<p>If you need further assistance or have any questions about your account, please reply to this email for support.</p>
<p>Best regards,</p>"""
    try:
        await send_one(cfg, email, "", "Account Activation Notification", html)
        logger.info("notify.welcome_sent", email=email)
    except Exception as e:
        logger.error("notify.welcome_failed", email=email, error=str(e))


async def send_enrollment_notification(
    customer_email: str, promo_name: str, mt5_account: str
) -> None:
    """Notify admin by email when a new enrollment arrives."""
    cfg = get_smtp_config()
    if not cfg.get("host") or cfg.get("host") == "localhost":
        return
    ps = get_portal_settings()
    admin_email = ps.get("support_email") or cfg.get("username") or cfg.get("from_email", "")
    if not admin_email:
        return
    mt5_line = f"<p>MT5 Account: <b>{mt5_account}</b></p>" if mt5_account else ""
    html = (
        f"<p>Customer <b>{customer_email}</b> has enrolled in program "
        f"<b>{promo_name}</b>.</p>"
        f"{mt5_line}"
        f"<p>Time: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>"
        f'<p><a href="{_site_url()}/admin/enrollments">Review and approve here</a></p>'
    )
    try:
        await send_one(
            cfg, admin_email, "",
            f"[Enrollment] {customer_email} enrolled in {promo_name}", html,
            skip_signature=True,
        )
    except Exception as e:
        logger.error("notify.enrollment_admin_failed", error=str(e))


async def send_enrollment_result_email(
    customer_email: str, promo_name: str, status: str, note: str
) -> None:
    """Notify customer when their enrollment is approved or rejected."""
    cfg = get_smtp_config()
    if not cfg.get("host") or cfg.get("host") == "localhost":
        return
    if status == "active":
        subject = f"[TradingBonusHub] {promo_name} enrollment approved"
        html = (
            f"<p>Congratulations! Your enrollment in <b>{promo_name}</b> has been approved.</p>"
            f"<p>You can track your trading history and rebates at "
            f'<a href="{_site_url()}/portal/">your personal portal</a>.</p>'
        )
    else:
        subject = f"[TradingBonusHub] {promo_name} enrollment not approved"
        html = (
            f"<p>Your enrollment in <b>{promo_name}</b> has not been approved.</p>"
            f"<p><b>Reason:</b> {note or 'No notes provided.'}</p>"
            f'<p>You can enroll in another program at '
            f'<a href="{_site_url()}/portal/promotions">here</a>.</p>'
        )
    try:
        await send_one(cfg, customer_email, "", subject, html)
    except Exception as e:
        logger.error("notify.enrollment_result_failed",
                     email=customer_email, status=status, error=str(e))


async def send_broker_email_verify(
    broker_email: str,
    customer_name: str,
    broker_name: str,
    verify_url: str,
) -> None:
    """Send verification email to broker_email so customer can prove ownership."""
    cfg = get_smtp_config()
    if not cfg.get("host") or cfg.get("host") == "localhost":
        return
    ps = get_portal_settings()
    site_name = ps.get("site_name") or "TradingBonusHub"
    html = (
        f"<p>Hello,</p>"
        f"<p>We received a request to link the email address <b>{broker_email}</b> "
        f"({broker_name} account) with the portal account <b>{customer_name}</b> "
        f"on {site_name}.</p>"
        f"<p>Click the button below to confirm you own this email:</p>"
        f'<p><a href="{verify_url}" style="display:inline-block;padding:12px 24px;'
        f'background:#c8972a;color:#fff;border-radius:6px;text-decoration:none;font-weight:700;">'
        f'Confirm Account Link</a></p>'
        f"<p>Or copy this link: {verify_url}</p>"
        f"<p>If you did not make this request, please ignore this email.</p>"
        f"<hr/><p style='color:#888;font-size:12px;'>{site_name}</p>"
    )
    try:
        await send_one(cfg, broker_email, "", f"[{site_name}] Confirm Broker Account Link", html, skip_signature=True)
        logger.info("notify.broker_verify_sent", to=broker_email)
    except Exception as e:
        logger.error("notify.broker_verify_failed", to=broker_email, error=str(e))


async def notify_broker_email_linked(
    customer_email: str, broker_email: str, broker_name: str,
) -> None:
    """Notify admin when a customer links their broker email."""
    cfg = get_smtp_config()
    if not cfg.get("host") or cfg.get("host") == "localhost":
        return
    ps = get_portal_settings()
    admin_email = ps.get("support_email") or cfg.get("username") or cfg.get("from_email", "")
    if not admin_email:
        return
    html = (
        f"<p>Customer <b>{customer_email}</b> has linked a broker email.</p>"
        f"<ul>"
        f"<li><b>Broker:</b> {broker_name}</li>"
        f"<li><b>Broker Email:</b> {broker_email}</li>"
        f"<li><b>Time:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</li>"
        f"</ul>"
        f'<p><a href="{_site_url()}/admin/customers">View customer list</a></p>'
    )
    try:
        await send_one(
            cfg, admin_email, "",
            f"[Email Linked] {customer_email} — {broker_name}", html,
            skip_signature=True,
        )
    except Exception as e:
        logger.error("notify.broker_link_admin_failed", error=str(e))


async def send_withdrawal_otp(customer_email: str, code: str) -> None:
    """Send 6-digit OTP code for withdrawal verification."""
    cfg = get_smtp_config()
    if not cfg.get("host") or cfg.get("host") == "localhost":
        return
    ps = get_portal_settings()
    site_name = ps.get("site_name") or "TradingBonusHub"
    html = (
        f"<p>Hello,</p>"
        f"<p>You are requesting a withdrawal from your {site_name} wallet.</p>"
        f"<p>Your verification code:</p>"
        f'<div style="text-align:center;margin:24px 0;">'
        f'<span style="font-size:32px;font-weight:800;letter-spacing:8px;'
        f'background:#f5f5f5;padding:16px 32px;border-radius:8px;color:#333;">'
        f'{code}</span></div>'
        f"<p>This code is valid for <strong>5 minutes</strong>. "
        f"Do not share this code with anyone.</p>"
        f"<p>If you did not make this request, "
        f"please change your password immediately and contact support.</p>"
        f"<p>Best regards,<br>{site_name}</p>"
    )
    try:
        await send_one(cfg, customer_email, "", f"[{site_name}] Withdrawal Verification Code: {code}", html)
        logger.info("notify.withdrawal_otp_sent", email=customer_email)
    except Exception as e:
        logger.error("notify.withdrawal_otp_failed", email=customer_email, error=str(e))


async def send_vantage_email_change_confirm(
    customer_email: str,
    new_vantage_email: str,
    token: str,
) -> None:
    """Send confirmation email to the NEW Vantage email for change verification."""
    cfg = get_smtp_config()
    if not cfg.get("host"):
        return
    ps = get_portal_settings()
    site_name = ps.get("site_name") or "TradingBonusHub"
    confirm_url = f"{_site_url()}/portal/confirm-vantage-email?token={token}"
    subject = f"[{site_name}] Confirm Vantage Email Change"
    html = (
        f"<p>Hello,</p>"
        f"<p>We received a request to link the email address <b>{new_vantage_email}</b> "
        f"with the account <b>{customer_email}</b> on {site_name}.</p>"
        f"<p>Click the button below to confirm the change. This link is valid for <b>24 hours</b>.</p>"
        f'<p><a href="{confirm_url}" style="display:inline-block;padding:12px 24px;'
        f'background:#c8972a;color:#fff;border-radius:6px;text-decoration:none;font-weight:700;">'
        f'Confirm Email Change</a></p>'
        f"<p>If you did not make this request, please ignore this email.</p>"
        f"<hr/><p style='color:#888;font-size:12px;'>{site_name}</p>"
    )
    try:
        await send_one(cfg, new_vantage_email, "", subject, html)
    except Exception as e:
        logger.error("notify.vantage_email_change_failed",
                     to=new_vantage_email, error=str(e))
