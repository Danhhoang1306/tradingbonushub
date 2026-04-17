"""
vantage_exporter.py — Export daily rebate files in Vantage bulk transfer format.

Output directory structure:
    rebate_YYYYMMDD/
        IB_20793068_Thi_Hoa_Nguyen/
            vantage_20793068_YYYYMMDD_01.csv
            vantage_20793068_YYYYMMDD_02.csv   <- if > 50 rows
        IB_16507592_Nguyen_Van_An/
            vantage_16507592_YYYYMMDD_01.csv

CSV format (Vantage standard):
    To Account,Amount
    22733415,210.0
    ...  (max 50 rows/file)

Filters from customer_accounts:
    broker_id = 6 (Vantage)
    pending_program_id IS NOT NULL
    program_status = 'confirmed'
    broker_email IS NOT NULL

Rebate amounts come from rebate_records batch for target_date.
"""
import csv
import math
import os
from datetime import date, timedelta
from pathlib import Path

import structlog

from app.db.connection import get_conn

logger = structlog.get_logger(__name__)

VANTAGE_BROKER_ID = 6
MAX_ROWS_PER_FILE  = 50
OUTPUT_BASE        = Path(os.environ.get("EXPORT_BASE", "f:/Tradingbonushub/exports"))

CSV_HEADER_ROW = (
    'To Account',
    'Amount',
    '*Please ensure the format follows the below guidelines:\n'
    '1. Fill in the account number as Trading Account/Rebate Account.\n'
    '2. The currency of the transfer-in account must be the same as '
    'the currency of the transfer-out account.\n'
    '3. Enter the amount as a number only.\n'
    '4. Only fill in transfer records in columns A and B.\n'
    '5. A maximum of 50 transfer records can be entered.',
)


# ── Data fetching ──────────────────────────────────────────────────────────────

def _get_eligible_accounts(conn) -> list[dict]:
    """
    Get the list of eligible Vantage customers for rebate.
    Conditions:
        broker_id = 6
        pending_program_id IS NOT NULL
        program_status = 'confirmed'
        broker_email IS NOT NULL AND broker_email != ''
    """
    rows = conn.execute(
        """
        SELECT
            ca.id               AS customer_account_id,
            ca.use_id,
            ca.ib_number,
            ca.client_name,
            ca.broker_email,
            ca.pending_program_id,
            i.ib_name
        FROM customer_accounts ca
        LEFT JOIN ibs i
            ON i.ib_number = ca.ib_number AND i.broker_id = ?
        WHERE ca.broker_id = ?
          AND ca.pending_program_id IS NOT NULL
          AND ca.program_status = 'confirmed'
          AND ca.broker_email IS NOT NULL
          AND ca.broker_email != ''
        ORDER BY ca.ib_number, ca.use_id
        """,
        (VANTAGE_BROKER_ID, VANTAGE_BROKER_ID),
    ).fetchall()
    return [dict(r) for r in rows]


def _get_batch_id_for_date(conn, target_date: date) -> int | None:
    """Find batch_id for target_date (created by daily_auto)."""
    row = conn.execute(
        """
        SELECT id FROM rebate_batches
        WHERE CAST(period_date AS DATE) = ? AND created_by = 'daily_auto'
        """,
        (str(target_date),),
    ).fetchone()
    return row["id"] if row else None


def _get_rebate_amounts(conn, batch_id: int, ca_ids: list[int]) -> dict[int, float]:
    """Return {customer_account_id: rebate_amount} from rebate_records."""
    if not ca_ids:
        return {}
    ph = ",".join(["?"] * len(ca_ids))
    rows = conn.execute(
        f"""
        SELECT customer_account_id, rebate_amount
        FROM rebate_records
        WHERE batch_id = ? AND customer_account_id IN ({ph})
          AND rebate_amount > 0
        """,
        [batch_id] + ca_ids,
    ).fetchall()
    return {r["customer_account_id"]: float(r["rebate_amount"]) for r in rows}


# ── File writing ───────────────────────────────────────────────────────────────

