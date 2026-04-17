"""
bonus_payment.py — Manage bonus milestones (Program 15).

Calculation logic:
  1. customer_accounts WHERE program_id=15, program_status='confirmed'
  2. SUM(hang_hoa_lot) from rebate_records JOIN rebate_batches by month
  3. Find highest tier reached (target_lot <= total_lots, reward_type='bonus_usd')
  4. "Pending" = tier reached AND no program_events(event_type='bonus_paid')
     for that (customer_account_id, tier_id, year, month) pair

Mark paid: INSERT into program_events with event_type='bonus_paid'
"""
import csv
import os
from datetime import date
from pathlib import Path

import structlog

from app.db.connection import get_conn

logger = structlog.get_logger(__name__)

OUTPUT_BASE = Path(os.environ.get("EXPORT_BASE", "f:/Tradingbonushub/exports"))
PROGRAM_ID = 15


# ── Read ───────────────────────────────────────────────────────────────────────

def get_pending_bonuses(year: int, month: int) -> list[dict]:
    """
    Calculate the list of pending bonus payments for month year/month.

    Flow:
      1. customer_accounts WHERE program_id=15, program_status='confirmed'
      2. SUM(hang_hoa_lot) from rebate_records JOIN rebate_batches by month
      3. Find highest tier reached (target_lot <= total_lots)
      4. Exclude already-paid via program_events(event_type='bonus_paid') for that tier+period
    """
    sql = """
        WITH confirmed_accounts AS (
            SELECT
                ca.id            AS customer_account_id,
                ca.use_id,
                ca.client_name,
                ca.broker_email AS rebate_account,
                ca.ib_number,
                ca.broker_id
            FROM customer_accounts ca
            WHERE ca.program_id       = ?
              AND ca.program_status   = 'confirmed'
        ),
        monthly_lots AS (
            SELECT
                rr.customer_account_id,
                SUM(rr.hang_hoa_lot) AS total_lots
            FROM rebate_records rr
            JOIN rebate_batches rb ON rb.id = rr.batch_id
            WHERE YEAR(rb.period_date)  = ?
              AND MONTH(rb.period_date) = ?
            GROUP BY rr.customer_account_id
        ),
        tiers AS (
            SELECT id AS tier_id, tier_number, target_lot, reward_value, label
            FROM program_tiers
            WHERE program_id  = ?
              AND reward_type = 'bonus_usd'
        ),
        account_with_lots AS (
            SELECT
                ca.customer_account_id,
                ca.use_id,
                ca.client_name,
                ca.rebate_account,
                ca.ib_number,
                ca.broker_id,
                ml.total_lots
            FROM confirmed_accounts ca
            JOIN monthly_lots ml ON ml.customer_account_id = ca.customer_account_id
        ),
        best_target AS (
            SELECT
                awl.customer_account_id,
                MAX(t.target_lot) AS reached_target
            FROM account_with_lots awl
            JOIN tiers t ON t.target_lot <= awl.total_lots
            GROUP BY awl.customer_account_id
        )
        SELECT
            awl.customer_account_id,
            awl.use_id,
            awl.client_name,
            awl.rebate_account,
            awl.ib_number,
            awl.total_lots,
            t.tier_id,
            t.tier_number,
            t.target_lot,
            t.reward_value  AS bonus_usd,
            t.label         AS tier_label,
            i.ib_name
        FROM account_with_lots awl
        JOIN best_target bt ON bt.customer_account_id = awl.customer_account_id
        JOIN tiers t        ON t.target_lot = bt.reached_target
        LEFT JOIN ibs i     ON i.ib_number = awl.ib_number AND i.broker_id = awl.broker_id
        WHERE NOT EXISTS (
            SELECT 1 FROM program_events pe
            WHERE pe.customer_account_id = awl.customer_account_id
              AND pe.program_tier_id     = t.tier_id
              AND pe.event_type          = 'bonus_paid'
              AND YEAR(pe.period_date)   = ?
              AND MONTH(pe.period_date)  = ?
        )
        ORDER BY awl.ib_number, awl.use_id
    """
    params = [PROGRAM_ID, year, month, PROGRAM_ID, year, month]

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    return [dict(r) for r in rows]


