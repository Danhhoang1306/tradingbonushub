"""Rebate calculation engine + Vantage bulk-upload CSV generator.

Flow:
  1. parse_and_preview(rows, period_date) — from Excel rows → preview list (no DB write)
  2. confirm_batch(preview_rows, period_date, actor) → batch_id (saves commission_records + rebate_records)
  3. export_batch_csvs(batch_id) → list of (filename, csv_bytes)

Export rules (Vantage bulk upload format):
  - 2 columns: "To Account", "Amount"
  - Max 50 rows per file
  - Files grouped by IB; if > 50 rows → split with seq number
  - Filename: {ib_name}_{YYYYMMDD}_{seq:02d}.csv
"""
import csv
import io
import re
from datetime import datetime

import structlog

from app.db.connection import get_conn
from app.db.repositories.promotions import resolve_tier_for_volume
from app.db.repositories.rebate import (
    bulk_update_rebate_status,
    bulk_upsert_commission_records,
    create_rebate_batch,
    get_rebate_records_by_batch,
    update_batch_status,
    update_batch_totals,
    upsert_rebate_record,
)
from app.utils.rebate_columns import ASSET_KEYS as _ASSET_KEYS

logger = structlog.get_logger(__name__)

MAX_PER_FILE = 50


# ── Rebate calculation ─────────────────────────────────────────────────────────

def calc_rebate(
    total_volume: float,
    total_commission: float,
    tier: dict | None,
) -> tuple[float, float]:
    """Return (rebate_amount, rebate_rate_pct).

    tier: dict from program_tiers with keys: target_lot, reward_value, reward_type
      reward_type = 'backcom_pct' → rebate = total_commission * reward_value
      reward_type = 'bonus_usd'  → rebate = reward_value (one-time milestone)

    rebate_rate_pct is the percentage for display (e.g. 60.0 for 60%).
    """
    if not tier:
        return 0.0, 0.0
    reward_type  = str(tier.get("reward_type") or "backcom_pct")
    reward_value = float(tier.get("reward_value") or 0)
    if "backcom_pct" in reward_type:
        amount = round(total_commission * reward_value, 4)
        return amount, round(reward_value * 100, 2)
    if "bonus_usd" in reward_type:
        return round(reward_value, 4), 0.0
    return 0.0, 0.0


# ── Preview (no DB write) ──────────────────────────────────────────────────────

