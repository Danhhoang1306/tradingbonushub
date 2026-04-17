import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.db.connection import get_conn

USE_ID = "9220968"

with get_conn() as conn:
    ca = conn.execute("SELECT id FROM customer_accounts WHERE use_id=?", (USE_ID,)).fetchone()
    ca_id = ca["id"]

    print("=== rebate_records for March 2026 (per day) ===")
    rows = conn.execute(
        """
        SELECT CAST(rb.period_date AS DATE) AS d,
               rr.hang_hoa_lot, rr.total_volume, rr.rebate_amount
        FROM rebate_records rr
        JOIN rebate_batches rb ON rb.id = rr.batch_id
        WHERE rr.customer_account_id = ?
          AND YEAR(rb.period_date) = 2026 AND MONTH(rb.period_date) = 3
        ORDER BY d
        """,
        (ca_id,),
    ).fetchall()
    total_hh = 0.0; total_tv = 0.0; total_reb = 0.0
    for r in rows:
        hh = float(r["hang_hoa_lot"] or 0)
        tv = float(r["total_volume"] or 0)
        rb = float(r["rebate_amount"] or 0)
        total_hh += hh; total_tv += tv; total_reb += rb
        print(f"  {r['d']} | hang_hoa={hh:.2f} | total_vol={tv:.2f} | rebate={rb:.2f}")
    print(f"  TOTAL | hang_hoa={total_hh:.2f} | total_vol={total_tv:.2f} | rebate={total_reb:.2f}")

    print()
    print("=== customer_monthly_stats March 2026 ===")
    r = conn.execute(
        "SELECT * FROM customer_monthly_stats WHERE use_id=? AND year=2026 AND month=3",
        (USE_ID,),
    ).fetchone()
    if r:
        print(f"  monthly_hang_hoa_lot={r['monthly_hang_hoa_lot']} | monthly_rebate={r['monthly_rebate']}")
    else:
        print("  No monthly_stats for March 2026")
