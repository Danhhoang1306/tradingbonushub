"""
Delete program_events for Feb 2026 for BVL and re-run rebate for 1-28/2/2026.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import date
from app.db.connection import get_conn
from app.services.rebate_calculator import run_daily_rebate

USE_ID = "9220968"

# 1. Delete program_events for Feb 2026 for BVL
with get_conn() as conn:
    # Get customer_account_id
    ca = conn.execute(
        "SELECT id FROM customer_accounts WHERE use_id=?", (USE_ID,)
    ).fetchone()
    if not ca:
        print("customer_account not found!")
        sys.exit(1)
    ca_id = ca["id"]
    print(f"customer_account_id = {ca_id}")

    # Delete program_events for Feb 2026
    deleted = conn.execute(
        """
        DELETE FROM program_events
        WHERE customer_account_id = ?
          AND event_type = 'bonus_milestone'
          AND YEAR(period_date)  = 2026
          AND MONTH(period_date) = 2
        """,
        (ca_id,),
    ).rowcount
    print(f"Deleted {deleted} program_events (Feb 2026)")

    # Delete rebate_records in daily batches for Feb 2026
    deleted_rr = conn.execute(
        """
        DELETE rr FROM rebate_records rr
        JOIN rebate_batches rb ON rr.batch_id = rb.id
        WHERE rr.customer_account_id = ?
          AND rb.created_by = 'daily_auto'
          AND YEAR(rb.period_date) = 2026
          AND MONTH(rb.period_date) = 2
        """,
        (ca_id,),
    ).rowcount
    print(f"Deleted {deleted_rr} rebate_records (Feb 2026)")

    # Delete monthly_stats for Feb 2026
    deleted_ms = conn.execute(
        """
        DELETE FROM customer_monthly_stats
        WHERE use_id = ? AND year = 2026 AND month = 2
        """,
        (USE_ID,),
    ).rowcount
    print(f"Deleted {deleted_ms} monthly_stats rows (Feb 2026)")

print()
print("=== Rerunning rebate Feb 1-28, 2026 ===")
for day in range(1, 29):
    d = date(2026, 2, day)
    result = run_daily_rebate(d)
    p15 = result["program_15"]
    if p15["processed"] > 0:
        d_info = p15["details"][0] if p15["details"] else {}
        bonuses = d_info.get("bonus_events", [])
        print(
            f"  {d} | hang_hoa_today={d_info.get('hang_hoa_lot_today', 0):.2f}"
            f" | rebate_fix={d_info.get('rebate_fix', 0):.2f}"
            f" | bonuses={bonuses}"
        )
    else:
        print(f"  {d} | No STP data")

print()
print("=== program_events Feb 2026 ===")
with get_conn() as conn:
    rows = conn.execute(
        """
        SELECT pe.period_date, pt.target_lot, pe.amount_usd, pe.lots_at_event
        FROM program_events pe
        JOIN program_tiers pt ON pt.id = pe.program_tier_id
        WHERE pe.customer_account_id = ?
          AND pe.event_type = 'bonus_milestone'
          AND YEAR(pe.period_date)  = 2026
          AND MONTH(pe.period_date) = 2
        ORDER BY pe.period_date, pt.target_lot
        """,
        (ca_id,),
    ).fetchall()
    if rows:
        for r in rows:
            print(f"  {r['period_date']} | {r['target_lot']} lots -> ${r['amount_usd']} | lots_at_event={r['lots_at_event']:.2f}")
    else:
        print("  No events found!")