def parse_and_preview(raw_rows: list, period_date: str) -> dict:
    """
    Given raw_rows (parsed from Excel — field names match DB columns):
      trading_account, use_id, name, total_volume, total_commission, <instrument cols>

    Looks up customer_account info and program tiers, returns preview data.
    No DB writes.
    """
    ta_set = {r["trading_account"] for r in raw_rows}
    ta_info: dict = {}   # trading_account → enriched info

    with get_conn() as conn:
        for ta in ta_set:
            # 1. Look up trading_accounts table → customer_account_id
            ta_row = conn.execute(
                "SELECT customer_account_id FROM trading_accounts WHERE trading_account=?",
                (ta,),
            ).fetchone()

            ca = None
            if ta_row:
                ca = conn.execute(
                    """SELECT ca.id, ca.use_id, ca.ib_number, ca.program_id,
                              ca.client_name, ca.broker_id, ca.client_status,
                              c.login_email
                       FROM customer_accounts ca
                       LEFT JOIN customers c ON c.id = ca.customer_id
                       WHERE ca.id = ?""",
                    (ta_row["customer_account_id"],),
                ).fetchone()

            # 2. Fallback: match by use_id from the raw rows
            if not ca:
                uid_val = next((r.get("use_id") for r in raw_rows
                                if r["trading_account"] == ta), "")
                if uid_val:
                    ca = conn.execute(
                        """SELECT ca.id, ca.use_id, ca.ib_number, ca.program_id,
                                  ca.client_name, ca.broker_id, ca.client_status,
                                  c.login_email
                           FROM customer_accounts ca
                           LEFT JOIN customers c ON c.id = ca.customer_id
                           WHERE ca.use_id = ?""",
                        (str(uid_val),),
                    ).fetchone()

            ca_id      = ca["id"]         if ca else None
            use_id     = (ca["use_id"]    if ca else "") or ""
            ib_number  = (ca["ib_number"] if ca else "") or ""
            program_id = ca["program_id"] if ca else None
            login_email = (ca["login_email"] if ca else "") or ""

            # 3. Look up IB name via ib_number
            ib_name = ""
            ib_account_number = ib_number
            if ib_number and ca:
                ib_row = conn.execute(
                    "SELECT ib_name FROM ibs WHERE broker_id=? AND ib_number=?",
                    (ca["broker_id"], ib_number),
                ).fetchone()
                if ib_row:
                    ib_name = ib_row["ib_name"] or ""

            ta_info[ta] = {
                "customer_account_id": ca_id,
                "login_email":         login_email,
                "use_id":              use_id,
                "ib_number":           ib_account_number,
                "ib_name":             ib_name,
                "program_id":          program_id,
            }

    result_rows = []
    total_rebate = 0.0
    no_program   = 0

    # Merge rows with same (trading_account, lots_type) if not already merged
    merged: dict = {}
    names:  dict = {}
    uids:   dict = {}
    for row in raw_rows:
        key = (row["trading_account"], row.get("lots_type", "Standard"))
        if key not in merged:
            merged[key] = dict(row)
        else:
            ex = merged[key]
            ex["total_volume"]     += row["total_volume"]
            ex["total_commission"] += row["total_commission"]
            for k in _ASSET_KEYS:
                ex[k] = ex.get(k, 0) + row.get(k, 0)
        if row["trading_account"] not in names:
            names[row["trading_account"]] = row.get("name", "")
        if row["trading_account"] not in uids and row.get("use_id"):
            uids[row["trading_account"]] = row["use_id"]

    for (ta, lots_type), row in sorted(merged.items()):
        info       = ta_info.get(ta, {})
        program_id = info.get("program_id")

        tier = None
        program_name = ""
        if program_id:
            tier = resolve_tier_for_volume(program_id, row["total_volume"])
            from app.db.repositories.promotions import get_program
            prog = get_program(program_id)
            program_name = prog["name"] if prog else ""
        else:
            no_program += 1

        rebate_amount, rebate_rate = calc_rebate(
            row["total_volume"], row["total_commission"], tier
        )
        total_rebate += rebate_amount

        note = _build_note(program_name, period_date)

        result_rows.append({
            "trading_account":     ta,
            "use_id":              uids.get(ta, "") or info.get("use_id", ""),
            "name":                names.get(ta, ""),
            "account_type":        row.get("account_type", ""),
            "lots_type":           lots_type,
            "total_volume":        round(row["total_volume"], 4),
            "total_commission":    round(row["total_commission"], 4),
            **{k: round(row.get(k, 0), 4) for k in _ASSET_KEYS},
            "login_email":         info.get("login_email", ""),
            "customer_account_id": info.get("customer_account_id"),
            "ib_name":             info.get("ib_name", ""),
            "ib_number":           info.get("ib_number", ""),
            "program_id":          program_id,
            "program_name":        program_name,
            "tier_id":             tier["id"] if tier else None,
            "rebate_rate":         rebate_rate,
            "rebate_amount":       round(rebate_amount, 2),
            "note":                note,
            "is_existing":         bool(info.get("customer_account_id")),
        })

    return {
        "period_date": period_date,
        "rows":        result_rows,
        "stats": {
            "total_accounts": len(ta_set),
            "total_commission": round(sum(r["total_commission"] for r in result_rows), 2),
            "total_rebate":     round(total_rebate, 2),
            "with_program":     sum(1 for r in result_rows if r["program_name"]),
            "no_program":       no_program,
        },
    }


def _build_note(program_name: str, period_date: str) -> str:
    label = _period_label(period_date)
    return f"{program_name} — {label}" if program_name else f"Backcom — {label}"


def _period_label(period_date: str) -> str:
    try:
        d = datetime.strptime(period_date[:10], "%Y-%m-%d")
        return f"Month {d.month}/{d.year}"
    except Exception:
        return period_date or ""


