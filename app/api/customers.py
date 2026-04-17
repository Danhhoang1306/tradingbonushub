"""Customer management API."""
import asyncio
import io
import re
import secrets
import string
from datetime import datetime
from typing import List

import openpyxl
import structlog
from openpyxl.styles import Alignment, Font, PatternFill
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.config import limiter

from app.db.repositories.customers import (
    count_customers, create_customer,
    delete_customer, get_all_customers,
    get_customer_by_email,
)
from app.db.repositories.customer_accounts import (
    get_accounts_for_customer, get_account_by_use_id,
    upsert_customer_account, upsert_trading_account,
)
from app.db.repositories.rebate import (
    create_rebate_batch, bulk_upsert_commission_records,
    get_rebate_batch, update_batch_totals, update_batch_status,
)
from app.services.rebate_calculator import run_daily_rebate
from app.db.repositories.smtp import get_smtp_config
from app.services.auth import hash_pw_async
from app.services.notifications import send_customer_welcome_email
from app.utils.audit import log_action
from app.utils.file_parser import parse_file
from app.utils.rebate_columns import REBATE_COL_MAP as _REBATE_COL_MAP, ASSET_KEYS as _ASSET_KEYS

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api")


async def _fire(coro, *, label: str) -> None:
    try:
        await coro
    except Exception as exc:
        logger.error("background_task_failed", label=label, error=str(exc))

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
_PW_ALPHABET = string.ascii_letters + string.digits


# ── List / Create / Delete ────────────────────────────────────────────────────

