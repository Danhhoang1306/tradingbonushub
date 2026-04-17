"""Customer accounts CRUD — one row per (customer, broker) pair.

customer_id   NULL  → lead (data imported before person registers on portal)
use_id        NULL  → no broker platform User ID yet
ib_number     NULL  → lead / pending; required when client_status = 'active'
"""
from app.db.connection import get_conn


# ── Read ───────────────────────────────────────────────────────────────────────

def get_customer_account(customer_id: int, broker_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT ca.*, b.name AS broker_name, b.slug AS broker_slug
               FROM customer_accounts ca
               JOIN brokers b ON b.id = ca.broker_id
               WHERE ca.customer_id = ? AND ca.broker_id = ?""",
            (customer_id, broker_id),
        ).fetchone()
        return dict(row) if row else None


def get_customer_account_by_id(account_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT ca.*, b.name AS broker_name, b.slug AS broker_slug,
                      c.login_email, c.name AS customer_name
               FROM customer_accounts ca
               JOIN brokers b ON b.id = ca.broker_id
               LEFT JOIN customers c ON c.id = ca.customer_id
               WHERE ca.id = ?""",
            (account_id,),
        ).fetchone()
        return dict(row) if row else None


def get_accounts_for_customer(customer_id: int) -> list:
    """All broker accounts for a portal customer, ordered by broker display_order."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT ca.*, b.name AS broker_name, b.slug AS broker_slug
               FROM customer_accounts ca
               JOIN brokers b ON b.id = ca.broker_id
               WHERE ca.customer_id = ?
               ORDER BY b.display_order""",
            (customer_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_account_by_use_id(broker_id: int, use_id: str) -> dict | None:
    """Find a customer account by broker platform User ID."""
    if not use_id or not str(use_id).strip():
        return None
    with get_conn() as conn:
        row = conn.execute(
            """SELECT ca.*, b.name AS broker_name, b.slug AS broker_slug,
                      c.login_email, c.name AS customer_name
               FROM customer_accounts ca
               JOIN brokers b ON b.id = ca.broker_id
               LEFT JOIN customers c ON c.id = ca.customer_id
               WHERE ca.broker_id = ? AND ca.use_id = ?""",
            (broker_id, str(use_id).strip()),
        ).fetchone()
        return dict(row) if row else None


def get_account_by_broker_email(broker_id: int, broker_email: str) -> dict | None:
    """Find a customer account by the email used at a specific broker."""
    if not broker_email or not broker_email.strip():
        return None
    with get_conn() as conn:
        row = conn.execute(
            """SELECT ca.*, b.name AS broker_name, b.slug AS broker_slug,
                      c.login_email, c.name AS customer_name
               FROM customer_accounts ca
               JOIN brokers b ON b.id = ca.broker_id
               LEFT JOIN customers c ON c.id = ca.customer_id
               WHERE ca.broker_id = ? AND ca.broker_email = ?""",
            (broker_id, broker_email.strip().lower()),
        ).fetchone()
        return dict(row) if row else None


def get_all_customer_accounts(
    client_status: str | None = None,
    broker_id: int | None = None,
    search: str | None = None,
    limit: int = 500,
    offset: int = 0,
    has_enrollment: bool = False,
    program_status: str | None = None,
) -> list:
    conds, params = [], []
    if has_enrollment:
        conds.append("ca.pending_program_id IS NOT NULL")
    if program_status:
        conds.append("ca.program_status = ?")
        params.append(program_status)
    if client_status:
        conds.append("ca.client_status = ?")
        params.append(client_status)
    if broker_id:
        conds.append("ca.broker_id = ?")
        params.append(broker_id)
    if search:
        s = f"%{search}%"
        conds.append(
            "(ca.broker_email LIKE ? OR ca.client_name LIKE ? "
            "OR ca.use_id LIKE ? OR ca.ib_number LIKE ? "
            "OR c.login_email LIKE ?)"
        )
        params.extend([s, s, s, s, s])
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    params.extend([offset, limit])
    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT ca.*, b.name AS broker_name, b.slug AS broker_slug,
                       c.login_email, c.name AS customer_name,
                       pp.name AS pending_promo_name,
                       p.name  AS active_promo_name,
                       ta_latest.trading_account AS mt5_account
                FROM customer_accounts ca
                JOIN brokers b ON b.id = ca.broker_id
                LEFT JOIN customers c ON c.id = ca.customer_id
                LEFT JOIN programs pp ON pp.id = ca.pending_program_id
                LEFT JOIN programs p  ON p.id  = ca.program_id
                LEFT JOIN (
                    SELECT customer_account_id,
                           trading_account,
                           ROW_NUMBER() OVER (
                               PARTITION BY customer_account_id ORDER BY created_at DESC
                           ) AS rn
                    FROM trading_accounts
                    WHERE is_active = 1
                ) ta_latest ON ta_latest.customer_account_id = ca.id AND ta_latest.rn = 1
                {where}
                ORDER BY ca.created_at DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def count_customer_accounts(
    client_status: str | None = None,
    broker_id: int | None = None,
    search: str | None = None,
) -> int:
    conds, params = [], []
    if client_status:
        conds.append("ca.client_status = ?")
        params.append(client_status)
    if broker_id:
        conds.append("ca.broker_id = ?")
        params.append(broker_id)
    if search:
        s = f"%{search}%"
        conds.append(
            "(ca.broker_email LIKE ? OR ca.client_name LIKE ? "
            "OR ca.use_id LIKE ? OR ca.ib_number LIKE ? "
            "OR c.login_email LIKE ?)"
        )
        params.extend([s, s, s, s, s])
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    with get_conn() as conn:
        row = conn.execute(
            f"""SELECT COUNT(*) AS cnt
                FROM customer_accounts ca
                LEFT JOIN customers c ON c.id = ca.customer_id
                {where}""",
            params,
        ).fetchone()
        return row["cnt"] if row else 0


# ── Write ──────────────────────────────────────────────────────────────────────

def create_customer_account(
    broker_id: int,
    *,
    customer_id: int | None = None,
    use_id: str | None = None,
    ib_number: str | None = None,
    broker_email: str = "",
    client_name: str = "",
    country: str = "",
    client_status: str = "lead",
    program_id: int | None = None,
    link_verify_token: str | None = None,
) -> int:
    """Create a new customer account row. Returns the new id."""
    with get_conn() as conn:
        row = conn.execute(
            """INSERT INTO customer_accounts
               (customer_id, broker_id, use_id, ib_number,
                broker_email, client_name, country, client_status, program_id,
                link_verify_token)
               OUTPUT INSERTED.id
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                customer_id, broker_id,
                use_id or None, ib_number or None,
                broker_email.strip().lower() if broker_email else "",
                client_name, country, client_status, program_id,
                link_verify_token or None,
            ),
        ).fetchone()
        return row["id"] if row else None


def upsert_customer_account(
    broker_id: int,
    use_id: str,
    *,
    customer_id: int | None = None,
    ib_number: str | None = None,
    broker_email: str = "",
    client_name: str = "",
    country: str = "",
    client_status: str = "lead",
    program_id: int | None = None,
) -> int:
    """Atomic insert-or-update by (broker_id, use_id) or (broker_id, broker_email).

    Uses a single transaction with UPDLOCK to prevent race conditions.
    Lookup priority:
    1. (broker_id, use_id)        — exact match when use_id is provided
    2. (broker_id, broker_email)  — fallback for pre-linked emails
    """
    uid = str(use_id).strip() if use_id else None
    norm_email = broker_email.strip().lower() if broker_email else ""

    with get_conn() as conn:
        # Single atomic lookup with UPDLOCK to prevent concurrent inserts
        existing = None
        if uid:
            existing = conn.execute(
                "SELECT id FROM customer_accounts WITH (UPDLOCK) "
                "WHERE broker_id=? AND use_id=?",
                (broker_id, uid),
            ).fetchone()
        if not existing and norm_email:
            existing = conn.execute(
                "SELECT id FROM customer_accounts WITH (UPDLOCK) "
                "WHERE broker_id=? AND broker_email=?",
                (broker_id, norm_email),
            ).fetchone()

        if existing:
            conn.execute(
                """UPDATE customer_accounts SET
                   customer_id   = CASE WHEN ? IS NOT NULL THEN ? ELSE customer_id END,
                   use_id        = CASE WHEN ? IS NOT NULL AND ?<>'' THEN ? ELSE use_id END,
                   ib_number     = CASE WHEN ? IS NOT NULL AND ?<>'' THEN ? ELSE ib_number END,
                   broker_email  = CASE WHEN ?<>'' THEN ? ELSE broker_email END,
                   client_name   = CASE WHEN ?<>'' THEN ? ELSE client_name END,
                   country       = CASE WHEN ?<>'' THEN ? ELSE country END,
                   program_id    = CASE WHEN ? IS NOT NULL THEN ? ELSE program_id END
                   WHERE id = ?""",
                (
                    customer_id, customer_id,
                    uid, uid, uid,
                    ib_number, ib_number, ib_number,
                    norm_email, norm_email,
                    client_name, client_name,
                    country, country,
                    program_id, program_id,
                    existing["id"],
                ),
            )
            return existing["id"]
        else:
            row = conn.execute(
                """INSERT INTO customer_accounts
                   (customer_id, broker_id, use_id, ib_number,
                    broker_email, client_name, country, client_status, program_id)
                   OUTPUT INSERTED.id
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    customer_id, broker_id, uid,
                    ib_number or None,
                    norm_email, client_name, country, client_status, program_id,
                ),
            ).fetchone()
            return row["id"] if row else None


