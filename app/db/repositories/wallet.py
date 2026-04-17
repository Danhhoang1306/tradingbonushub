"""Wallet CRUD — SQL Server.

Tables:
  customer_wallets       — one wallet per customer (balance + pending_balance)
  wallet_transactions    — ledger of all credits/debits
  withdrawal_requests    — customer withdrawal requests (bank/crypto)
"""
from app.db.connection import get_conn


# ── Wallet ────────────────────────────────────────────────────────────────────

def get_or_create_wallet(customer_id: int) -> dict:
    """Return the wallet for a customer, creating one if it doesn't exist."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM customer_wallets WHERE customer_id=?",
            (customer_id,),
        ).fetchone()
        if row:
            return dict(row)
        conn.execute(
            "INSERT INTO customer_wallets (customer_id) VALUES (?)",
            (customer_id,),
        )
        row = conn.execute(
            "SELECT * FROM customer_wallets WHERE customer_id=?",
            (customer_id,),
        ).fetchone()
        return dict(row)


def get_wallet_by_id(wallet_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM customer_wallets WHERE id=?", (wallet_id,)
        ).fetchone()
        return dict(row) if row else None


def get_wallet_by_customer(customer_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM customer_wallets WHERE customer_id=?",
            (customer_id,),
        ).fetchone()
        return dict(row) if row else None


def update_wallet_balance(wallet_id: int, balance: float, pending_balance: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE customer_wallets SET balance=?, pending_balance=?, updated_at=GETDATE() WHERE id=?",
            (balance, pending_balance, wallet_id),
        )


# ── Transactions ──────────────────────────────────────────────────────────────

def create_transaction(
    wallet_id: int,
    tx_type: str,
    amount: float,
    balance_after: float,
    *,
    reference_type: str | None = None,
    reference_id: int | None = None,
    description: str = "",
    status: str = "completed",
    created_by: str = "",
) -> int:
    with get_conn() as conn:
        row = conn.execute(
            """INSERT INTO wallet_transactions
               (wallet_id, tx_type, amount, balance_after,
                reference_type, reference_id, description, status, created_by)
               OUTPUT INSERTED.id
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (wallet_id, tx_type, amount, balance_after,
             reference_type, reference_id, description, status, created_by),
        ).fetchone()
        return row["id"]


def get_transactions(wallet_id: int, limit: int = 50, offset: int = 0) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM wallet_transactions
               WHERE wallet_id=?
               ORDER BY created_at DESC
               OFFSET ? ROWS FETCH NEXT ? ROWS ONLY""",
            (wallet_id, offset, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_transactions(limit: int = 100, offset: int = 0,
                         tx_type: str | None = None) -> list:
    """Admin: list all transactions across all wallets."""
    with get_conn() as conn:
        sql = """
            SELECT wt.*, cw.customer_id, c.login_email, c.name AS customer_name
            FROM wallet_transactions wt
            JOIN customer_wallets cw ON cw.id = wt.wallet_id
            JOIN customers c ON c.id = cw.customer_id
        """
        params = []
        if tx_type:
            sql += " WHERE wt.tx_type=?"
            params.append(tx_type)
        sql += " ORDER BY wt.created_at DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        params.extend([offset, limit])
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


# ── Withdrawal Requests ───────────────────────────────────────────────────────

def create_withdrawal_request(
    wallet_id: int,
    amount: float,
    method: str = "bank_transfer",
    *,
    wallet_address: str | None = None,
    wallet_network: str | None = None,
    bank_info: str | None = None,
) -> int:
    with get_conn() as conn:
        row = conn.execute(
            """INSERT INTO withdrawal_requests
               (wallet_id, amount, method, wallet_address, wallet_network, bank_info)
               OUTPUT INSERTED.id
               VALUES (?,?,?,?,?,?)""",
            (wallet_id, amount, method, wallet_address, wallet_network, bank_info),
        ).fetchone()
        return row["id"]


def get_withdrawal_request(wr_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT wr.*, cw.customer_id, c.login_email, c.name AS customer_name
               FROM withdrawal_requests wr
               JOIN customer_wallets cw ON cw.id = wr.wallet_id
               JOIN customers c ON c.id = cw.customer_id
               WHERE wr.id=?""",
            (wr_id,),
        ).fetchone()
        return dict(row) if row else None


