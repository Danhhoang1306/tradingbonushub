"""Enrollment management API.

New design: 'enrollment' = a customer_accounts row pending admin review.
Admin sees accounts by client_status and can approve (set to 'active').
"""
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from app.db.connection import get_conn
from app.db.repositories.customer_accounts import (
    count_customer_accounts, get_all_customer_accounts,
    get_customer_account, get_customer_account_by_id,
    get_trading_accounts, update_customer_account,
)
from app.db.repositories.customers import get_customer_by_email
from app.db.repositories.promotions import get_all_ibs, get_broker_by_id, get_program
from app.utils.audit import log_action

import structlog as _structlog
_logger = _structlog.get_logger(__name__)

router = APIRouter(prefix="/api")


async def build_enrollment_context(
    customer_email: str,
    program_id: int | None = None,
    broker_id: int | None = None,
) -> dict:
    """
    Core eligibility check — resolves broker, customer account, and IB status.

    Steps:
    1. Resolve broker_id from program if not provided.
    2. Look up customer_accounts row for (customer, broker).
    3. Check if customer_accounts.ib_number matches a known IB in ibs table.
    4. Return structured context used by enrollment modals.

    Reusable — call from any endpoint that needs enrollment info.
    """
    prog = None
    if program_id:
        prog = await asyncio.to_thread(get_program, int(program_id))
        if not broker_id:
            # Try to match the broker the customer already has an account at
            # (avoids picking the wrong broker for multi-broker programs).
            with get_conn() as conn:
                if customer_email:
                    cust_row = conn.execute(
                        "SELECT id FROM customers WHERE login_email=?", (customer_email,)
                    ).fetchone()
                    if cust_row:
                        matched = conn.execute(
                            """SELECT pb.broker_id
                               FROM program_brokers pb
                               JOIN customer_accounts ca
                                 ON ca.broker_id = pb.broker_id
                                AND ca.customer_id = ?
                               WHERE pb.program_id = ?
                               ORDER BY ca.created_at""",
                            (cust_row["id"], int(program_id)),
                        ).fetchone()
                        if matched:
                            broker_id = matched["broker_id"]

                if not broker_id:
                    # Fallback: first broker in the program
                    row = conn.execute(
                        "SELECT broker_id FROM program_brokers WHERE program_id=? ORDER BY broker_id",
                        (int(program_id),),
                    ).fetchone()
                    broker_id = row["broker_id"] if row else None

    broker = await asyncio.to_thread(get_broker_by_id, broker_id) if broker_id else None
    broker_name = broker["name"] if broker else ""

    customer_account = None
    broker_account_exists = False
    has_broker_email = False
    ib_status = ""
    mt5_accounts = []

    if customer_email and broker_id:
        customer = await asyncio.to_thread(get_customer_by_email, customer_email)
        if customer:
            ca = await asyncio.to_thread(get_customer_account, customer["id"], broker_id)
            if ca:
                # Block early if already has an active/pending enrollment
                if ca.get("program_id") or ca.get("pending_program_id"):
                    existing_name = ""
                    existing_pid = ca.get("pending_program_id") or ca.get("program_id")
                    if existing_pid:
                        ep = await asyncio.to_thread(get_program, int(existing_pid))
                        existing_name = ep.get("name", "") if ep else ""
                    return {
                        "eligible": False,
                        "message": f"You are already enrolled in \"{existing_name}\". Please cancel your current program before enrolling in a new one.",
                    }

                customer_account = ca
                broker_account_exists = bool(ca.get("broker_email"))
                has_broker_email = broker_account_exists
                ib_status = ca.get("client_status", "")
                trading = await asyncio.to_thread(get_trading_accounts, ca["id"])
                mt5_accounts = [
                    {
                        "mt5_number":   t["trading_account"],
                        "account_type": t.get("account_type", ""),
                        "display_name": t.get("account_type", ""),
                    }
                    for t in trading
                ]

    # IB resolution:
    # If customer_accounts.ib_number matches an IB in ibs → already under that IB
    # Otherwise → needs transfer, use first IB with referral link
    ibs = await asyncio.to_thread(get_all_ibs, broker_id=broker_id, active_only=True)
    ca_ib_number = (customer_account or {}).get("ib_number", "") or ""
    matched_ib = next((i for i in ibs if ca_ib_number and i.get("ib_number") == ca_ib_number), None)

    if matched_ib:
        picked = matched_ib
        transfer_required = False
    else:
        ibs_with_link = [i for i in ibs if i.get("reff_link")]
        picked = ibs_with_link[0] if ibs_with_link else (ibs[0] if ibs else {})
        transfer_required = True

    return {
        "program_id":           program_id,
        "program_name":         prog.get("name", "") if prog else "",
        "broker_id":            broker_id,
        "broker_name":          broker_name,
        "broker_account_exists": broker_account_exists,
        "has_broker_email":     has_broker_email,
        "ib_status":            ib_status,
        "registration_type":    "",
        "owner_ib_name":        picked.get("ib_name", ""),
        "ib_number":            picked.get("ib_number", ""),
        "registration_link":    picked.get("reff_link", ""),
        "owner_id":             picked.get("id"),
        "mt5_accounts":         mt5_accounts,
        "transfer_required":    transfer_required,
        "already_under_ib":     matched_ib is not None,
        "is_volume_promo":      (prog.get("type") == "volume") if prog else False,
        "account_type":         "",
        "required_types":       [],
        "required_type_labels": [],
        "ibs":                  ibs,
    }


