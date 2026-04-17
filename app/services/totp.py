"""TOTP (Time-based One-Time Password) service for admin MFA."""
import io
import base64

import pyotp
import qrcode

from app.db.connection import get_conn

APP_NAME = "TradingBonusHub Admin"


def generate_secret() -> str:
    """Generate a new random TOTP secret."""
    return pyotp.random_base32()


def get_provisioning_uri(secret: str, username: str) -> str:
    """Return the otpauth:// URI for QR code generation."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name=APP_NAME)


def generate_qr_base64(secret: str, username: str) -> str:
    """Generate a QR code image as a base64-encoded PNG string."""
    uri = get_provisioning_uri(secret, username)
    img = qrcode.make(uri, box_size=6, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def verify_code(secret: str, code: str) -> bool:
    """Verify a TOTP code against a secret (allows 1 window of drift)."""
    if not secret or not code:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def save_totp_secret(username: str, secret: str) -> None:
    """Save the TOTP secret for a user."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET totp_secret=? WHERE username=?",
            (secret, username),
        )


def get_totp_secret(username: str) -> str | None:
    """Get the TOTP secret for a user. Returns None if not set."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT totp_secret FROM users WHERE username=?",
            (username,),
        ).fetchone()
        return row["totp_secret"] if row else None


def disable_totp(username: str) -> None:
    """Remove TOTP for a user (admin action)."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET totp_secret=NULL WHERE username=?",
            (username,),
        )
