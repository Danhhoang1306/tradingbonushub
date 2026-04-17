"""New Customer Promo API — 100% rebate for first 30 days."""
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request

from app.db.connection import get_conn
from app.db.repositories.customer_accounts import update_customer_account

router = APIRouter(prefix="/api/promo")

PROMO_DAYS = 30


def get_promo_customers() -> list[dict]:
    """Return all customers currently on a promo (promo_expires_at IS NOT NULL)."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT ca.id, ca.customer_id, ca.use_id, ca.client_name,
                      ca.broker_email, ca.program_id, ca.client_status,
                      ca.promo_expires_at, ca.promo_original_program_id,
                      ca.program_joined_at, ca.created_at,
                      b.name AS broker_name, b.slug AS broker_slug,
                      c.login_email, c.name AS customer_name,
                      p.name AS program_name
               FROM customer_accounts ca
               JOIN brokers b ON b.id = ca.broker_id
               LEFT JOIN customers c ON c.id = ca.customer_id
               LEFT JOIN programs p ON p.id = ca.program_id
               WHERE ca.promo_expires_at IS NOT NULL
               ORDER BY ca.promo_expires_at ASC"""
        ).fetchall()
    return [dict(r) for r in rows]


def get_expiring_promos(days_ahead: int = 3) -> list[dict]:
    """Return promos expiring within the next N days."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT ca.id, ca.customer_id, ca.use_id, ca.client_name,
                      ca.broker_email, ca.program_id, ca.client_status,
                      ca.promo_expires_at, ca.promo_original_program_id,
                      b.name AS broker_name,
                      c.login_email, c.name AS customer_name,
                      p.name AS program_name
               FROM customer_accounts ca
               JOIN brokers b ON b.id = ca.broker_id
               LEFT JOIN customers c ON c.id = ca.customer_id
               LEFT JOIN programs p ON p.id = ca.program_id
               WHERE ca.promo_expires_at IS NOT NULL
                 AND ca.promo_expires_at <= DATEADD(day, ?, GETDATE())
                 AND ca.promo_expires_at >= GETDATE()
               ORDER BY ca.promo_expires_at ASC""",
            (days_ahead,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_expired_promos() -> list[dict]:
    """Return promos that have expired but not yet downgraded."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT ca.id, ca.customer_id, ca.use_id, ca.client_name,
                      ca.broker_email, ca.program_id, ca.client_status,
                      ca.promo_expires_at, ca.promo_original_program_id,
                      b.name AS broker_name,
                      c.login_email, c.name AS customer_name,
                      p.name AS program_name
               FROM customer_accounts ca
               JOIN brokers b ON b.id = ca.broker_id
               LEFT JOIN customers c ON c.id = ca.customer_id
               LEFT JOIN programs p ON p.id = ca.program_id
               WHERE ca.promo_expires_at IS NOT NULL
                 AND ca.promo_expires_at < GETDATE()
               ORDER BY ca.promo_expires_at ASC""",
        ).fetchall()
    return [dict(r) for r in rows]


def downgrade_expired_promos() -> int:
    """Revert expired promo customers to their original program. Returns count."""
    expired = get_expired_promos()
    count = 0
    for ca in expired:
        original_pid = ca["promo_original_program_id"]
        update_customer_account(
            ca["id"],
            program_id=original_pid,
            promo_expires_at=None,
            promo_original_program_id=None,
            program_joined_at=datetime.utcnow(),
        )
        count += 1
    return count


def assign_promo(account_id: int, promo_program_id: int,
                 days: int = PROMO_DAYS) -> None:
    """Assign a promo program to a customer account for N days."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT program_id, promo_expires_at FROM customer_accounts WHERE id=?",
            (account_id,),
        ).fetchone()
    if not row:
        raise ValueError(f"Account {account_id} not found")
    if row["promo_expires_at"]:
        raise ValueError("Account already has an active promo")

    original_program_id = row["program_id"]
    expires = datetime.utcnow() + timedelta(days=days)

    update_customer_account(
        account_id,
        program_id=promo_program_id,
        promo_expires_at=expires,
        promo_original_program_id=original_program_id,
        program_joined_at=datetime.utcnow(),
    )


# ── API Routes ────────────────────────────────────────────────────────────────

@router.get("/customers")
async def api_promo_customers():
    """List all customers with active promos."""
    return get_promo_customers()


@router.get("/expiring")
async def api_expiring_promos(days: int = 3):
    """List promos expiring within N days."""
    return get_expiring_promos(days)


@router.get("/expired")
async def api_expired_promos():
    """List promos that have expired but not downgraded."""
    return get_expired_promos()


@router.post("/assign/{account_id}")
async def api_assign_promo(account_id: int, request: Request):
    """Assign promo to a customer account."""
    d = await request.json()
    promo_program_id = d.get("promo_program_id")
    days = d.get("days", PROMO_DAYS)
    if not promo_program_id:
        raise HTTPException(400, "promo_program_id is required")
    try:
        assign_promo(account_id, promo_program_id, days)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@router.post("/downgrade")
async def api_downgrade_expired():
    """Manually trigger downgrade of all expired promos."""
    count = downgrade_expired_promos()
    return {"ok": True, "downgraded": count}


@router.delete("/revoke/{account_id}")
async def api_revoke_promo(account_id: int):
    """Revoke promo early — revert to original program."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT promo_expires_at, promo_original_program_id FROM customer_accounts WHERE id=?",
            (account_id,),
        ).fetchone()
    if not row or not row["promo_expires_at"]:
        raise HTTPException(400, "Account has no active promo")
    update_customer_account(
        account_id,
        program_id=row["promo_original_program_id"],
        promo_expires_at=None,
        promo_original_program_id=None,
        program_joined_at=datetime.utcnow(),
    )
    return {"ok": True}


@router.get("/dashboard-stats")
async def api_promo_dashboard():
    """Stats for admin dashboard widget."""
    all_promo = get_promo_customers()
    expiring = get_expiring_promos(3)
    expired = get_expired_promos()
    return {
        "total_active": len(all_promo),
        "expiring_3d": len(expiring),
        "expired_pending": len(expired),
        "expiring": expiring[:10],
        "expired": expired[:10],
    }
