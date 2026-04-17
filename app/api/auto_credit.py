"""Auto-credit rebates to customer wallets."""
import structlog
from fastapi import APIRouter, HTTPException, Request

from app.db.connection import get_conn
from app.services.wallet_service import credit_wallet
from app.utils.audit import log_action

router = APIRouter(prefix="/api/rebate", tags=["auto-credit"])
logger = structlog.get_logger(__name__)


def _require_admin(request: Request) -> str:
    user = request.session.get("user")
    if not user:
        raise HTTPException(403, "Admin required")
    return user


@router.post("/batches/{batch_id}/auto-credit")
async def api_auto_credit_batch(batch_id: int, request: Request):
    """Auto-credit all rebate records in a batch to customer wallets.

    For each rebate_record with a linked customer, credits the rebate_amount
    to their wallet as a 'rebate_credit' transaction.

    Only processes confirmed batches that haven't been auto-credited yet.
    """
    admin = _require_admin(request)

    with get_conn() as conn:
        batch = conn.execute(
            "SELECT * FROM rebate_batches WHERE id=?", (batch_id,)
        ).fetchone()
        if not batch:
            raise HTTPException(404, "Batch not found")
        if batch["status"] == "draft":
            raise HTTPException(400, "Batch must be confirmed first")

        # Check auto_credited column exists and value
        auto_credited = batch.get("auto_credited", 0)
        if auto_credited:
            raise HTTPException(400, "Batch has already been auto-credited")

        # Get all rebate records with customer linkage
        records = conn.execute("""
            SELECT rr.id, rr.rebate_amount, rr.customer_account_id,
                   ca.customer_id,
                   c.login_email
            FROM rebate_records rr
            JOIN customer_accounts ca ON ca.id = rr.customer_account_id
            LEFT JOIN customers c ON c.id = ca.customer_id
            WHERE rr.batch_id = ? AND rr.rebate_amount > 0 AND ca.customer_id IS NOT NULL
        """, (batch_id,)).fetchall()

    if not records:
        raise HTTPException(400, "No eligible records to credit (no linked customers)")

    credited = 0
    skipped = 0
    errors = []
    total_amount = 0.0

    for rec in records:
        try:
            amount = float(rec["rebate_amount"])
            if amount <= 0:
                skipped += 1
                continue

            credit_wallet(
                rec["customer_id"],
                amount,
                "rebate_credit",
                reference_type="rebate_record",
                reference_id=rec["id"],
                description=f"Rebate batch #{batch_id} — {rec.get('login_email', '')}",
                created_by=admin,
            )
            credited += 1
            total_amount += amount
        except Exception as e:
            errors.append({"record_id": rec["id"], "error": str(e)})
            logger.warning("auto_credit.error", record_id=rec["id"], error=str(e))

    # Mark batch as auto-credited
    with get_conn() as conn:
        conn.execute(
            "UPDATE rebate_batches SET auto_credited=1 WHERE id=?",
            (batch_id,),
        )

    log_action(admin, "rebate.auto_credit", entity_type="rebate_batch",
               entity_id=str(batch_id),
               detail={"credited": credited, "skipped": skipped,
                        "errors": len(errors), "total_amount": round(total_amount, 2)})

    return {
        "ok": True,
        "credited": credited,
        "skipped": skipped,
        "errors": errors[:10],  # limit error details
        "total_amount": round(total_amount, 2),
    }


@router.get("/batches/{batch_id}/credit-preview")
async def api_credit_preview(batch_id: int, request: Request):
    """Preview which customers would receive wallet credit from this batch."""
    _require_admin(request)

    with get_conn() as conn:
        batch = conn.execute(
            "SELECT * FROM rebate_batches WHERE id=?", (batch_id,)
        ).fetchone()
        if not batch:
            raise HTTPException(404, "Batch not found")

        records = conn.execute("""
            SELECT rr.id, rr.rebate_amount, rr.customer_account_id,
                   ca.customer_id, ca.broker_email,
                   c.login_email, c.name AS customer_name,
                   ISNULL(cw.balance, 0) AS current_balance,
                   b.name AS broker_name
            FROM rebate_records rr
            JOIN customer_accounts ca ON ca.id = rr.customer_account_id
            LEFT JOIN customers c ON c.id = ca.customer_id
            LEFT JOIN customer_wallets cw ON cw.customer_id = ca.customer_id
            LEFT JOIN brokers b ON b.id = ca.broker_id
            WHERE rr.batch_id = ? AND rr.rebate_amount > 0
            ORDER BY rr.rebate_amount DESC
        """, (batch_id,)).fetchall()

    eligible = []
    no_customer = []
    total = 0.0

    for rec in records:
        d = dict(rec)
        if rec["customer_id"]:
            eligible.append(d)
            total += float(rec["rebate_amount"])
        else:
            no_customer.append(d)

    return {
        "batch": dict(batch),
        "already_credited": bool(batch.get("auto_credited", 0)),
        "eligible": eligible,
        "no_customer": no_customer,
        "total_amount": round(total, 2),
        "eligible_count": len(eligible),
    }


@router.get("/credit-history")
async def api_credit_history(request: Request):
    """List batches with their auto-credit status."""
    _require_admin(request)

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT rb.id, rb.period_date, rb.status, rb.total_rows,
                   rb.total_amount, rb.created_at, rb.created_by,
                   ISNULL(rb.auto_credited, 0) AS auto_credited,
                   ISNULL(rb.broker, 'vantage') AS broker,
                   (SELECT COUNT(*) FROM rebate_records rr
                    JOIN customer_accounts ca ON ca.id=rr.customer_account_id
                    WHERE rr.batch_id=rb.id AND ca.customer_id IS NOT NULL
                    AND rr.rebate_amount > 0) AS eligible_credits,
                   (SELECT ISNULL(SUM(CAST(rr2.rebate_amount AS FLOAT)), 0)
                    FROM rebate_records rr2
                    JOIN customer_accounts ca2 ON ca2.id=rr2.customer_account_id
                    WHERE rr2.batch_id=rb.id AND ca2.customer_id IS NOT NULL
                    AND rr2.rebate_amount > 0) AS eligible_amount
            FROM rebate_batches rb
            ORDER BY rb.created_at DESC
        """).fetchall()

    return [dict(r) for r in rows]