@router.post("/enrollments/check-promo")
async def api_check_promo(request: Request):
    """
    Check program eligibility and return enrollment info for the modal.
    Reads customer session to determine broker account linkage status.
    """
    data = await request.json()
    program_id  = data.get("program_id") or data.get("promotion_id")
    broker_id   = data.get("broker_id")
    broker_slug = data.get("broker_slug", "")

    if not program_id and not broker_id:
        raise HTTPException(400, "program_id or broker_id is required")

    # Resolve broker_id from slug when explicitly supplied (avoids picking wrong
    # broker for multi-broker programs from program_brokers first row)
    if broker_slug and not broker_id:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM brokers WHERE slug=?", (broker_slug.lower(),)
            ).fetchone()
            if row:
                broker_id = row["id"]

    # Validate program exists
    if program_id and not broker_id:
        prog_check = await asyncio.to_thread(get_program, int(program_id))
        if not prog_check:
            raise HTTPException(404, "Program not found")

    customer_email = request.session.get("customer_email", "")
    return await build_enrollment_context(customer_email, program_id=program_id, broker_id=broker_id)


def _format_enrollment(row: dict) -> dict:
    # Prefer broker_email (the actual trading account email) for admin display.
    # Fall back to portal login_email only when broker_email is absent.
    display_email = row.get("broker_email") or row.get("login_email") or ""
    return {
        "id":             row["id"],
        "customer_email": display_email,
        "login_email":    row.get("login_email") or "",
        "broker_email":   row.get("broker_email") or "",
        "customer_name":  row.get("customer_name") or "",
        "broker_name":    row.get("broker_name") or "",
        "broker_slug":    row.get("broker_slug") or "",
        "promo_name":     row.get("pending_promo_name") or row.get("active_promo_name") or "—",
        "mt5_account":    row.get("mt5_account") or "",
        "program_status": row.get("program_status") or "",
        "pending_program_id": row.get("pending_program_id"),
        "created_at":     str(row["created_at"]) if row.get("created_at") else None,
    }


