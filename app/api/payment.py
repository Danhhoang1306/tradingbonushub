"""API endpoints cho Payment admin page."""
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Request

from app.services.vantage_exporter import export_vantage_rebate

router = APIRouter(prefix="/api/payment", tags=["payment"])


@router.post("/export-daily")
def api_export_daily(request: Request, date_str: str = Query(None, alias="date")):
    if not request.session.get("user"):
        raise HTTPException(401, "Unauthorized")
    """
    Export Vantage rebate file for a specific date.
    date format: YYYY-MM-DD (default: yesterday)
    """
    target = None
    if date_str:
        try:
            target = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(400, f"Invalid date format: {date_str}. Use YYYY-MM-DD")

    result = export_vantage_rebate(target)
    return result
