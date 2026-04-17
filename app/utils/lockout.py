"""Account lockout helper — 3 failed attempts within 30 minutes blocks for 30 minutes."""
from app.db.connection import get_conn

_MAX_ATTEMPTS = 3
_WINDOW_MINUTES = 30


def check_lockout(identifier: str, user_type: str) -> tuple[bool, int]:
    """Return (is_locked, minutes_remaining).

    Counts failed login attempts for *identifier* within the last WINDOW_MINUTES.
    If >= MAX_ATTEMPTS, the account is locked until the oldest attempt expires.
    """
    with get_conn() as conn:
        row = conn.execute("""
            SELECT COUNT(*) AS cnt,
                   MIN(attempted_at) AS oldest
            FROM login_attempts
            WHERE identifier = ?
              AND user_type  = ?
              AND attempted_at >= DATEADD(MINUTE, ?, GETUTCDATE())
        """, (identifier, user_type, -_WINDOW_MINUTES)).fetchone()

        if not row or row["cnt"] < _MAX_ATTEMPTS:
            return False, 0

        # Calculate remaining lock time from the oldest attempt in the window
        if row["oldest"]:
            from datetime import datetime, timezone, timedelta
            oldest = row["oldest"]
            if hasattr(oldest, "tzinfo") and oldest.tzinfo is None:
                oldest = oldest.replace(tzinfo=timezone.utc)
            unlock_at = oldest + timedelta(minutes=_WINDOW_MINUTES)
            now = datetime.now(timezone.utc)
            remaining = max(0, int((unlock_at - now).total_seconds() / 60) + 1)
            if remaining > 0:
                return True, remaining

    return False, 0


def record_attempt(identifier: str, user_type: str, ip: str = "") -> None:
    """Record a failed login attempt."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO login_attempts (identifier, user_type, ip_address) VALUES (?, ?, ?)",
            (identifier, user_type, ip or None),
        )


def clear_attempts(identifier: str, user_type: str) -> None:
    """Clear all failed attempts after a successful login."""
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM login_attempts WHERE identifier=? AND user_type=?",
            (identifier, user_type),
        )