@router.get("/enrollments/pending-count")
async def api_pending_count():
    """Count enrollments awaiting admin confirmation."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM customer_accounts "
            "WHERE program_status = 'unconfirmed'"
        ).fetchone()
    return {"count": row["cnt"] if row else 0}


@router.get("/enrollments")
async def api_get_enrollments(
    status: Optional[str] = None,
    broker: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
):
    """List enrollments (rows with pending_program_id set) for admin review."""
    broker_id = None
    if broker:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM brokers WHERE slug=?", (broker,)
            ).fetchone()
            broker_id = row["id"] if row else None

    rows = await asyncio.to_thread(
        get_all_customer_accounts,
        broker_id=broker_id,
        search=search,
        limit=limit,
        offset=offset,
        has_enrollment=True,          # only rows with pending_program_id
        program_status=status if status in ("unconfirmed", "confirmed") else None,
    )
    return [_format_enrollment(r) for r in rows]


@router.put("/enrollments/{eid}/confirm")
async def api_confirm_enrollment(eid: int, request: Request):
    """Admin confirms an enrollment: set program_id, client_status='active', send email."""
    account = await asyncio.to_thread(get_customer_account_by_id, eid)
    if not account:
        raise HTTPException(404, "Not found")
    if account.get("program_status") == "confirmed":
        raise HTTPException(400, "Already confirmed")
    if not account.get("pending_program_id"):
        raise HTTPException(400, "No pending program to confirm")

    # Validate ib_number exists under this broker
    ib_number = (account.get("ib_number") or "").strip()
    if not ib_number:
        raise HTTPException(400, "Customer has no IB number — cannot confirm")
    from app.db.connection import get_conn as _gc
    with _gc() as conn:
        ib_exists = conn.execute(
            "SELECT 1 FROM ibs WHERE ib_number=? AND broker_id=?",
            (ib_number, account["broker_id"]),
        ).fetchone()
    if not ib_exists:
        raise HTTPException(400,
            f"IB number '{ib_number}' not found for this broker — "
            f"add it to IBs first or update the customer's IB number")

    # Atomic confirm: only succeed if still in 'unconfirmed' state
    # Prevents race condition if admin clicks confirm twice simultaneously
    pending_pid = account["pending_program_id"]

    def _atomic_confirm():
        from app.db.connection import get_conn as _gc
        with _gc() as conn:
            result = conn.execute(
                """UPDATE customer_accounts SET
                     program_id = ?,
                     pending_program_id = NULL,
                     program_status = 'confirmed',
                     client_status = 'active',
                     program_joined_at = GETUTCDATE()
                   WHERE id = ?
                     AND pending_program_id = ?
                     AND program_status = 'unconfirmed'""",
                (pending_pid, eid, pending_pid),
            )
            if result.rowcount == 0:
                raise ValueError("State changed — enrollment already confirmed or cancelled")

            # Auto-link portal account if broker_email matches a customer
            broker_email = (account.get("broker_email") or "").strip().lower()
            if not account.get("customer_id") and broker_email:
                cust = conn.execute(
                    "SELECT id FROM customers WHERE login_email=?",
                    (broker_email,),
                ).fetchone()
                if cust:
                    # Validate: don't link if this customer already has an account at this broker
                    conflict = conn.execute(
                        "SELECT 1 FROM customer_accounts "
                        "WHERE customer_id=? AND broker_id=? AND id<>?",
                        (cust["id"], account["broker_id"], eid),
                    ).fetchone()
                    if not conflict:
                        conn.execute(
                            "UPDATE customer_accounts SET customer_id=? WHERE id=?",
                            (cust["id"], eid),
                        )

    await asyncio.to_thread(_atomic_confirm)

    # Send confirmation email to customer (non-blocking)
    customer_email = account.get("login_email") or account.get("broker_email") or ""
    promo_name = account.get("pending_promo_name") or str(account["pending_program_id"])
    if customer_email:
        asyncio.create_task(_send_confirmed_email(customer_email, promo_name))

    reviewer = request.session.get("user", "admin")
    log_action(reviewer, "enrollment.confirm",
               entity_type="customer_account", entity_id=str(eid),
               detail={"program_id": account["pending_program_id"]})
    return {"ok": True}


async def _send_confirmed_email(customer_email: str, promo_name: str) -> None:
    from app.services.notifications import send_enrollment_result_email
    try:
        await send_enrollment_result_email(customer_email, promo_name, "active", "")
    except Exception as exc:
        _logger.error("enrollment.confirm_email_failed", error=str(exc))


@router.put("/enrollments/{eid}/reject")
async def api_reject_enrollment(eid: int, request: Request):
    """Admin rejects an enrollment: clear pending state, reset client_status to lead."""
    account = await asyncio.to_thread(get_customer_account_by_id, eid)
    if not account:
        raise HTTPException(404, "Not found")
    if not account.get("pending_program_id"):
        raise HTTPException(400, "No pending program to confirm")

    def _atomic_reject():
        from app.db.connection import get_conn as _gc
        with _gc() as conn:
            result = conn.execute(
                """UPDATE customer_accounts SET
                     pending_program_id = NULL,
                     program_status = NULL,
                     client_status = 'lead'
                   WHERE id = ? AND program_status = 'unconfirmed'""",
                (eid,),
            )
            if result.rowcount == 0:
                raise ValueError("State changed — enrollment no longer pending")

    await asyncio.to_thread(_atomic_reject)

    reviewer = request.session.get("user", "admin")
    log_action(reviewer, "enrollment.reject",
               entity_type="customer_account", entity_id=str(eid),
               detail={"program_id": account["pending_program_id"]})
    return {"ok": True}


@router.put("/enrollments/{eid}/cancel")
async def api_cancel_enrollment(eid: int, request: Request):
    """Admin cancels a confirmed enrollment: clear program_id and reset join date."""
    account = await asyncio.to_thread(get_customer_account_by_id, eid)
    if not account:
        raise HTTPException(404, "Not found")
    if account.get("program_status") != "confirmed":
        raise HTTPException(400, "No confirmed enrollment to cancel")

    prev_program_id = account.get("program_id")

    def _atomic_cancel():
        from app.db.connection import get_conn as _gc
        with _gc() as conn:
            result = conn.execute(
                """UPDATE customer_accounts SET
                     program_id = NULL,
                     program_status = NULL,
                     program_joined_at = NULL,
                     client_status = 'lead'
                   WHERE id = ? AND program_status = 'confirmed'""",
                (eid,),
            )
            if result.rowcount == 0:
                raise ValueError("State changed — enrollment already cancelled")

    await asyncio.to_thread(_atomic_cancel)

    reviewer = request.session.get("user", "admin")
    log_action(reviewer, "enrollment.cancel",
               entity_type="customer_account", entity_id=str(eid),
               detail={"program_id": prev_program_id})
    return {"ok": True}
