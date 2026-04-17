"""One-time migration: encrypt existing plaintext secrets in the DB.

Run ONCE immediately after deploying the crypto.py changes and BEFORE
restarting the app. Safe to run multiple times — decrypt_secret() detects
already-encrypted values via Fernet token format and skips them.

Usage:
    cd f:/Tradingbonushub
    python scripts/encrypt_existing_secrets.py
"""
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.db.connection import get_conn
from app.utils.crypto import encrypt_secret, decrypt_secret


def _is_fernet_token(s: str) -> bool:
    """Fernet tokens are base64url-encoded and start with 'gAAAAA'."""
    return isinstance(s, str) and s.startswith("gAAAAA")


def migrate():
    print("Starting one-time secret encryption migration...")

    with get_conn() as conn:
        # ── smtp_config.password ──────────────────────────────────────────────
        row = conn.execute("SELECT password FROM smtp_config WHERE id=1").fetchone()
        if row:
            pw = row["password"] or ""
            if pw and not _is_fernet_token(pw):
                conn.execute(
                    "UPDATE smtp_config SET password=? WHERE id=1",
                    (encrypt_secret(pw),)
                )
                print(f"  [OK] smtp_config.password encrypted")
            else:
                print(f"  [SKIP] smtp_config.password already encrypted or empty")

        # ── google_oauth_config.client_secret ─────────────────────────────────
        row = conn.execute("SELECT client_secret FROM google_oauth_config WHERE id=1").fetchone()
        if row:
            secret = row["client_secret"] or ""
            if secret and not _is_fernet_token(secret):
                conn.execute(
                    "UPDATE google_oauth_config SET client_secret=? WHERE id=1",
                    (encrypt_secret(secret),)
                )
                print(f"  [OK] google_oauth_config.client_secret encrypted")
            else:
                print(f"  [SKIP] google_oauth_config.client_secret already encrypted or empty")

        # ── gmail_send_tokens.refresh_token ───────────────────────────────────
        rows = conn.execute("SELECT google_email, refresh_token FROM gmail_send_tokens").fetchall()
        for row in rows:
            token = row["refresh_token"] or ""
            if token and not _is_fernet_token(token):
                conn.execute(
                    "UPDATE gmail_send_tokens SET refresh_token=? WHERE google_email=?",
                    (encrypt_secret(token), row["google_email"])
                )
                print(f"  [OK] gmail_send_tokens.refresh_token encrypted for {row['google_email']}")
            else:
                print(f"  [SKIP] {row['google_email']} already encrypted or empty")

    print("\nMigration complete. You may delete this script.")


if __name__ == "__main__":
    migrate()
