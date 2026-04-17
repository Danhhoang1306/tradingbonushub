"""Health check endpoint — no authentication required."""
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import APP_START_TIME, APP_VERSION
from app.db.connection import get_conn

router = APIRouter()


@router.get("/health")
async def health_check():
    # DB ping
    db_status = "ok"
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1")
    except Exception as e:
        db_status = f"error: {e}"

    now = datetime.now(timezone.utc)
    uptime = (now - APP_START_TIME).total_seconds()

    status = "ok" if db_status == "ok" else "degraded"
    return JSONResponse(
        status_code=200 if status == "ok" else 503,
        content={
            "status":          status,
            "version":         APP_VERSION,
            "db":              db_status,
            "uptime_seconds":  round(uptime, 1),
            "timestamp":       now.isoformat(),
        },
    )
