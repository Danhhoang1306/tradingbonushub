"""Analytics & Reporting API — dashboard stats, trends, program performance."""
from fastapi import APIRouter, Query, Request

from app.db.connection import get_conn

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _require_admin(request: Request) -> str:
    user = request.session.get("user")
    role = request.session.get("user_role", "admin")
    if not user or role not in ("admin", "finance"):
        from fastapi import HTTPException
        raise HTTPException(403, "Admin role required")
    return user


@router.get("/overview")
async def api_overview(request: Request):
    """Full dashboard analytics overview."""
    _require_admin(request)
    with get_conn() as conn:
        # Customer stats
        total_customers = conn.execute(
            "SELECT COUNT(*) AS cnt FROM customers"
        ).fetchone()["cnt"]
        new_customers_30d = conn.execute(
            "SELECT COUNT(*) AS cnt FROM customers "
            "WHERE created_at >= DATEADD(DAY, -30, GETDATE())"
        ).fetchone()["cnt"]
        new_customers_7d = conn.execute(
            "SELECT COUNT(*) AS cnt FROM customers "
            "WHERE created_at >= DATEADD(DAY, -7, GETDATE())"
        ).fetchone()["cnt"]
        active_accounts = conn.execute(
            "SELECT COUNT(*) AS cnt FROM customer_accounts WHERE client_status='active'"
        ).fetchone()["cnt"]

        # Rebate stats
        total_rebate_paid = conn.execute(
            "SELECT ISNULL(SUM(CAST(rebate_amount AS FLOAT)), 0) AS total "
            "FROM rebate_records WHERE status IN ('exported','paid')"
        ).fetchone()["total"]
        rebate_this_month = conn.execute(
            "SELECT ISNULL(SUM(CAST(rebate_amount AS FLOAT)), 0) AS total "
            "FROM rebate_records rr "
            "JOIN rebate_batches rb ON rb.id = rr.batch_id "
            "WHERE rb.period_date >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)"
        ).fetchone()["total"]

        # Wallet stats
        total_wallet_balance = conn.execute(
            "SELECT ISNULL(SUM(CAST(balance AS FLOAT)), 0) AS total FROM customer_wallets"
        ).fetchone()["total"]
        pending_withdrawals = conn.execute(
            "SELECT COUNT(*) AS cnt, ISNULL(SUM(CAST(amount AS FLOAT)), 0) AS total "
            "FROM withdrawal_requests WHERE status='pending'"
        ).fetchone()

        # Program stats
        active_programs = conn.execute(
            "SELECT COUNT(*) AS cnt FROM programs WHERE is_active=1"
        ).fetchone()["cnt"]
        pending_enrollments = conn.execute(
            "SELECT COUNT(*) AS cnt FROM customer_accounts WHERE program_status='unconfirmed'"
        ).fetchone()["cnt"]

        # Email stats
        total_emails = conn.execute("SELECT COUNT(*) AS cnt FROM emails").fetchone()["cnt"]
        total_campaigns = conn.execute("SELECT COUNT(*) AS cnt FROM campaigns").fetchone()["cnt"]

        # Trading volume
        total_volume = conn.execute(
            "SELECT ISNULL(SUM(CAST(total_volume AS FLOAT)), 0) AS total FROM commission_records"
        ).fetchone()["total"]
        total_commission = conn.execute(
            "SELECT ISNULL(SUM(CAST(total_commission AS FLOAT)), 0) AS total FROM commission_records"
        ).fetchone()["total"]

    return {
        "customers": {
            "total": total_customers,
            "new_30d": new_customers_30d,
            "new_7d": new_customers_7d,
            "active_accounts": active_accounts,
        },
        "rebates": {
            "total_paid": round(total_rebate_paid, 2),
            "this_month": round(rebate_this_month, 2),
        },
        "wallet": {
            "total_balance": round(total_wallet_balance, 2),
            "pending_withdrawals_count": pending_withdrawals["cnt"],
            "pending_withdrawals_amount": round(pending_withdrawals["total"], 2),
        },
        "programs": {
            "active": active_programs,
            "pending_enrollments": pending_enrollments,
        },
        "emails": {
            "total_sent": total_emails,
            "total_campaigns": total_campaigns,
        },
        "trading": {
            "total_volume": round(total_volume, 2),
            "total_commission": round(total_commission, 2),
        },
    }


@router.get("/trends/customers")
async def api_customer_trends(request: Request, days: int = Query(90, le=365)):
    """Customer registration trend by day."""
    _require_admin(request)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT CAST(created_at AS DATE) AS dt, COUNT(*) AS cnt "
            "FROM customers WHERE created_at >= DATEADD(DAY, ?, GETDATE()) "
            "GROUP BY CAST(created_at AS DATE) ORDER BY dt",
            (-days,),
        ).fetchall()
    return [{"date": str(r["dt"]), "count": r["cnt"]} for r in rows]


@router.get("/trends/rebates")
async def api_rebate_trends(request: Request, months: int = Query(12, le=24)):
    """Rebate amount trend by month."""
    _require_admin(request)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT FORMAT(rb.period_date, 'yyyy-MM') AS month, "
            "       SUM(CAST(rr.rebate_amount AS FLOAT)) AS total, "
            "       COUNT(*) AS records "
            "FROM rebate_records rr "
            "JOIN rebate_batches rb ON rb.id = rr.batch_id "
            "WHERE rb.period_date >= DATEADD(MONTH, ?, GETDATE()) "
            "GROUP BY FORMAT(rb.period_date, 'yyyy-MM') "
            "ORDER BY month",
            (-months,),
        ).fetchall()
    return [{"month": r["month"], "total": round(r["total"], 2), "records": r["records"]} for r in rows]