def _write_csv(filepath: Path, records: list[dict]) -> None:
    """Write one Vantage CSV file. records = [{"to_account": str, "amount": float}]"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER_ROW)
        writer.writerow([])  # blank row after header (per template)
        writer.writerow([])
        for rec in records:
            writer.writerow([rec["to_account"], rec["amount"]])


def _safe_folder_name(name: str) -> str:
    """Convert IB name to a safe folder name."""
    return name.replace(" ", "_").replace("/", "-").replace("\\", "-")


# ── Main export ────────────────────────────────────────────────────────────────

def export_vantage_rebate(target_date: date = None) -> dict:
    """
    Export Vantage rebate files for target_date.

    Args:
        target_date: date to export (default: yesterday)

    Returns:
        {
            "date": str,
            "batch_id": int,
            "root_folder": str,
            "total_accounts": int,
            "total_amount": float,
            "files": [{"ib_number": str, "ib_name": str, "file": str, "rows": int}],
            "skipped": [{"use_id": str, "reason": str}],
        }
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    log = logger.bind(date=str(target_date))
    date_str = target_date.strftime("%Y%m%d")

    with get_conn() as conn:
        # 1. Get eligible customer accounts
        accounts = _get_eligible_accounts(conn)
        if not accounts:
            log.info("No eligible Vantage accounts")
            return {"date": str(target_date), "batch_id": None,
                    "total_accounts": 0, "total_amount": 0.0,
                    "files": [], "skipped": []}

        # 2. Find batch for that date
        batch_id = _get_batch_id_for_date(conn, target_date)
        if not batch_id:
            log.info("No rebate batch found for date")
            return {"date": str(target_date), "batch_id": None,
                    "total_accounts": 0, "total_amount": 0.0,
                    "files": [], "skipped": []}

        # 3. Get rebate amounts
        ca_ids = [a["customer_account_id"] for a in accounts]
        rebate_map = _get_rebate_amounts(conn, batch_id, ca_ids)

        # 4. Combine + separate skipped customers
        eligible: list[dict] = []
        skipped:  list[dict] = []

        for acc in accounts:
            ca_id  = acc["customer_account_id"]
            amount = rebate_map.get(ca_id)
            if not amount:
                skipped.append({"use_id": acc["use_id"],
                                "client_name": acc["client_name"],
                                "reason": "No rebate record for this date"})
                continue
            eligible.append({**acc, "amount": amount})

        if not eligible:
            log.info("No rebate data for eligible accounts")
            return {"date": str(target_date), "batch_id": batch_id,
                    "total_accounts": 0, "total_amount": 0.0,
                    "files": [], "skipped": skipped}

        # 5. Group by ib_number
        ib_groups: dict[str, list] = {}
        for rec in eligible:
            ib_key = rec["ib_number"] or "NO_IB"
            ib_groups.setdefault(ib_key, []).append(rec)

        # 6. Create root folder: exports/rebate_YYYYMMDD/
        root_folder = OUTPUT_BASE / f"rebate_{date_str}"
        root_folder.mkdir(parents=True, exist_ok=True)

        files_written: list[dict] = []
        total_amount = 0.0

        for ib_number, recs in ib_groups.items():
            ib_name = recs[0].get("ib_name") or f"IB_{ib_number}"

            # Sub-folder: IB_20793068_Thi_Hoa_Nguyen/
            ib_folder = root_folder / f"IB_{ib_number}_{_safe_folder_name(ib_name)}"
            ib_folder.mkdir(parents=True, exist_ok=True)

            # Split into chunks of max 50 rows
            n_files = math.ceil(len(recs) / MAX_ROWS_PER_FILE)
            for seq in range(n_files):
                chunk = recs[seq * MAX_ROWS_PER_FILE: (seq + 1) * MAX_ROWS_PER_FILE]
                records_to_write = [
                    {"to_account": r["broker_email"], "amount": r["amount"]}
                    for r in chunk
                ]

                filename = f"vantage_{ib_number}_{date_str}_{seq + 1:02d}.csv"
                filepath = ib_folder / filename
                _write_csv(filepath, records_to_write)

                chunk_total = sum(r["amount"] for r in chunk)
                total_amount += chunk_total

                files_written.append({
                    "ib_number": ib_number,
                    "ib_name": ib_name,
                    "file": str(filepath),
                    "rows": len(chunk),
                    "amount": round(chunk_total, 2),
                })
                log.info("file written", file=filename,
                         ib=ib_number, rows=len(chunk), amount=chunk_total)

        result = {
            "date": str(target_date),
            "batch_id": batch_id,
            "root_folder": str(root_folder),
            "total_accounts": len(eligible),
            "total_amount": round(total_amount, 2),
            "files": files_written,
            "skipped": skipped,
        }
        log.info("export done", total_accounts=len(eligible),
                 total_amount=total_amount, files=len(files_written))
        return result
