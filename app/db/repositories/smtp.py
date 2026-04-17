"""SMTP config and Google OAuth token storage — secrets encrypted at rest."""
from app.db.connection import get_conn
from app.utils.crypto import decrypt_secret, encrypt_secret


# ── SMTP config ───────────────────────────────────────────────────────────────

def get_smtp_config() -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM smtp_config WHERE id = 1").fetchone()
        if not row:
            return {}
        cfg = dict(row)
        cfg["password"] = decrypt_secret(cfg.get("password", ""))
        return cfg


def save_smtp_config(host, port, username, password,
                     from_email, from_name, use_tls, use_ssl):
    with get_conn() as conn:
        conn.execute("""
            UPDATE smtp_config SET
                host=?, port=?, username=?, password=?,
                from_email=?, from_name=?, use_tls=?, use_ssl=?
            WHERE id = 1
        """, (host, port, username, encrypt_secret(password),
              from_email, from_name, int(use_tls), int(use_ssl)))


# ── Google OAuth ──────────────────────────────────────────────────────────────

def get_google_oauth_config() -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM google_oauth_config WHERE id=1").fetchone()
        if not row:
            return {"client_id": "", "client_secret": "", "site_url": ""}
        cfg = dict(row)
        cfg["client_secret"] = decrypt_secret(cfg.get("client_secret", ""))
        return cfg


def save_google_oauth_config(client_id: str, client_secret: str, site_url: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE google_oauth_config SET client_id=?, client_secret=?, site_url=? WHERE id=1",
            (client_id, encrypt_secret(client_secret), site_url.rstrip("/")),
        )


def get_gmail_token(google_email: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM gmail_send_tokens WHERE google_email=?", (google_email,)
        ).fetchone()
        if not row:
            return None
        token = dict(row)
        token["refresh_token"] = decrypt_secret(token.get("refresh_token", ""))
        return token


def save_gmail_token(google_email: str, refresh_token: str):
    with get_conn() as conn:
        conn.execute("""
            MERGE gmail_send_tokens AS t
            USING (VALUES (?, ?)) AS s(google_email, refresh_token)
            ON t.google_email = s.google_email
            WHEN MATCHED THEN
                UPDATE SET refresh_token=s.refresh_token, last_used=GETDATE()
            WHEN NOT MATCHED THEN
                INSERT (google_email, refresh_token, last_used)
                VALUES (s.google_email, s.refresh_token, GETDATE());
        """, (google_email, encrypt_secret(refresh_token)))