# ── Confirm batch (save to DB) ─────────────────────────────────────────────────

async def confirm_batch(
    preview_rows: list,
    period_date: str,
    actor: str = "",
    broker: str = "vantage",
) -> int:
    """Save preview rows to commission_records + rebate_records. Returns batch_id."""
    import asyncio

    rows_with_data = [r for r in preview_rows if r.get("trading_account")]
    rows_with_rebate = [r for r in rows_with_data if r.get("rebate_amount", 0) > 0]
    total_amount = sum(r["rebate_amount"] for r in rows_with_rebate)

    broker_label = broker.upper() if broker else "VANTAGE"
    batch_id = await asyncio.to_thread(
        create_rebate_batch, period_date, actor,
        f"[{broker_label}] Import {len(rows_with_data)} accounts — {period_date}",
    )

    # Save commission records (raw data)
    comm_records = []
    for row in rows_with_data:
        comm_records.append({
            "trading_account":    row["trading_account"],
            "use_id":             row.get("use_id", "") or "",
            "total_volume":       float(row.get("total_volume") or 0),
            "total_commission":   float(row.get("total_commission") or 0),
            **{k: float(row.get(k) or 0) for k in _ASSET_KEYS},
        })
    await asyncio.to_thread(bulk_upsert_commission_records, batch_id, comm_records, period_date)

    # rebate_records are NOT written here.
    # Admin calculates rebate from commission_records in a separate step.

    await asyncio.to_thread(update_batch_totals, batch_id, len(rows_with_data), total_amount)
    await asyncio.to_thread(update_batch_status, batch_id, "confirmed")

    logger.info("rebate.batch_confirmed", batch_id=batch_id,
                rows=len(rows_with_data), total_amount=total_amount)
    return batch_id


# ── Export CSV files ───────────────────────────────────────────────────────────

def export_batch_csvs(batch_id: int) -> list[tuple[str, bytes]]:
    """
    Return list of (filename, csv_bytes) for the given batch,
    grouped by IB, max MAX_PER_FILE rows per file.
    Reads from rebate_records (has rebate_amount + ib info).
    """
    rows = get_rebate_records_by_batch(batch_id)
    if not rows:
        return []

    # Get period_date from batch
    from app.db.repositories.rebate import get_rebate_batch
    batch = get_rebate_batch(batch_id)
    period_date = (batch.get("period_date") or "") if batch else ""
    try:
        date_str = datetime.strptime(period_date[:10], "%Y-%m-%d").strftime("%Y%m%d")
    except Exception:
        date_str = datetime.now().strftime("%Y%m%d")

    # Group rows by ib_name
    groups: dict[str, list] = {}
    for row in rows:
        ib = (row.get("ib_name") or "NoIB").strip()
        groups.setdefault(ib, []).append(row)

    files: list[tuple[str, bytes]] = []
    for ib_name, ib_rows in sorted(groups.items()):
        chunks = [ib_rows[i:i + MAX_PER_FILE]
                  for i in range(0, len(ib_rows), MAX_PER_FILE)]
        for seq, chunk in enumerate(chunks, start=1):
            slug     = _slugify(ib_name)
            filename = f"{slug}_{date_str}_{seq:02d}.csv"
            csv_bytes = _make_csv(chunk)
            files.append((filename, csv_bytes))

    update_batch_status(batch_id, "exported")
    bulk_update_rebate_status(batch_id, "exported")

    return files


def _make_csv(rows: list) -> bytes:
    """Generate Vantage-format CSV bytes: To Account, Amount.

    rebate_records rows have use_id (customer platform account) as the
    transfer target, and rebate_amount as the amount.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["To Account", "Amount"])
    for row in rows:
        # use_id is the IB's client platform account for the transfer
        account = row.get("use_id") or row.get("trading_account", "")
        amount  = row.get("rebate_amount", 0)
        if account and amount and float(amount) > 0:
            writer.writerow([account, f"{float(amount):.2f}"])
    return buf.getvalue().encode("utf-8-sig")


def _slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s-]+", "_", text.strip())
    return text[:40] or "IB"