@router.get("/trends/volume")
async def api_volume_trends(request: Request, months: int = Query(12, le=24)):
    """Trading volume trend by month."""
    _require_admin(request)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT FORMAT(trading_date, 'yyyy-MM') AS month, "
            "       SUM(CAST(total_volume AS FLOAT)) AS volume, "
            "       SUM(CAST(total_commission AS FLOAT)) AS commission "
            "FROM commission_records "
            "WHERE trading_date >= DATEADD(MONTH, ?, GETDATE()) "
            "GROUP BY FORMAT(trading_date, 'yyyy-MM') "
            "ORDER BY month",
            (-months,),
        ).fetchall()
    return [{"month": r["month"], "volume": round(r["volume"], 2),
             "commission": round(r["commission"], 2)} for r in rows]


@router.get("/programs/performance")
async def api_program_performance(request: Request):
    """Program performance — enrollment count, rebate total, volume."""
    _require_admin(request)
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT p.id, p.name, p.type, p.is_active,
                   COUNT(DISTINCT ca.id) AS enrolled_accounts,
                   ISNULL(SUM(CAST(rr.rebate_amount AS FLOAT)), 0) AS total_rebate,
                   ISNULL(SUM(CAST(rr.total_volume AS FLOAT)), 0) AS total_volume
            FROM programs p
            LEFT JOIN customer_accounts ca ON ca.program_id = p.id AND ca.program_status='confirmed'
            LEFT JOIN rebate_records rr ON rr.customer_account_id = ca.id
            GROUP BY p.id, p.name, p.type, p.is_active
            ORDER BY total_rebate DESC
        """).fetchall()
    return [dict(r) for r in rows]


@router.get("/brokers/performance")
async def api_broker_performance(request: Request):
    """Broker performance — accounts, volume, rebate."""
    _require_admin(request)
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT b.id, b.name, b.slug,
                   COUNT(DISTINCT ca.id) AS total_accounts,
                   COUNT(DISTINCT CASE WHEN ca.client_status='active' THEN ca.id END) AS active_accounts,
                   ISNULL(SUM(CAST(cr.total_volume AS FLOAT)), 0) AS total_volume,
                   ISNULL(SUM(CAST(cr.total_commission AS FLOAT)), 0) AS total_commission
            FROM brokers b
            LEFT JOIN customer_accounts ca ON ca.broker_id = b.id
            LEFT JOIN trading_accounts ta ON ta.customer_account_id = ca.id
            LEFT JOIN commission_records cr ON cr.trading_account = ta.trading_account
            GROUP BY b.id, b.name, b.slug
            ORDER BY total_volume DESC
        """).fetchall()
    return [dict(r) for r in rows]


@router.get("/wallet/summary")
async def api_wallet_summary(request: Request):
    """Wallet financial summary."""
    _require_admin(request)
    with get_conn() as conn:
        # Credits by type
        credits = conn.execute("""
            SELECT tx_type,
                   COUNT(*) AS cnt,
                   SUM(CAST(amount AS FLOAT)) AS total
            FROM wallet_transactions
            WHERE amount > 0 AND status='completed'
            GROUP BY tx_type
        """).fetchall()

        # Withdrawals by status
        withdrawals = conn.execute("""
            SELECT status,
                   COUNT(*) AS cnt,
                   SUM(CAST(amount AS FLOAT)) AS total
            FROM withdrawal_requests
            GROUP BY status
        """).fetchall()

        # Monthly wallet activity
        monthly = conn.execute("""
            SELECT FORMAT(created_at, 'yyyy-MM') AS month,
                   SUM(CASE WHEN amount > 0 THEN CAST(amount AS FLOAT) ELSE 0 END) AS credits,
                   SUM(CASE WHEN amount < 0 THEN ABS(CAST(amount AS FLOAT)) ELSE 0 END) AS debits
            FROM wallet_transactions
            WHERE status='completed' AND created_at >= DATEADD(MONTH, -12, GETDATE())
            GROUP BY FORMAT(created_at, 'yyyy-MM')
            ORDER BY month
        """).fetchall()

    return {
        "credits_by_type": [dict(r) for r in credits],
        "withdrawals_by_status": [dict(r) for r in withdrawals],
        "monthly_activity": [dict(r) for r in monthly],
    }


@router.get("/top-customers")
async def api_top_customers(request: Request, limit: int = Query(20, le=100)):
    """Top customers by trading volume."""
    _require_admin(request)
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT TOP (?) c.id, c.login_email, c.name, c.created_at,
                   ISNULL(SUM(CAST(rr.total_volume AS FLOAT)), 0) AS total_volume,
                   ISNULL(SUM(CAST(rr.rebate_amount AS FLOAT)), 0) AS total_rebate,
                   COUNT(DISTINCT ca.id) AS accounts,
                   ISNULL(cw.balance, 0) AS wallet_balance
            FROM customers c
            LEFT JOIN customer_accounts ca ON ca.customer_id = c.id
            LEFT JOIN rebate_records rr ON rr.customer_account_id = ca.id
            LEFT JOIN customer_wallets cw ON cw.customer_id = c.id
            GROUP BY c.id, c.login_email, c.name, c.created_at, cw.balance
            ORDER BY total_volume DESC
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]