def get_withdrawal_requests_by_wallet(wallet_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM withdrawal_requests WHERE wallet_id=? ORDER BY created_at DESC",
            (wallet_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_withdrawal_requests(status: str | None = None,
                                 limit: int = 100, offset: int = 0) -> list:
    """Admin: list all withdrawal requests."""
    with get_conn() as conn:
        sql = """
            SELECT wr.*, cw.customer_id, c.login_email, c.name AS customer_name,
                   cw.balance AS wallet_balance
            FROM withdrawal_requests wr
            JOIN customer_wallets cw ON cw.id = wr.wallet_id
            JOIN customers c ON c.id = cw.customer_id
        """
        params = []
        if status:
            sql += " WHERE wr.status=?"
            params.append(status)
        sql += " ORDER BY wr.created_at DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        params.extend([offset, limit])
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def update_withdrawal_status(
    wr_id: int,
    status: str,
    *,
    admin_note: str = "",
    reviewed_by: str = "",
    tx_hash: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """UPDATE withdrawal_requests
               SET status=?, admin_note=?, reviewed_by=?, reviewed_at=GETDATE(), tx_hash=?
               WHERE id=?""",
            (status, admin_note, reviewed_by, tx_hash, wr_id),
        )


# ── Admin summary ─────────────────────────────────────────────────────────────

def get_all_wallets(limit: int = 100, offset: int = 0,
                    search: str | None = None) -> list:
    """Admin: list all wallets with customer info."""
    with get_conn() as conn:
        sql = """
            SELECT cw.*, c.login_email, c.name AS customer_name
            FROM customer_wallets cw
            JOIN customers c ON c.id = cw.customer_id
        """
        params = []
        if search:
            sql += " WHERE c.login_email LIKE ? OR c.name LIKE ?"
            params.extend([f"%{search}%", f"%{search}%"])
        sql += " ORDER BY cw.updated_at DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        params.extend([offset, limit])
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_wallet_stats() -> dict:
    """Admin dashboard summary."""
    with get_conn() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*)           AS total_wallets,
                SUM(balance)       AS total_balance,
                SUM(pending_balance) AS total_pending
            FROM customer_wallets
        """).fetchone()
        wr = conn.execute("""
            SELECT
                COUNT(CASE WHEN status='pending' THEN 1 END) AS pending_withdrawals,
                SUM(CASE WHEN status='pending' THEN amount ELSE 0 END) AS pending_amount
            FROM withdrawal_requests
        """).fetchone()
        return {
            "total_wallets": row["total_wallets"] or 0,
            "total_balance": float(row["total_balance"] or 0),
            "total_pending": float(row["total_pending"] or 0),
            "pending_withdrawals": wr["pending_withdrawals"] or 0,
            "pending_withdrawal_amount": float(wr["pending_amount"] or 0),
        }


# ── Withdrawal OTP ────────────────────────────────────────────────────────────

def get_last_otp_time(customer_id: int):
    """Return created_at of the most recent OTP for cooldown check."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT TOP 1 created_at FROM withdrawal_otps "
            "WHERE customer_id=? ORDER BY created_at DESC",
            (customer_id,),
        ).fetchone()
        return row["created_at"] if row else None


def create_withdrawal_otp(customer_id: int, code: str, expires_at: str) -> int:
    with get_conn() as conn:
        # Invalidate any existing unused OTPs for this customer
        conn.execute(
            "UPDATE withdrawal_otps SET used=1 WHERE customer_id=? AND used=0",
            (customer_id,),
        )
        row = conn.execute(
            """INSERT INTO withdrawal_otps (customer_id, code, expires_at)
               OUTPUT INSERTED.id VALUES (?,?,?)""",
            (customer_id, code, expires_at),
        ).fetchone()
        return row["id"]


def verify_withdrawal_otp(customer_id: int, code: str) -> dict:
    """Verify OTP. Returns {"valid": True/False, "reason": ...}."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT TOP 1 * FROM withdrawal_otps
               WHERE customer_id=? AND used=0
               ORDER BY created_at DESC""",
            (customer_id,),
        ).fetchone()
        if not row:
            return {"valid": False, "reason": "no_otp"}
        if row["attempts"] >= 5:
            return {"valid": False, "reason": "too_many_attempts"}
        # Check expiry
        conn.execute(
            "UPDATE withdrawal_otps SET attempts=attempts+1 WHERE id=?",
            (row["id"],),
        )
        import datetime as _dt
        expires = row["expires_at"]
        if isinstance(expires, str):
            expires = _dt.datetime.fromisoformat(expires)
        # Compare naive (local) times — DB uses GETDATE() (local)
        if expires.tzinfo is not None:
            expires = expires.replace(tzinfo=None)
        now = _dt.datetime.now()
        if now > expires:
            return {"valid": False, "reason": "expired"}
        if row["code"] != code:
            remaining = 5 - (row["attempts"] + 1)
            return {"valid": False, "reason": "wrong_code",
                    "remaining": max(0, remaining)}
        # Mark used
        conn.execute(
            "UPDATE withdrawal_otps SET used=1 WHERE id=?",
            (row["id"],),
        )
        return {"valid": True}