def update_customer_account(account_id: int, **kwargs) -> None:
    """Update whitelisted fields on a customer account."""
    _ALLOWED = {
        "customer_id", "use_id", "ib_number", "broker_email",
        "client_name", "country", "client_status", "program_id",
        "pending_program_id", "program_status",
        "link_verify_token", "customer_linked_at",
        "program_joined_at",
        "promo_expires_at", "promo_original_program_id",
    }
    updates = {k: v for k, v in kwargs.items() if k in _ALLOWED}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE customer_accounts SET {set_clause} WHERE id=?",
            [*updates.values(), account_id],
        )


def link_customer_to_account(account_id: int, customer_id: int, verify_token: str = "") -> None:
    """Link a portal customer to an existing lead account (pending verification).

    Security: clears any program enrollment state the lead row may carry so that
    the customer must go through the normal enrollment + admin-approval flow.
    """
    with get_conn() as conn:
        conn.execute(
            """UPDATE customer_accounts
               SET customer_id=?, link_verify_token=?, customer_linked_at=NULL,
                   program_id=NULL, pending_program_id=NULL,
                   program_status=NULL, program_joined_at=NULL
               WHERE id=?""",
            (customer_id, verify_token or None, account_id),
        )


def verify_broker_email_token(token: str) -> bool:
    """Verify broker email ownership token. Returns True if token was valid."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM customer_accounts WHERE link_verify_token=?", (token,)
        ).fetchone()
        if not row:
            return False
        conn.execute(
            "UPDATE customer_accounts SET link_verify_token=NULL, customer_linked_at=GETDATE() WHERE id=?",
            (row["id"],),
        )
        return True


def unlink_customer_account(account_id: int) -> None:
    """Remove customer link from account row, preserving lead data."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE customer_accounts SET customer_id=NULL, link_verify_token=NULL, customer_linked_at=NULL WHERE id=?",
            (account_id,),
        )


