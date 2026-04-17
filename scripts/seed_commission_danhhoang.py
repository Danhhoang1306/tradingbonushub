"""Seed commission history for danhhoangsmk@gmail.com.

Creates rebate_batches + rebate_records from Dec 2025 to Mar 2026.

Run:  python scripts/seed_commission_danhhoang.py
"""
import os
import random
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_conn

TARGET_EMAIL = "danhhoangsmk@gmail.com"

# Months to seed: Dec 2025 -> Apr 2026
MONTHS = [
    (date(2025, 12, 1), "paid"),
    (date(2026, 1, 1),  "paid"),
    (date(2026, 2, 1),  "paid"),
    (date(2026, 3, 1),  "paid"),
    (date(2026, 4, 1),  "pending"),
]


def seed() -> None:
    with get_conn() as conn:
        # ── 1. Find customer ──────────────────────────────────────────────
        cust = conn.execute(
            "SELECT id FROM customers WHERE login_email=?", (TARGET_EMAIL,)
        ).fetchone()
        if not cust:
            print(f"ERROR: Customer with email {TARGET_EMAIL} not found.")
            return
        customer_id = cust["id"]
        print(f"  Customer id={customer_id}")

        # ── 2. Find customer_account ──────────────────────────────────────
        ca = conn.execute(
            "SELECT id FROM customer_accounts WHERE customer_id=?",
            (customer_id,),
        ).fetchone()
        if not ca:
            print("ERROR: No customer_account found for this customer.")
            return
        ca_id = ca["id"]
        print(f"  customer_account id={ca_id}")

        # ── 3. Seed monthly data ──────────────────────────────────────────
        random.seed()  # truly random

        for period, rec_status in MONTHS:
            # Create or find batch
            batch = conn.execute(
                "SELECT id FROM rebate_batches WHERE period_date=? AND created_by='seed_danhhoang'",
                (period.isoformat(),),
            ).fetchone()
            if not batch:
                batch = conn.execute(
                    "INSERT INTO rebate_batches "
                    "(period_date, created_by, status, notes) "
                    "OUTPUT INSERTED.id VALUES (?,?,?,?)",
                    (period.isoformat(), "seed_danhhoang", rec_status,
                     f"Seed — Month {period.month}/{period.year}"),
                ).fetchone()
            batch_id = batch["id"]

            # Random per-instrument lots (from 0)
            fx_lot       = round(random.uniform(0, 30), 2)
            hh_lot       = round(random.uniform(0, 15), 2)
            idx_lot      = round(random.uniform(0, 8),  2)
            crypto_lot   = round(random.uniform(0, 5),  2)
            sharecfd_lot = round(random.uniform(0, 3),  2)
            bond_lot     = round(random.uniform(0, 2),  2)
            synthetic_lot = round(random.uniform(0, 2), 2)
            total_volume = round(fx_lot + hh_lot + idx_lot + crypto_lot
                                 + sharecfd_lot + bond_lot + synthetic_lot, 2)

            # Commission = lots * random rate per instrument
            fx_comm       = round(fx_lot       * random.uniform(3.0, 6.0), 2)
            hh_comm       = round(hh_lot       * random.uniform(4.0, 7.0), 2)
            idx_comm      = round(idx_lot      * random.uniform(2.0, 4.5), 2)
            crypto_comm   = round(crypto_lot   * random.uniform(5.0, 10.0), 2)
            sharecfd_comm = round(sharecfd_lot * random.uniform(2.0, 5.0), 2)
            bond_comm     = round(bond_lot     * random.uniform(1.5, 3.0), 2)
            synthetic_comm = round(synthetic_lot * random.uniform(2.0, 6.0), 2)
            total_comm    = round(fx_comm + hh_comm + idx_comm + crypto_comm
                                  + sharecfd_comm + bond_comm + synthetic_comm, 2)
            rebate_amt    = round(total_comm * 0.60, 2)

            # Check existing
            existing = conn.execute(
                "SELECT id FROM rebate_records WHERE batch_id=? AND customer_account_id=?",
                (batch_id, ca_id),
            ).fetchone()
            if existing:
                print(f"  {period}: already exists (skipped)")
                continue

            conn.execute(
                """INSERT INTO rebate_records
                   (batch_id, customer_account_id, program_tier_id, rebate_amount, status,
                    total_volume, total_commission,
                    fx_lot, fx_commission,
                    hang_hoa_lot, hang_hoa_commission,
                    index_lot, index_commission,
                    crypto_lot, crypto_commission,
                    sharecfd_lot, sharecfd_commission,
                    bond_lot, bond_commission,
                    synthetic_lot, synthetic_commission)
                   VALUES (?,?,NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (batch_id, ca_id, rebate_amt, rec_status,
                 total_volume, total_comm,
                 fx_lot, fx_comm,
                 hh_lot, hh_comm,
                 idx_lot, idx_comm,
                 crypto_lot, crypto_comm,
                 sharecfd_lot, sharecfd_comm,
                 bond_lot, bond_comm,
                 synthetic_lot, synthetic_comm),
            )
            print(f"  {period}: {total_volume:.1f} lots | ${total_comm:.2f} comm | ${rebate_amt:.2f} rebate")

    print("\nDone! Commission history seeded for", TARGET_EMAIL)


if __name__ == "__main__":
    seed()
