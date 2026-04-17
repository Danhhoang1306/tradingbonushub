"""API endpoints for wallet management (admin + customer portal)."""
import asyncio
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.db.repositories.customers import get_customer_by_email
from app.db.repositories.wallet import (
    create_withdrawal_otp,
    get_all_wallets,
    get_all_withdrawal_requests,
    get_or_create_wallet,
    get_transactions,
    get_wallet_stats,
    get_withdrawal_request,
    get_withdrawal_requests_by_wallet,
    verify_withdrawal_otp,
)
from app.services.wallet_service import (
    approve_withdrawal,
    cancel_withdrawal,
    complete_withdrawal,
    credit_wallet,
    reject_withdrawal,
    request_withdrawal,
)

router = APIRouter(prefix="/api/wallet", tags=["wallet"])

OTP_EXPIRY_MINUTES = 5
OTP_COOLDOWN_SECONDS = 60


# ── Admin endpoints ──────────────────────────────────────────────────────────

@router.get("/admin/stats")
def api_wallet_stats():
    return get_wallet_stats()


@router.get("/admin/list")
def api_wallet_list(search: str = "", limit: int = 100, offset: int = 0):
    return get_all_wallets(limit=limit, offset=offset,
                           search=search or None)


@router.get("/admin/withdrawals")
def api_withdrawal_list(status: str = "", limit: int = 100, offset: int = 0):
    return get_all_withdrawal_requests(status=status or None,
                                       limit=limit, offset=offset)


class CreditRequest(BaseModel):
    customer_id: int
    amount: float
    tx_type: str = "manual_credit"
    description: str = ""


@router.post("/admin/credit")
def api_admin_credit(body: CreditRequest, request: Request):
    admin = request.session.get("user", "admin")
    try:
        return credit_wallet(
            body.customer_id, body.amount, body.tx_type,
            description=body.description or f"Manual credit by {admin}",
            created_by=admin,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/admin/withdrawal/{wr_id}")
def api_get_withdrawal(wr_id: int):
    wr = get_withdrawal_request(wr_id)
    if not wr:
        raise HTTPException(404, "Not found")
    return wr


class WithdrawalActionRequest(BaseModel):
    admin_note: str = ""
    tx_hash: str | None = None


@router.post("/admin/withdrawal/{wr_id}/approve")
def api_approve_withdrawal(wr_id: int, body: WithdrawalActionRequest,
                           request: Request):
    admin = request.session.get("user", "admin")
    try:
        return approve_withdrawal(wr_id, reviewed_by=admin, tx_hash=body.tx_hash)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/admin/withdrawal/{wr_id}/complete")
def api_complete_withdrawal(wr_id: int, body: WithdrawalActionRequest,
                            request: Request):
    admin = request.session.get("user", "admin")
    try:
        return complete_withdrawal(wr_id, reviewed_by=admin, tx_hash=body.tx_hash)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/admin/withdrawal/{wr_id}/reject")
def api_reject_withdrawal(wr_id: int, body: WithdrawalActionRequest,
                           request: Request):
    admin = request.session.get("user", "admin")
    try:
        return reject_withdrawal(wr_id, reviewed_by=admin,
                                  admin_note=body.admin_note)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── Customer portal endpoints ────────────────────────────────────────────────

def _get_customer(request: Request) -> dict:
    email = request.session.get("customer_email", "")
    if not email:
        raise HTTPException(401, "Unauthorized")
    customer = get_customer_by_email(email)
    if not customer:
        raise HTTPException(401, "Unauthorized")
    return customer


@router.get("/me")
def api_my_wallet(request: Request):
    customer = _get_customer(request)
    wallet = get_or_create_wallet(customer["id"])
    return {
        "wallet": wallet,
        "withdrawals": get_withdrawal_requests_by_wallet(wallet["id"]),
    }


@router.get("/me/transactions")
def api_my_transactions(request: Request,
                        limit: int = 50, offset: int = 0):
    customer = _get_customer(request)
    wallet = get_or_create_wallet(customer["id"])
    return get_transactions(wallet["id"], limit=limit, offset=offset)


# ── OTP-protected withdrawal flow ────────────────────────────────────────────

@router.post("/me/withdraw/send-otp")
async def api_send_withdrawal_otp(request: Request):
    """Send a 6-digit OTP code to the customer's email."""
    customer = _get_customer(request)

    # Cooldown: check DB for last OTP created_at (prevents bypass via session manipulation)
    from app.db.repositories.wallet import get_last_otp_time
    last_otp_time = get_last_otp_time(customer["id"])
    if last_otp_time:
        if isinstance(last_otp_time, str):
            last_otp_time = datetime.fromisoformat(last_otp_time)
        # DB uses GETDATE() (local time), so compare with naive local time
        if last_otp_time.tzinfo is not None:
            last_otp_time = last_otp_time.replace(tzinfo=None)
        elapsed = (datetime.now() - last_otp_time).total_seconds()
        if elapsed < OTP_COOLDOWN_SECONDS:
            remaining = int(OTP_COOLDOWN_SECONDS - elapsed)
            raise HTTPException(429, f"Please wait {remaining} seconds before requesting a new code")

    # Generate 6-digit code
    code = "".join(str(secrets.randbelow(10)) for _ in range(6))
    expires = datetime.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)

    create_withdrawal_otp(customer["id"], code, expires.isoformat())

    # Send email
    from app.services.notifications import send_withdrawal_otp
    await send_withdrawal_otp(customer["login_email"], code)

    return {"sent": True, "expires_in": OTP_EXPIRY_MINUTES * 60}


class WithdrawalRequest(BaseModel):
    amount: float
    method: str = "bank_transfer"
    wallet_address: str | None = None
    wallet_network: str | None = None
    bank_info: str | None = None
    otp_code: str


@router.post("/me/withdraw")
def api_request_withdrawal(body: WithdrawalRequest, request: Request):
    customer = _get_customer(request)

    # Verify OTP first
    if not body.otp_code or len(body.otp_code) != 6:
        raise HTTPException(400, "Invalid verification code")

    result = verify_withdrawal_otp(customer["id"], body.otp_code)
    if not result["valid"]:
        messages = {
            "no_otp": "No verification code found. Please request one first.",
            "expired": "Verification code has expired. Please request a new one.",
            "too_many_attempts": "Too many incorrect attempts. Please request a new code.",
            "wrong_code": f"Incorrect verification code. {result.get('remaining', 0)} attempts remaining.",
        }
        raise HTTPException(400, messages.get(result["reason"], "Invalid code"))

    try:
        return request_withdrawal(
            customer["id"], body.amount, body.method,
            wallet_address=body.wallet_address,
            wallet_network=body.wallet_network,
            bank_info=body.bank_info,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/me/withdraw/{wr_id}/cancel")
def api_cancel_withdrawal(wr_id: int, request: Request):
    customer = _get_customer(request)
    try:
        return cancel_withdrawal(customer["id"], wr_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