# ── Trading accounts ───────────────────────────────────────────────────────────

def get_trading_accounts(customer_account_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM trading_accounts
               WHERE customer_account_id = ? AND is_active = 1
               ORDER BY id""",
            (customer_account_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_trading_accounts_by_customer(customer_id: int) -> list:
    """All active trading accounts for a portal customer across all brokers."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT ta.*, ca.broker_id, b.name AS broker_name, b.slug AS broker_slug,
                      ca.use_id, ca.ib_number
               FROM trading_accounts ta
               JOIN customer_accounts ca ON ca.id = ta.customer_account_id
               JOIN brokers b ON b.id = ca.broker_id
               WHERE ca.customer_id = ? AND ta.is_active = 1
               ORDER BY b.display_order, ta.id""",
            (customer_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def upsert_trading_account(
    customer_account_id: int,
    trading_account: str,
    account_type: str = "",
) -> int:
    """Insert or update by trading_account number. Returns trading_account id."""
    ta = str(trading_account).strip()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM trading_accounts WHERE trading_account=?", (ta,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE trading_accounts SET
                   customer_account_id = ?,
                   account_type = CASE WHEN ?<>'' THEN ? ELSE account_type END
                   WHERE id = ?""",
                (customer_account_id, account_type, account_type, existing["id"]),
            )
            return existing["id"]
        else:
            row = conn.execute(
                """INSERT INTO trading_accounts
                   (customer_account_id, trading_account, account_type)
                   OUTPUT INSERTED.id
                   VALUES (?,?,?)""",
                (customer_account_id, ta, account_type),
            ).fetchone()
            return row["id"] if row else None
