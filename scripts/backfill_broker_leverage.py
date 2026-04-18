"""One-off: copy the most common non-empty program leverage into
brokers.leverage for brokers that still have a NULL/empty value.

Idempotent — safe to re-run. Skips brokers that already have a leverage set.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.db.connection import get_conn


with get_conn() as conn:
    before = conn.execute(
        "SELECT id, slug, leverage FROM brokers ORDER BY display_order"
    ).fetchall()
    print("BEFORE:")
    for b in before:
        print(f"  {b['slug']:<14} leverage={b['leverage']!r}")

    conn.execute(
        """UPDATE b
           SET b.leverage = src.leverage
           FROM brokers b
           CROSS APPLY (
               SELECT TOP 1 p.leverage
               FROM programs p
               JOIN program_brokers pb ON pb.program_id = p.id
               WHERE pb.broker_id = b.id
                 AND p.leverage IS NOT NULL
                 AND LTRIM(RTRIM(p.leverage)) <> ''
               GROUP BY p.leverage
               ORDER BY COUNT(*) DESC
           ) src
           WHERE b.leverage IS NULL OR LTRIM(RTRIM(b.leverage)) = ''"""
    )

    after = conn.execute(
        "SELECT id, slug, leverage FROM brokers ORDER BY display_order"
    ).fetchall()
    print("\nAFTER:")
    for b in after:
        print(f"  {b['slug']:<14} leverage={b['leverage']!r}")