@router.get("/customers")
async def api_list_customers(
    limit: int = 500, offset: int = 0,
    type: str = "client", search: str = "",
):
    limit = min(max(limit, 1), 1000)
    ctype = type if type in ("client",) else "client"
    q = search.strip() or None
    rows  = await asyncio.to_thread(get_all_customers, limit, offset, ctype, q)
    total = await asyncio.to_thread(count_customers, ctype, q)
    items = [{**r, "portal_email": r.get("login_email", "")} for r in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/leads")
async def api_list_leads(
    limit: int = 100, offset: int = 0, search: str = "",
):
    """Lead = customer_accounts missing at least 1 of 3 client conditions:
       program_status='confirmed' AND client_status='active' AND ib_number exists in ibs.
    """
    limit = min(max(limit, 1), 1000)
    q = f"%{search.strip()}%" if search.strip() else None

    # Client condition (all 3 must be true):
    #   ca.program_status = 'confirmed'
    #   AND ca.client_status = 'active'
    #   AND EXISTS (SELECT 1 FROM ibs i WHERE i.ib_number = ca.ib_number AND i.broker_id = ca.broker_id)
    # Lead = NOT (client condition)
    _LEAD_COND = (
        "NOT ("
        "  ca.program_status = 'confirmed'"
        "  AND ca.client_status = 'active'"
        "  AND EXISTS (SELECT 1 FROM ibs i"
        "              WHERE i.ib_number = ca.ib_number AND i.broker_id = ca.broker_id)"
        ")"
    )

    def _query():
        from app.db.connection import get_conn as _gc
        with _gc() as conn:
            params: list = []
            search_cond = ""
            if q:
                search_cond = (
                    " AND (ca.use_id LIKE ? OR ca.broker_email LIKE ?"
                    " OR ca.client_name LIKE ? OR ca.country LIKE ? OR i.ib_name LIKE ?)"
                )
                params.extend([q, q, q, q, q])

            rows = conn.execute(
                f"""SELECT ca.id, ca.customer_id, ca.use_id, ca.broker_email,
                           ca.client_name, ca.country, ca.ib_number,
                           ca.client_status, ca.program_status, ca.created_at,
                           b.name  AS broker_name,
                           i.ib_name,
                           c.login_email, c.name AS portal_name,
                           c.is_verified, c.must_change_password, c.unsubscribed
                    FROM customer_accounts ca
                    JOIN brokers b ON b.id = ca.broker_id
                    LEFT JOIN ibs i ON i.ib_number = ca.ib_number
                                   AND i.broker_id = ca.broker_id
                    LEFT JOIN customers c ON c.id = ca.customer_id
                    WHERE {_LEAD_COND}
                    {search_cond}
                    ORDER BY ca.created_at DESC
                    OFFSET ? ROWS FETCH NEXT ? ROWS ONLY""",
                [*params, offset, limit],
            ).fetchall()

            total = conn.execute(
                f"""SELECT COUNT(*) AS cnt
                    FROM customer_accounts ca
                    LEFT JOIN ibs i ON i.ib_number = ca.ib_number
                                   AND i.broker_id = ca.broker_id
                    WHERE {_LEAD_COND}
                    {search_cond}""",
                params,
            ).fetchone()["cnt"]

        return rows, total

    rows, total = await asyncio.to_thread(_query)
    items = []
    for r in rows:
        r = dict(r)
        items.append({
            "id":               r["id"],
            "customer_id":      r["customer_id"],
            "use_id":           r["use_id"] or "",
            "broker_email":     r["broker_email"] or "",
            "client_name":      r["client_name"] or "",
            "country":          r["country"] or "",
            "ib_name":          r["ib_name"] or "",
            "ib_number":        r["ib_number"] or "",
            "broker_name":      r["broker_name"] or "",
            "client_status":    r["client_status"] or "",
            "program_status":   r["program_status"] or "",
            "is_verified":      r["is_verified"] or 0,
            "must_change_password": r["must_change_password"] or 0,
            "unsubscribed":     r["unsubscribed"] or 0,
            "portal_email":     r["login_email"] or "",
            "portal_name":      r["portal_name"] or "",
            "created_at":       str(r["created_at"]) if r["created_at"] else "",
        })
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/customers/unified")
async def api_unified_customers(
    limit: int = 100, offset: int = 0,
    search: str = "", client_status: str = "",
):
    """Unified view of ALL customer_accounts — lead, pending, active.

    client_status filter: 'lead', 'pending_data', 'pending_transfer', 'active', '' (all).
    """
    limit = min(max(limit, 1), 1000)
    q = f"%{search.strip()}%" if search.strip() else None

    def _query():
        from app.db.connection import get_conn as _gc
        with _gc() as conn:
            conditions = ["1=1"]
            params: list = []

            if client_status:
                conditions.append("ca.client_status = ?")
                params.append(client_status)
            if q:
                conditions.append(
                    "(ca.use_id LIKE ? OR ca.broker_email LIKE ?"
                    " OR ca.client_name LIKE ? OR ca.country LIKE ?"
                    " OR i.ib_name LIKE ? OR c.login_email LIKE ?)"
                )
                params.extend([q, q, q, q, q, q])

            where = " AND ".join(conditions)

            rows = conn.execute(
                f"""SELECT ca.id, ca.customer_id, ca.use_id, ca.broker_email,
                           ca.client_name, ca.country, ca.ib_number,
                           ca.client_status, ca.program_status, ca.created_at,
                           b.name  AS broker_name,
                           i.ib_name,
                           c.login_email, c.name AS portal_name,
                           c.is_verified, c.must_change_password, c.unsubscribed
                    FROM customer_accounts ca
                    JOIN brokers b ON b.id = ca.broker_id
                    LEFT JOIN ibs i ON i.ib_number = ca.ib_number
                                   AND i.broker_id = ca.broker_id
                    LEFT JOIN customers c ON c.id = ca.customer_id
                    WHERE {where}
                    ORDER BY ca.created_at DESC
                    OFFSET ? ROWS FETCH NEXT ? ROWS ONLY""",
                [*params, offset, limit],
            ).fetchall()

            total = conn.execute(
                f"""SELECT COUNT(*) AS cnt
                    FROM customer_accounts ca
                    JOIN brokers b ON b.id = ca.broker_id
                    LEFT JOIN ibs i ON i.ib_number = ca.ib_number
                                   AND i.broker_id = ca.broker_id
                    LEFT JOIN customers c ON c.id = ca.customer_id
                    WHERE {where}""",
                params,
            ).fetchone()["cnt"]

            # Count per status for pills
            status_counts = {}
            for row in conn.execute(
                "SELECT client_status, COUNT(*) AS cnt FROM customer_accounts GROUP BY client_status"
            ).fetchall():
                status_counts[row["client_status"]] = row["cnt"]

        return rows, total, status_counts

    rows, total, status_counts = await asyncio.to_thread(_query)
    items = []
    for r in rows:
        r = dict(r)
        items.append({
            # ── IDs ──
            "id":               r["id"],              # customer_accounts.id
            "customer_id":      r["customer_id"],      # FK → customers.id (NULL if no portal)
            # ── Broker account fields ──
            "use_id":           r["use_id"] or "",     # broker user ID (was "vantage_uid")
            "broker_email":     r["broker_email"] or "",  # email at broker (was "email")
            "client_name":      r["client_name"] or "",   # name from broker (was "name")
            "country":          r["country"] or "",
            "ib_number":        r["ib_number"] or "",
            "ib_name":          r["ib_name"] or "",
            "broker_name":      r["broker_name"] or "",
            # ── Status ──
            "client_status":    r["client_status"] or "",    # lead/pending_data/pending_transfer/active
            "program_status":   r["program_status"] or "",   # unconfirmed/confirmed
            # ── Portal account fields ──
            "portal_email":     r["login_email"] or "",      # login email on portal
            "portal_name":      r["portal_name"] or "",      # name on portal
            "has_portal":       1 if r["customer_id"] else 0,
            "is_verified":      r["is_verified"] or 0,
            "must_change_password": r["must_change_password"] or 0,
            "unsubscribed":     r["unsubscribed"] or 0,
            # ── Meta ──
            "created_at":       str(r["created_at"]) if r["created_at"] else "",
        })
    return {
        "items": items, "total": total,
        "limit": limit, "offset": offset,
        "status_counts": status_counts,
    }


@router.get("/customers/export")
@limiter.limit("10/minute")
async def api_export_customers(request: Request):
    """Export all customers and their broker accounts to Excel."""
    customers = await asyncio.to_thread(get_all_customers, 10000, 0)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Customers"

    header_fill = PatternFill("solid", fgColor="1A1A2E")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    headers = ["ID", "Email", "Full Name", "Unsubscribed",
               "Verified", "Broker emails", "Created"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for c in customers:
        unsub   = "Yes" if c.get("unsubscribed") else "No"
        verified = "Yes" if c.get("is_verified") else "No"
        ws.append([
            c["id"],
            c["login_email"],
            c.get("name") or "",
            unsub, verified,
            c.get("broker_emails") or "",
            str(c.get("created_at", "")),
        ])

    for col_letter, width in zip("ABCDEFG", [6, 34, 22, 14, 12, 40, 22]):
        ws.column_dimensions[col_letter].width = width

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"customers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/customers", status_code=201)
async def api_create_customer(request: Request, payload: dict):
    email = (payload.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(400, "Email is required")
    if not _EMAIL_RE.match(email):
        raise HTTPException(400, "Invalid email")
    if get_customer_by_email(email):
        raise HTTPException(409, "Email already exists")
    ctype = payload.get("customer_type", "client")
    if ctype not in ("client", "lead"):
        ctype = "client"
    temp_pw = ''.join(secrets.choice(_PW_ALPHABET) for _ in range(12))
    cid = create_customer(email, await hash_pw_async(temp_pw), customer_type=ctype)
    uid = cid
    log_action(request.session.get("user", ""), "customer.create",
               entity_type="customer", entity_id=str(uid), detail={"email": email})
    cfg = get_smtp_config()
    if not cfg.get("host") or cfg.get("host") == "localhost":
        return {"id": uid, "temp_password": temp_pw, "email_sent": False,
                "email_error": "SMTP not configured"}
    base_url = str(request.base_url).rstrip("/")
    asyncio.create_task(_fire(
        send_customer_welcome_email(cfg, email, temp_pw, f"{base_url}/portal/login"),
        label="send_customer_welcome_email",
    ))
    return {"id": uid, "email_sent": True, "email_error": ""}


@router.delete("/customers/{cid}")
async def api_delete_customer(request: Request, cid: int):
    await asyncio.to_thread(delete_customer, cid)
    log_action(request.session.get("user", ""), "customer.delete",
               entity_type="customer", entity_id=str(cid))
    return {"ok": True}


# ── Rebate upload: raw commission data → commission_records ───────────────────

@router.post("/customers/upload-rebate")
async def api_upload_rebate(
    request: Request,
    file: UploadFile = File(...),
):
    """
    Parse Vantage rebate Excel → save as a new draft rebate_batch +
    commission_records. Returns batch_id for review / confirm.
    """
    content = await file.read()
    from app.utils.file_validation import check_upload_size, MAX_UPLOAD_DATA
    check_upload_size(content, MAX_UPLOAD_DATA, "Rebate file")
    buf = io.BytesIO(content)

    import re as _re
    dm = _re.search(r'(\d{4}-\d{2}-\d{2})', file.filename or '')
    period_date = dm.group(1) if dm else datetime.now().strftime("%Y-%m-%d")

    try:
        wb = openpyxl.load_workbook(buf, read_only=True, data_only=True)
    except Exception as e:
        raise HTTPException(400, f"Cannot read Excel file: {e}")

    sheet_name = "rebate" if "rebate" in wb.sheetnames else wb.sheetnames[0]
    ws = wb[sheet_name]
    rows_iter = ws.iter_rows(values_only=True)
    header_raw = next(rows_iter, None)
    if not header_raw:
        raise HTTPException(400, "File is empty or missing headers")

    col_idx = {i: _REBATE_COL_MAP[str(c).strip()]
               for i, c in enumerate(header_raw)
               if c and str(c).strip() in _REBATE_COL_MAP}

    records = []
    skipped = 0
    for row in rows_iter:
        data = {col_idx[i]: (row[i] if row[i] is not None else 0)
                for i in col_idx if i < len(row)}
        ta = str(data.get("trading_account") or "").strip()
        if not ta:
            skipped += 1
            continue
        records.append({
            "trading_account":   ta,
            "use_id":            str(data.get("use_id") or "").strip(),
            "total_volume":      float(data.get("total_volume") or 0),
            "total_commission":  float(data.get("total_commission") or 0),
            **{k: float(data.get(k) or 0) for k in _ASSET_KEYS},
        })

    if not records:
        raise HTTPException(400, "No valid data found in file")

    actor = request.session.get("user", "admin")
    batch_id = await asyncio.to_thread(
        create_rebate_batch, period_date, actor,
        f"Upload {file.filename} — {period_date}",
    )
    await asyncio.to_thread(bulk_upsert_commission_records, batch_id, records, period_date)
    total_comm = sum(r["total_commission"] for r in records)
    await asyncio.to_thread(update_batch_totals, batch_id, len(records), total_comm)

    # Auto-calculate rebate for this trading date
    from datetime import date as _date
    trade_date = _date.fromisoformat(period_date)
    rebate_result = await asyncio.to_thread(run_daily_rebate, trade_date)

    return {"ok": True, "batch_id": batch_id,
            "imported": len(records), "skipped": skipped,
            "rebate": rebate_result}


# ── Customer detail ───────────────────────────────────────────────────────────

def _customer_detail_sync(login_email: str) -> dict:
    from app.db.connection import get_conn as _gc
    with _gc() as conn:
        cust = conn.execute(
            """SELECT id, name, login_email, must_change_password,
                      is_verified, unsubscribed, customer_type, created_at
               FROM customers WHERE login_email=?""",
            (login_email,),
        ).fetchone()
        if not cust:
            raise HTTPException(404, "Customer not found")
        cust = dict(cust)
        if cust.get("created_at"):
            cust["created_at"] = str(cust["created_at"])

        # Broker accounts
        ca_rows = conn.execute(
            """SELECT ca.*, b.name AS broker_name, b.slug AS broker_slug,
                      p.name AS program_name
               FROM customer_accounts ca
               JOIN brokers b ON b.id = ca.broker_id
               LEFT JOIN programs p ON p.id = ca.program_id
               WHERE ca.customer_id = ?
               ORDER BY b.display_order""",
            (cust["id"],),
        ).fetchall()

        accounts = []
        for ca in ca_rows:
            ca_dict = dict(ca)
            ta_rows = conn.execute(
                "SELECT * FROM trading_accounts WHERE customer_account_id=? AND is_active=1",
                (ca_dict["id"],),
            ).fetchall()
            ca_dict["trading_accounts"] = [dict(t) for t in ta_rows]
            # Serialize datetime fields for JSON
            for dtf in ("promo_expires_at", "program_joined_at", "created_at"):
                if ca_dict.get(dtf):
                    ca_dict[dtf] = str(ca_dict[dtf])
            accounts.append(ca_dict)

        # Email history
        emails_sent = conn.execute(
            """SELECT TOP 20 e.id, e.recipient_name, e.created_at,
                      COUNT(o.id) AS open_count, MAX(o.opened_at) AS last_opened
               FROM emails e
               LEFT JOIN opens o ON o.tracking_id = e.id
               WHERE e.recipient_email=?
               GROUP BY e.id, e.recipient_name, e.created_at
               ORDER BY e.created_at DESC""",
            (login_email,),
        ).fetchall()

    return {
        "customer": cust,
        "accounts": accounts,
        "emails_sent": [
            {
                "id":          r["id"],
                "subject":     r["recipient_name"] or "",
                "created_at":  str(r["created_at"]) if r["created_at"] else "",
                "open_count":  r["open_count"] or 0,
                "last_opened": str(r["last_opened"]) if r["last_opened"] else "",
            }
            for r in emails_sent
        ],
    }


@router.get("/customers/{email}/detail")
async def api_customer_detail(email: str):
    return await asyncio.to_thread(_customer_detail_sync, email.strip().lower())


# ── Client folder import ──────────────────────────────────────────────────────

# Old format: "Registration Date" column
_CLIENT_COL_MAP_OLD = {
    "User ID":            "use_id",
    "Account Owner":      "ib_name",
    "Client Name (IPT)":  "client_name",
    "AFFID":              "affid",
    "Account":            "country",
    "IB Campaign Source": "broker_email",
    "Source Adjustment":  "mt5_accounts_raw",
}

# New format: "Register Date" column
_CLIENT_COL_MAP_NEW = {
    "Sales":              "use_id",
    "Client Name (IPT)":  "ib_info",
    "Client Name (EN)":   "client_name",
    "Account":            "broker_email",
    "Register Date":      "country",
    "Update Date":        "trading_account",
    "IB Campaign Source": "account_type",
}

_IB_INFO_RE = re.compile(r'^(.*?)\((\d+)\)\s*$')


def _parse_client_csv(content: bytes) -> list:
    import csv as _csv
    text = content.decode("utf-8-sig", errors="replace")
    reader = _csv.DictReader(io.StringIO(text))
    fieldnames = set(reader.fieldnames or [])
    is_new = "Register Date" in fieldnames
    col_map = _CLIENT_COL_MAP_NEW if is_new else _CLIENT_COL_MAP_OLD

    result = []
    for raw_row in reader:
        data = {}
        for raw_key, val in raw_row.items():
            key = (raw_key or "").strip()
            if key in col_map:
                data[col_map[key]] = (val or "").strip()

        use_id       = str(data.get("use_id") or "").strip()
        broker_email = str(data.get("broker_email") or "").strip().lower()
        client_name  = str(data.get("client_name") or "").strip()
        country      = str(data.get("country") or "").strip()

        if is_new:
            ib_info = data.get("ib_info", "")
            m = _IB_INFO_RE.match(ib_info)
            ib_name    = m.group(1).strip() if m else ib_info
            ib_number  = m.group(2).strip() if m else ""
            ta_raw     = data.get("trading_account", "").strip()
            mt5_list   = [ta_raw] if ta_raw.isdigit() else []
            account_type = str(data.get("account_type") or "").strip()
        else:
            ib_name    = str(data.get("ib_name") or "").strip()
            ib_number  = ""
            raw_mt5    = str(data.get("mt5_accounts_raw") or "").strip()
            mt5_list   = [m2 for m2 in raw_mt5.split() if m2.isdigit()]
            account_type = ""

        if not use_id and not broker_email:
            continue
        # Skip mapping/header rows: use_id is not numeric AND email has no "@"
        if not use_id.isdigit() and "@" not in broker_email:
            continue

        result.append({
            "use_id":        use_id,
            "broker_email":  broker_email,
            "client_name":   client_name,
            "country":       country,
            "ib_name":       ib_name,
            "ib_number":     ib_number,
            "account_type":  account_type,
            "mt5_accounts":  mt5_list,
        })
    return result


@router.post("/customers/process-client-folder")
async def api_process_client_folder(
    files: List[UploadFile] = File(...),
    broker: str = Form("vantage"),
):
    """Parse client CSV folder, match to existing accounts, return preview."""
    merged: dict = {}   # use_id → row
    files_processed = 0

    for file in files:
        fname = (file.filename or "").lower()
        if not fname.endswith(".csv"):
            continue
        content = await file.read()
        rows = _parse_client_csv(content)
        for row in rows:
            key = row["use_id"] or row["broker_email"]
            if key not in merged:
                merged[key] = dict(row)
            else:
                ex = merged[key]
                for f2 in ("use_id", "client_name", "ib_name", "ib_number",
                           "broker_email", "country"):
                    if row.get(f2):
                        ex[f2] = row[f2]
                existing_mt5 = set(ex.get("mt5_accounts") or [])
                existing_mt5.update(row.get("mt5_accounts") or [])
                ex["mt5_accounts"] = list(existing_mt5)
        files_processed += 1

    if not merged:
        raise HTTPException(400, "No valid data found in selected files")

    all_use_ids      = [r["use_id"]      for r in merged.values() if r.get("use_id")]
    all_broker_emails = [r["broker_email"] for r in merged.values() if r.get("broker_email")]

    # Single DB round-trip to check existing
    from app.db.connection import get_conn as _gc
    use_id_map:   dict = {}   # use_id → customer_account id
    email_map:    dict = {}   # broker_email → customer_account id

    with _gc() as conn:
        broker_row = conn.execute(
            "SELECT id FROM brokers WHERE slug=?", [broker]
        ).fetchone()
        default_broker_id = broker_row["id"] if broker_row else None

        if all_use_ids and default_broker_id:
            ph = ",".join("?" * len(all_use_ids))
            rows_db = conn.execute(
                f"SELECT id, use_id FROM customer_accounts "
                f"WHERE broker_id=? AND use_id IN ({ph})",
                [default_broker_id, *all_use_ids],
            ).fetchall()
            for r in rows_db:
                use_id_map[r["use_id"]] = r["id"]

        if all_broker_emails and default_broker_id:
            ph = ",".join("?" * len(all_broker_emails))
            rows_db = conn.execute(
                f"SELECT id, broker_email FROM customer_accounts "
                f"WHERE broker_id=? AND broker_email IN ({ph})",
                [default_broker_id, *all_broker_emails],
            ).fetchall()
            for r in rows_db:
                email_map[r["broker_email"]] = r["id"]

    result_rows = []
    stats = {"matched_by_use_id": 0, "matched_by_email": 0,
             "new_accounts": 0, "total_mt5": 0}

    for key, row in sorted(merged.items()):
        use_id       = row.get("use_id", "")
        broker_email = row.get("broker_email", "")
        if use_id and use_id in use_id_map:
            match_type = "use_id"
            stats["matched_by_use_id"] += 1
        elif broker_email and broker_email in email_map:
            match_type = "email"
            stats["matched_by_email"] += 1
        else:
            match_type = "new"
            stats["new_accounts"] += 1
        mt5_list = row.get("mt5_accounts") or []
        stats["total_mt5"] += len(mt5_list)
        result_rows.append({
            "use_id":       use_id,
            "broker_email": broker_email,
            "client_name":  row.get("client_name", ""),
            "country":      row.get("country", ""),
            "ib_name":      row.get("ib_name", ""),
            "ib_number":    row.get("ib_number", ""),
            "account_type": row.get("account_type", ""),
            "mt5_accounts": mt5_list,
            "match_type":   match_type,
            "is_existing":  match_type != "new",
        })

    return {
        "ok":              True,
        "broker":          broker,
        "files_processed": files_processed,
        "rows":            result_rows,
        "stats":           {**stats, "total_rows": len(result_rows)},
    }


@router.post("/customers/confirm-client-batch")
async def api_confirm_client_batch(payload: dict):
    """Apply previewed client import to DB: upsert customer_accounts + trading_accounts."""
    rows = payload.get("rows", [])
    if not rows:
        raise HTTPException(400, "No data to save")

    broker_slug = payload.get("broker", "vantage")
    from app.db.connection import get_conn as _gc
    with _gc() as conn:
        broker_row = conn.execute(
            "SELECT id, name FROM brokers WHERE slug=?", [broker_slug]
        ).fetchone()
        default_broker_id = broker_row["id"] if broker_row else None

    if not default_broker_id:
        raise HTTPException(500, f"Broker '{broker_slug}' not found")

    upserted = 0
    mt5_linked = 0

    for row in rows:
        use_id       = str(row.get("use_id") or "").strip()
        broker_email = str(row.get("broker_email") or "").strip().lower()
        client_name  = str(row.get("client_name") or "").strip()
        country      = str(row.get("country") or "").strip()
        ib_number    = str(row.get("ib_number") or "").strip()
        mt5_list     = [str(m).strip() for m in (row.get("mt5_accounts") or []) if str(m).strip()]
        account_type = str(row.get("account_type") or "").strip()

        if not use_id and not broker_email:
            continue

        ca_id = await asyncio.to_thread(
            upsert_customer_account,
            default_broker_id,
            use_id,
            ib_number=ib_number or None,
            broker_email=broker_email,
            client_name=client_name,
            country=country,
            client_status="lead",
        )
        if ca_id is None:
            continue
        upserted += 1

        for mt5 in mt5_list:
            await asyncio.to_thread(upsert_trading_account, ca_id, mt5, account_type)
            mt5_linked += 1

    return {"ok": True, "upserted": upserted, "mt5_linked": mt5_linked}