def get_bonus_summary(year: int, month: int) -> dict:
    """Monthly bonus summary: total amount, number of customers, breakdown by tier."""
    bonuses = get_pending_bonuses(year, month)
    total   = sum(b["bonus_usd"] for b in bonuses)

    tier_breakdown: dict[str, dict] = {}
    for b in bonuses:
        label = b["tier_label"]
        if label not in tier_breakdown:
            tier_breakdown[label] = {"count": 0, "amount": 0.0,
                                     "target_lot": b["target_lot"]}
        tier_breakdown[label]["count"]  += 1
        tier_breakdown[label]["amount"] += b["bonus_usd"]

    return {
        "year": year, "month": month,
        "total_pending": len(bonuses),
        "total_amount_usd": round(total, 2),
        "tier_breakdown": tier_breakdown,
        "items": bonuses,
    }


# ── Mark paid ──────────────────────────────────────────────────────────────────

def mark_bonuses_paid(items: list[dict], paid_by: str) -> dict:
    """
    Mark bonuses as paid by inserting program_events + credit wallet.

    items: list of {customer_account_id, tier_id, year, month, total_lots, bonus_usd}
    paid_by: name of the admin who confirmed payment
    """
    if not items:
        return {"inserted": 0}

    inserted = 0
    with get_conn() as conn:
        for item in items:
            period = date(item["year"], item["month"], 1)
            # Prevent duplicate: skip if already marked paid for this tier+period
            existing = conn.execute(
                """
                SELECT 1 FROM program_events
                WHERE customer_account_id = ?
                  AND program_tier_id     = ?
                  AND event_type          = 'bonus_paid'
                  AND YEAR(period_date)   = ?
                  AND MONTH(period_date)  = ?
                """,
                [item["customer_account_id"], item["tier_id"],
                 item["year"], item["month"]],
            ).fetchone()
            if existing:
                continue
            conn.execute(
                """
                INSERT INTO program_events
                    (customer_account_id, program_tier_id, event_type,
                     lots_at_event, amount_usd, period_date, note)
                VALUES (?, ?, 'bonus_paid', ?, ?, ?, ?)
                """,
                [
                    item["customer_account_id"],
                    item["tier_id"],
                    item.get("total_lots", 0),
                    item["bonus_usd"],
                    period,
                    f"Bonus milestone Program 15 — Month {item['month']}/{item['year']} — Reached {item.get('total_lots',0):.2f} lots → ${item['bonus_usd']:.2f} — Paid by {paid_by}",
                ],
            )
            inserted += 1

    logger.info("bonuses marked paid", inserted=inserted, paid_by=paid_by)
    return {"inserted": inserted}


# ── Export ─────────────────────────────────────────────────────────────────────

def export_bonus_csv(year: int, month: int) -> dict:
    """
    Export CSV of pending bonuses for month year/month.
    File: exports/bonus_YYYY_MM/bonus_pending_YYYYMM.csv
    """
    bonuses = get_pending_bonuses(year, month)
    if not bonuses:
        return {"file": None, "rows": 0,
                "message": f"No pending bonuses for {year}/{month:02d}"}

    folder   = OUTPUT_BASE / f"bonus_{year}_{month:02d}"
    folder.mkdir(parents=True, exist_ok=True)
    filepath = folder / f"bonus_pending_{year}{month:02d}.csv"

    fieldnames = [
        "customer_account_id", "use_id", "client_name",
        "ib_number", "ib_name",
        "tier_label", "target_lot", "total_lots",
        "bonus_usd", "rebate_account",
    ]

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(bonuses)

    total = sum(b["bonus_usd"] for b in bonuses)
    logger.info("bonus export done",
                file=str(filepath), rows=len(bonuses), total_usd=total)

    return {
        "file": str(filepath),
        "rows": len(bonuses),
        "total_amount_usd": round(total, 2),
    }
