"""Seed a demo customer account with 12 months of random rebate_records data.

Run from project root:
    python scripts/seed_demo_commission.py

Creates:
  - customers row: demo@tradingbonushub.com
  - customer_accounts row linked to Vantage broker
  - 12 rebate_batches (one per past month) with status='paid'
  - 12 rebate_records with randomized commission + per-asset breakdown

Login to portal with:  demo@tradingbonushub.com / demo1234
"""
import hashlib
import os
import random
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_conn

DEMO_EMAIL = "demo@tradingbonushub.com"
DEMO_NAME  = "Demo Trader"
DEMO_USE_ID = "DEM-0001"
DEMO_PASSWORD = "demo1234"


def _hash_pw(pw: str) -> str:
    import os as _os
    salt = _os.urandom(16)
    k = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 100_000)
    return salt.hex() + ":" + k.hex()


def seed() -> None:
    with get_conn() as conn:
        # ── 1. Customer ────────────────────────────────────────────────────────
        row = conn.execute(
            "SELECT id FROM customers WHERE login_email=?", (DEMO_EMAIL,)
        ).fetchone()
        if row:
            customer_id = row["id"]
            print(f"  Customer already exists (id={customer_id})")
        else:
            row = conn.execute(
                "INSERT INTO customers (login_email, name, password_hash, is_verified, must_change_password) "
                "OUTPUT INSERTED.id VALUES (?,?,?,1,0)",
                (DEMO_EMAIL, DEMO_NAME, _hash_pw(DEMO_PASSWORD)),
            ).fetchone()
            customer_id = row["id"]
            print(f"  Created customer id={customer_id}")

        # ── 2. Broker (Vantage) ────────────────────────────────────────────────
        broker = conn.execute(
            "SELECT id FROM brokers WHERE slug='vantage'"
        ).fetchone()
        if not broker:
            print("ERROR: Vantage broker not found. Run the app once to seed brokers.")
            return
        broker_id = broker["id"]

        # ── 3. customer_account ────────────────────────────────────────────────
        ca = conn.execute(
            "SELECT id FROM customer_accounts WHERE customer_id=? AND broker_id=?",
            (customer_id, broker_id),
        ).fetchone()
        if ca:
            ca_id = ca["id"]
            print(f"  customer_account already exists (id={ca_id})")
        else:
            ca = conn.execute(
                "INSERT INTO customer_accounts "
                "(customer_id, broker_id, use_id, client_name, client_status, customer_linked_at) "
                "OUTPUT INSERTED.id VALUES (?,?,?,?,'active',GETDATE())",
                (customer_id, broker_id, DEMO_USE_ID, DEMO_NAME),
            ).fetchone()
            ca_id = ca["id"]
            print(f"  Created customer_account id={ca_id}")

        # ── 4. 12 months of rebate_batches + rebate_records ───────────────────
        today = date.today()
        random.seed(42)  # reproducible

        # Cumulative lots for progress bar demo — build up toward 50-lot milestone
        base_lots = 0.0

        for i in range(12, 0, -1):
            # compute year/month going back i months
            m = today.month - i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            period = date(y, m, 1)

            # Check existing batch
            batch = conn.execute(
                "SELECT id FROM rebate_batches WHERE period_date=? AND created_by='demo_seed'",
                (period.isoformat(),),
            ).fetchone()
            if not batch:
                batch = conn.execute(
                    "INSERT INTO rebate_batches "
                    "(period_date, created_by, status, notes) "
                    "OUTPUT INSERTED.id VALUES (?,?,?,?)",
                    (period.isoformat(), "demo_seed", "paid",
                     f"Demo — Month {m}/{y}"),
                ).fetchone()
            batch_id = batch["id"]

            # Random per-instrument data
            fx_lot       = round(random.uniform(5, 35), 2)
            hh_lot       = round(random.uniform(2, 18), 2)
            idx_lot      = round(random.uniform(0, 8),  2)
            crypto_lot   = round(random.uniform(0, 4),  2)
            total_volume = round(fx_lot + hh_lot + idx_lot + crypto_lot, 2)

            fx_comm     = round(fx_lot     * random.uniform(3.5, 5.5), 2)
            hh_comm     = round(hh_lot     * random.uniform(4.0, 7.0), 2)
            idx_comm    = round(idx_lot    * random.uniform(2.0, 4.0), 2)
            crypto_comm = round(crypto_lot * random.uniform(5.0, 10.0), 2)
            total_comm  = round(fx_comm + hh_comm + idx_comm + crypto_comm, 2)
            rebate_amt  = round(total_comm * 0.60, 2)

            base_lots += total_volume

            # Upsert rebate_record
            existing = conn.execute(
                "SELECT id FROM rebate_records WHERE batch_id=? AND customer_account_id=?",
                (batch_id, ca_id),
            ).fetchone()
            if not existing:
                conn.execute(
                    """INSERT INTO rebate_records
                       (batch_id, customer_account_id, program_tier_id, rebate_amount, status,
                        total_volume, total_commission,
                        fx_lot, fx_commission,
                        hang_hoa_lot, hang_hoa_commission,
                        index_lot, index_commission,
                        crypto_lot, crypto_commission)
                       VALUES (?,?,NULL,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (batch_id, ca_id, rebate_amt, "paid",
                     total_volume, total_comm,
                     fx_lot, fx_comm,
                     hh_lot, hh_comm,
                     idx_lot, idx_comm,
                     crypto_lot, crypto_comm),
                )
                print(f"  {period}: {total_volume:.1f} lots | ${total_comm:.2f} comm | ${rebate_amt:.2f} rebate")
            else:
                print(f"  {period}: already seeded (skipped)")

    print(f"\nDone!")
    print(f"  Login: {DEMO_EMAIL} / {DEMO_PASSWORD}")
    print(f"  customer_account_id: {ca_id}")


if __name__ == "__main__":
    seed()
