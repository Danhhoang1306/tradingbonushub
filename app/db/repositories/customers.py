"""Customer (portal user) CRUD — SQL Server.

customers.login_email is the web portal identifier.
Broker-specific data (use_id, ib_number, broker_email…) lives in customer_accounts.
"""
from app.db.connection import get_conn


# ── Read ───────────────────────────────────────────────────────────────────────

def get_customer_by_email(login_email: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM customers WHERE login_email = ?",
            (login_email,),
        ).fetchone()
        return dict(row) if row else None


def get_customer_by_id(customer_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        return dict(row) if row else None


def get_customer_by_reset_token(token: str) -> dict | None:
    """Return customer only if token exists AND has not expired."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM customers WHERE reset_token=? AND reset_token_expires > GETUTCDATE()",
            (token,),
        ).fetchone()
        return dict(row) if row else None


def get_customer_by_verify_token(token: str) -> dict | None:
    """Return customer only if token exists AND has not expired."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM customers WHERE verify_token=? "
            "AND (verify_token_expires IS NULL OR verify_token_expires > GETUTCDATE())",
            (token,),
        ).fetchone()
        return dict(row) if row else None


# A customer is a "client" when they have ≥1 account that is confirmed+active+managed by an IB.
_CLIENT_SUBQ = (
    "EXISTS (SELECT 1 FROM customer_accounts ca"
    " JOIN ibs i ON i.ib_number = ca.ib_number AND i.broker_id = ca.broker_id"
    " WHERE ca.customer_id = c.id"
    " AND ca.program_status = 'confirmed'"
    " AND ca.client_status = 'active')"
)


def get_all_customers(
    limit: int = 500,
    offset: int = 0,
    customer_type: str | None = None,
    search: str | None = None,
) -> list:
    """customer_type='client' → has ≥1 account that is confirmed+active+has IB."""
    conds, params = [], []
    if customer_type == "client":
        conds.append(_CLIENT_SUBQ)
    elif customer_type == "lead":
        conds.append(f"NOT {_CLIENT_SUBQ}")
    if search:
        s = f"%{search}%"
        conds.append(
            "(c.login_email LIKE ? OR c.name LIKE ? OR EXISTS ("
            "  SELECT 1 FROM customer_accounts ca"
            "  WHERE ca.customer_id = c.id"
            "  AND (ca.broker_email LIKE ? OR ca.use_id LIKE ? OR ca.client_name LIKE ?)"
            "))"
        )
        params.extend([s, s, s, s, s])
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    params.extend([offset, limit])
    with get_conn() as conn:
        # Aggregate broker data once in a derived table — avoids per-row correlated subqueries
        rows = conn.execute(
            f"""SELECT c.id, c.login_email, c.name,
                       c.must_change_password, c.unsubscribed, c.is_verified,
                       c.created_at,
                       ba.broker_emails,
                       ba.broker_use_ids
               FROM customers c
               LEFT JOIN (
                   SELECT ca.customer_id,
                          STRING_AGG(
                              CASE WHEN ca.broker_email <> '' THEN
                                  ca.broker_email + ' [' + b.name + ']'
                              ELSE NULL END, ', ') AS broker_emails,
                          STRING_AGG(
                              CASE WHEN ca.use_id IS NOT NULL THEN
                                  ca.use_id + ' [' + b.name + ']'
                              ELSE NULL END, ', ') AS broker_use_ids
                   FROM customer_accounts ca
                   JOIN brokers b ON b.id = ca.broker_id
                   GROUP BY ca.customer_id
               ) ba ON ba.customer_id = c.id
               {where}
               ORDER BY c.created_at DESC
               OFFSET ? ROWS FETCH NEXT ? ROWS ONLY""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def count_customers(
    customer_type: str | None = None,
    search: str | None = None,
) -> int:
    conds, params = [], []
    if customer_type == "client":
        conds.append(_CLIENT_SUBQ)
    elif customer_type == "lead":
        conds.append(f"NOT {_CLIENT_SUBQ}")
    if search:
        s = f"%{search}%"
        conds.append(
            "(c.login_email LIKE ? OR c.name LIKE ? OR EXISTS ("
            "  SELECT 1 FROM customer_accounts ca"
            "  WHERE ca.customer_id = c.id"
            "  AND (ca.broker_email LIKE ? OR ca.use_id LIKE ? OR ca.client_name LIKE ?)"
            "))"
        )
        params.extend([s, s, s, s, s])
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM customers c {where}", params
        ).fetchone()
        return row["cnt"] if row else 0


# ── Write ──────────────────────────────────────────────────────────────────────

def create_customer(
    login_email: str,
    password_hash: str,
    name: str = "",
    must_change_password: int = 1,
    is_verified: int = 0,
    verify_token: str | None = None,
    customer_type: str = "client",  # kept for call-site compatibility, ignored
) -> int:
    with get_conn() as conn:
        row = conn.execute(
            """INSERT INTO customers
               (login_email, name, password_hash, must_change_password,
                is_verified, verify_token)
               OUTPUT INSERTED.id
               VALUES (?, ?, ?, ?, ?, ?)""",
            (login_email, name, password_hash, must_change_password,
             is_verified, verify_token),
        ).fetchone()
        return row["id"] if row else None


def set_customer_password(login_email: str, password_hash: str, must_change: int = 0) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE customers SET password_hash=?, must_change_password=?, "
            "reset_token=NULL, reset_token_expires=NULL WHERE login_email=?",
            (password_hash, must_change, login_email),
        )


def set_reset_token(login_email: str, token: str, expires_iso: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE customers SET reset_token=?, reset_token_expires=? WHERE login_email=?",
            (token, expires_iso, login_email),
        )


def clear_reset_token(login_email: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE customers SET reset_token=NULL, reset_token_expires=NULL WHERE login_email=?",
            (login_email,),
        )


def set_verify_token(login_email: str, token: str, expires_hours: int = 24) -> None:
    from datetime import datetime, timedelta, timezone
    expires = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    with get_conn() as conn:
        conn.execute(
            "UPDATE customers SET verify_token=?, verify_token_expires=?, is_verified=0 "
            "WHERE login_email=?",
            (token, expires, login_email),
        )


def clear_verify_token(login_email: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE customers SET verify_token=NULL, is_verified=1 WHERE login_email=?",
            (login_email,),
        )


def set_unsubscribed(login_email: str, value: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE customers SET unsubscribed=? WHERE login_email=?",
            (value, login_email),
        )


def delete_customer(customer_id: int) -> None:
    # customer_accounts rows are deleted via ON DELETE CASCADE
    with get_conn() as conn:
        conn.execute("DELETE FROM customers WHERE id=?", (customer_id,))


def update_last_login(login_email: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE customers SET last_login_at=GETUTCDATE() WHERE login_email=?",
            (login_email,),
        )


# ── Email history ──────────────────────────────────────────────────────────────

def get_customer_emails(login_email: str) -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT e.id, e.recipient_name, e.created_at,
                   COUNT(o.id)      AS open_count,
                   MAX(o.opened_at) AS last_opened
            FROM emails e
            LEFT JOIN opens o ON o.tracking_id = e.id
            WHERE e.recipient_email = ?
            GROUP BY e.id, e.recipient_name, e.created_at
            ORDER BY e.created_at DESC
        """, (login_email,)).fetchall()
        return [dict(r) for r in rows]


# ── Contact requests ───────────────────────────────────────────────────────────

def create_contact(name: str, email: str, phone: str, message: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO contact_requests (name, email, phone, message) VALUES (?,?,?,?)",
            (name, email, phone, message),
        )


def get_all_contacts() -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM contact_requests ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
