"""
Delete all rebate_records and recalculate from commission_records.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db.connection import get_conn
from app.services.rebate_calculator import run_daily_rebate
from datetime import date

# Step 1: Find all distinct dates in commission_records
with get_conn() as conn:
    date_rows = conn.execute(
        "SELECT DISTINCT CAST(uploaded_at AS DATE) AS d FROM commission_records ORDER BY d"
    ).fetchall()
    dates = [r["d"] for r in date_rows]
    print(f"Found {len(dates)} distinct dates in commission_records: {dates}")

    # Delete all rebate_records
    deleted = conn.execute("DELETE FROM rebate_records").rowcount
    print(f"Deleted {deleted} rebate_records")

    # Also delete orphaned rebate_batches (daily_auto ones with 0 rows)
    deleted_b = conn.execute(
        "DELETE FROM rebate_batches WHERE created_by='daily_auto' AND (total_rows=0 OR total_rows IS NULL)"
    ).rowcount
    print(f"Deleted {deleted_b} empty rebate_batches")

print()
print("=== Recalculating ===")
for d in dates:
    if isinstance(d, str):
        d = date.fromisoformat(d)
    result = run_daily_rebate(d)
    p15 = result["program_15"]
    p11 = result["program_11"]
    print(f"  {d} | P11: {p11['processed']} records, ${p11['total_rebate']}"
          f" | P15: {p15['processed']} records, ${p15['total_rebate']}")

print()
print("=== Summary ===")
with get_conn() as conn:
    r = conn.execute(
        """SELECT COUNT(*) AS cnt, SUM(rebate_amount) AS total
           FROM rebate_records"""
    ).fetchone()
    print(f"  rebate_records: {r['cnt']} rows, total rebate = ${r['total']:.2f}")

    r2 = conn.execute(
        """SELECT YEAR(rb.period_date) AS y, MONTH(rb.period_date) AS m,
                  SUM(rr.rebate_amount) AS total
           FROM rebate_records rr
           JOIN rebate_batches rb ON rb.id=rr.batch_id
           GROUP BY YEAR(rb.period_date), MONTH(rb.period_date)
           ORDER BY y, m"""
    ).fetchall()
    for row in r2:
        print(f"  {row['y']}-{row['m']:02d}: ${row['total']:.2f}")
