"""API endpoints for end-of-month bonus milestones."""
from datetime import date
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.services.bonus_payment import (
    get_bonus_summary,
    get_pending_bonuses,
    mark_bonuses_paid,
    export_bonus_csv,
)

router = APIRouter(prefix="/api/bonus", tags=["bonus"])


def _require_admin(request: Request):
    if not request.session.get("user"):
        raise HTTPException(401, "Unauthorized")


class PaidItem(BaseModel):
    customer_account_id: int
    tier_id: int
    year: int
    month: int
    total_lots: float = 0
    bonus_usd: float


class MarkPaidRequest(BaseModel):
    items: list[PaidItem]
    paid_by: str = "admin"


# GET /api/bonus/pending?year=2026&month=3
@router.get("/pending")
def api_get_pending(request: Request, year: int = None, month: int = None):
    _require_admin(request)
    today = date.today()
    y = year  or today.year
    m = month or today.month
    return get_bonus_summary(y, m)


# POST /api/bonus/mark-paid
@router.post("/mark-paid")
def api_mark_paid(request: Request, body: MarkPaidRequest):
    _require_admin(request)
    if not body.items:
        raise HTTPException(400, "items is required")
    return mark_bonuses_paid(
        [i.model_dump() for i in body.items],
        body.paid_by,
    )


# POST /api/bonus/export?year=2026&month=3
@router.post("/export")
def api_export(request: Request, year: int = None, month: int = None):
    _require_admin(request)
    today = date.today()
    y = year  or today.year
    m = month or today.month
    result = export_bonus_csv(y, m)
    if not result["file"]:
        raise HTTPException(404, result["message"])
    return result
