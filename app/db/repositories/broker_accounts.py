"""Customer broker account CRUD — one row per (customer, broker) pair.

Each customer can have at most one account per broker.
broker_email uniqueness per broker is enforced by a filtered DB index
(UQ_cba_broker_email) — the same broker email cannot be linked to two
different portal accounts.
"""
from app.db.connection import get_conn


def get_broker_account(customer_id: int, broker_id: int) -> dict | None:
    """Return the broker account for a given (customer, broker) pair, or None."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT cba.*, b.name AS broker_name, b.slug AS broker_slug
               FROM customer_broker_accounts cba
               JOIN brokers b ON b.id = cba.broker_id
               WHERE cba.customer_id = ? AND cba.broker_id = ?""",
            (customer_id, broker_id),
        ).fetchone()
        return dict(row) if row else None


def get_broker_account_by_id(broker_account_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT cba.*, b.name AS broker_name, b.slug AS broker_slug,
                      c.email AS login_email, c.name AS customer_name
               FROM customer_broker_accounts cba
               JOIN brokers b ON b.id = cba.broker_id
               JOIN customers c ON c.id = cba.customer_id
               WHERE cba.id = ?""",
            (broker_account_id,),
        ).fetchone()
        return dict(row) if row else None


def get_broker_accounts_for_customer(customer_id: int) -> list:
    """Return all broker accounts for a customer, ordered by broker display_order."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT cba.*, b.name AS broker_name, b.slug AS broker_slug
               FROM customer_broker_accounts cba
               JOIN brokers b ON b.id = cba.broker_id
               WHERE cba.customer_id = ?
               ORDER BY b.display_order""",
            (customer_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_broker_account_by_broker_email(broker_id: int, broker_email: str) -> dict | None:
    """Find which customer owns a given broker email.

    Used to detect conflicts when a new customer tries to register or link an
    email that already belongs to another portal account at the same broker.
    Returns None when broker_email is empty.
    """
    if not broker_email or not broker_email.strip():
        return None
    with get_conn() as conn:
        row = conn.execute(
            """SELECT cba.*, c.email AS login_email, c.name AS customer_name,
                      b.name AS broker_name, b.slug AS broker_slug
               FROM customer_broker_accounts cba
               JOIN customers c ON c.id = cba.customer_id
               JOIN brokers   b ON b.id = cba.broker_id
               WHERE cba.broker_id = ? AND cba.broker_email = ?""",
            (broker_id, broker_email.strip().lower()),
        ).fetchone()
        return dict(row) if row else None


def get_broker_account_by_uid(broker_id: int, broker_uid: str) -> dict | None:
    """Find broker account by UID at a specific broker."""
    if not broker_uid or not broker_uid.strip():
        return None
    with get_conn() as conn:
        row = conn.execute(
            """SELECT cba.*, c.email AS login_email, c.name AS customer_name,
                      b.name AS broker_name, b.slug AS broker_slug
               FROM customer_broker_accounts cba
               JOIN customers c ON c.id = cba.customer_id
               JOIN brokers   b ON b.id = cba.broker_id
               WHERE cba.broker_id = ? AND cba.broker_uid = ?""",
            (broker_id, broker_uid.strip()),
        ).fetchone()
        return dict(row) if row else None


def upsert_broker_account(
    customer_id: int,
    broker_id: int,
    *,
    broker_email: str = "",
    broker_uid: str = "",
    ib_name: str = "",
    affid: str = "",
    ib_status: str = "pending_data",
    registration_type: str = "new_account",
    vantage_account_type: str = "",
    ib_account_number: str = "",
) -> int:
    """Create or update a broker account. Returns broker_account_id.

    Only overwrites non-empty values for optional fields (broker_email,
    broker_uid, ib_name, affid, vantage_account_type, ib_account_number).
    ib_status and registration_type are always updated.
    """
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM customer_broker_accounts WHERE customer_id=? AND broker_id=?",
            (customer_id, broker_id),
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE customer_broker_accounts SET
                   broker_email         = CASE WHEN ?<>'' THEN ? ELSE broker_email END,
                   broker_uid           = CASE WHEN ?<>'' THEN ? ELSE broker_uid END,
                   ib_name              = CASE WHEN ?<>'' THEN ? ELSE ib_name END,
                   affid                = CASE WHEN ?<>'' THEN ? ELSE affid END,
                   ib_status            = ?,
                   registration_type    = ?,
                   vantage_account_type = CASE WHEN ?<>'' THEN ? ELSE vantage_account_type END,
                   ib_account_number    = CASE WHEN ?<>'' THEN ? ELSE ib_account_number END
                   WHERE id = ?""",
                (
                    broker_email, broker_email,
                    broker_uid,   broker_uid,
                    ib_name,      ib_name,
                    affid,        affid,
                    ib_status,
                    registration_type,
                    vantage_account_type, vantage_account_type,
                    ib_account_number,    ib_account_number,
                    existing["id"],
                ),
            )
            return existing["id"]
        else:
            row = conn.execute(
                """INSERT INTO customer_broker_accounts
                   (customer_id, broker_id, broker_email, broker_uid, ib_name, affid,
                    ib_status, registration_type, vantage_account_type, ib_account_number)
                   OUTPUT INSERTED.id
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    customer_id, broker_id,
                    broker_email, broker_uid,
                    ib_name, affid,
                    ib_status, registration_type,
                    vantage_account_type, ib_account_number,
                ),
            ).fetchone()
            return row["id"] if row else None


def update_broker_account_ib_status(broker_account_id: int, ib_status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE customer_broker_accounts SET ib_status=? WHERE id=?",
            (ib_status, broker_account_id),
        )


def update_broker_account_fields(broker_account_id: int, **kwargs) -> None:
    """Update arbitrary whitelisted fields on a broker account."""
    _ALLOWED = {
        "broker_email", "broker_uid", "ib_name", "affid",
        "ib_status", "registration_type", "vantage_account_type", "ib_account_number",
    }
    updates = {k: v for k, v in kwargs.items() if k in _ALLOWED}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE customer_broker_accounts SET {set_clause} WHERE id=?",
            [*updates.values(), broker_account_id],
        )
