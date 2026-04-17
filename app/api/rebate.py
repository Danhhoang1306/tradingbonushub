"""Rebate management API — import, preview, confirm, export."""
import io
import re
import unicodedata
import zipfile
from typing import List

import openpyxl
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.db.repositories.rebate import (
    get_all_rebate_batches,
    get_commission_records_by_batch,
    get_rebate_batch,
    get_rebate_records_by_batch,
)
from app.services.rebate_export import (
    MAX_PER_FILE,
    confirm_batch,
    export_batch_csvs,
    parse_and_preview,
)
from app.utils.rebate_columns import (
    REBATE_COL_MAP as _REBATE_COL_MAP,
    ASSET_KEYS as _ASSET_KEYS,
    get_col_map,
)

router = APIRouter(prefix="/api/rebate")


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", str(s).strip())


def _coerce_id(val) -> str:
    """Convert Excel use_id (may be int/float) to clean string without trailing .0"""
    if val is None:
        return ""
    if isinstance(val, float):
        return str(int(val)) if val else ""
    if isinstance(val, int):
        return str(val) if val else ""
    return str(val).strip()


def _parse_excel_sheet(ws, col_map: dict = None) -> list:
    if col_map is None:
        col_map = _REBATE_COL_MAP
    # Normalize col_map keys to NFC so Vietnamese headers always match
    col_map_nfc = {_nfc(k): v for k, v in col_map.items()}
    rows_iter = ws.iter_rows(values_only=True)
    header_raw = next(rows_iter, None)
    if not header_raw:
        return []
    col_idx = {i: col_map_nfc[_nfc(str(c))]
               for i, c in enumerate(header_raw)
               if c and _nfc(str(c)) in col_map_nfc}
    if not any(v == "trading_account" for v in col_idx.values()):
        return []
    result = []
    for row in rows_iter:
        data = {col_idx[i]: row[i] for i in col_idx if i < len(row)}
        ta = str(data.get("trading_account") or "").strip()
        if not ta:
            continue
        data["trading_account"] = ta
        data["use_id"]          = _coerce_id(data.get("use_id"))
        data["name"]            = str(data.get("name") or "").strip()
        data["lots_type"]       = str(data.get("lots_type") or "Standard").strip()
        data["account_type"]    = str(data.get("account_type") or "").strip()
        data["total_volume"]    = float(data.get("total_volume") or 0)
        data["total_commission"] = float(data.get("total_commission") or 0)
        for k in _ASSET_KEYS:
            data[k] = float(data.get(k) or 0)
        result.append(data)
    return result


def _parse_csv_content(content: bytes, col_map: dict = None) -> list:
    if col_map is None:
        col_map = _REBATE_COL_MAP
    col_map_nfc = {_nfc(k): v for k, v in col_map.items()}
    import csv as _csv
    text = content.decode("utf-8-sig", errors="replace")
    reader = _csv.DictReader(io.StringIO(text))
    result = []
    for raw_row in reader:
        data = {}
        for raw_key, val in raw_row.items():
            key = _nfc(raw_key or "")
            if key in col_map_nfc:
                data[col_map_nfc[key]] = val
        ta = str(data.get("trading_account") or "").strip()
        if not ta:
            continue
        data["trading_account"]   = ta
        data["use_id"]            = str(data.get("use_id") or "").strip()
        data["name"]              = str(data.get("name") or "").strip()
        data["lots_type"]         = str(data.get("lots_type") or "Standard").strip()
        data["account_type"]      = str(data.get("account_type") or "").strip()
        try:
            data["total_volume"]    = float(str(data.get("total_volume") or 0).replace(",", "") or 0)
            data["total_commission"] = float(str(data.get("total_commission") or 0).replace(",", "") or 0)
        except (ValueError, TypeError):
            data["total_volume"] = data["total_commission"] = 0.0
        for k in _ASSET_KEYS:
            try:
                data[k] = float(str(data.get(k) or 0).replace(",", "") or 0)
            except (ValueError, TypeError):
                data[k] = 0.0
        result.append(data)
    return result


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/preview")
async def api_rebate_preview(
    files: List[UploadFile] = File(...),
    broker: str = Form("vantage"),
):
    """
    Upload one or more broker rebate Excel/CSV files.
    broker: slug identifying the source broker (vantage, exness, ec, vt-market, dupoin).
    Returns preview with calculated rebate per trading account — no DB writes.
    """
    col_map = get_col_map(broker)

    merged: dict = {}
    names:  dict = {}
    uids:   dict = {}
    period_dates = []

    from app.utils.file_validation import check_upload_size, MAX_UPLOAD_DATA
    for file in files:
        fname = (file.filename or "").lower()
        if not fname.endswith((".xlsx", ".xls", ".csv")):
            continue
        content = await file.read()
        check_upload_size(content, MAX_UPLOAD_DATA, f"File {file.filename}")

        dm = re.search(r"(\d{4}-\d{2}-\d{2})", file.filename or "")
        if dm:
            period_dates.append(dm.group(1))

        if fname.endswith(".csv"):
            rows = _parse_csv_content(content, col_map)
        else:
            try:
                wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            except Exception:
                continue
            ws_name = "rebate" if "rebate" in wb.sheetnames else wb.sheetnames[0]
            rows = _parse_excel_sheet(wb[ws_name], col_map)

        for row in rows:
            key = (row["trading_account"], row["lots_type"])
            if key not in merged:
                merged[key] = dict(row)
            else:
                ex = merged[key]
                ex["total_volume"]     += row["total_volume"]
                ex["total_commission"] += row["total_commission"]
                for k in _ASSET_KEYS:
                    ex[k] += row.get(k, 0)
            if row["trading_account"] not in names:
                names[row["trading_account"]] = row.get("name", "")
            if row["trading_account"] not in uids and row.get("use_id"):
                uids[row["trading_account"]] = row["use_id"]

    if not merged:
        raise HTTPException(400, "No valid data found in files")

    period_date = sorted(period_dates)[0] if period_dates else ""
    raw_rows = list(merged.values())
    for r in raw_rows:
        if r["trading_account"] in uids:
            r["use_id"] = uids[r["trading_account"]]
        r["name"] = names.get(r["trading_account"], "")

    preview = parse_and_preview(raw_rows, period_date)
    return {"ok": True, "broker": broker, **preview}


@router.post("/confirm")
async def api_rebate_confirm(request: Request, payload: dict):
    """Save previewed rebate data to DB as a confirmed batch. Returns batch_id."""
    from datetime import datetime as _dt
    rows        = payload.get("rows", [])
    period_date = payload.get("period_date", "")
    broker      = payload.get("broker", "vantage") or "vantage"
    if not rows:
        raise HTTPException(400, "No data to save")
    if not period_date:
        raise HTTPException(400, "Missing period_date")
    try:
        _dt.strptime(period_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "period_date must be in YYYY-MM-DD format")

    actor = request.session.get("user", "admin")
    batch_id = await confirm_batch(rows, period_date, actor, broker=broker)
    batch = get_rebate_batch(batch_id)
    return {"ok": True, "batch_id": batch_id, "batch": batch}


@router.get("/batches")
async def api_rebate_batches():
    return get_all_rebate_batches()


@router.get("/batches/{batch_id}")
async def api_rebate_batch_detail(batch_id: int):
    batch = get_rebate_batch(batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    rows = get_commission_records_by_batch(batch_id)
    return {"batch": batch, "rows": rows}


@router.post("/batches/{batch_id}/export")
async def api_rebate_export(batch_id: int):
    """Generate Vantage bulk-upload CSV files for a batch. Returns ZIP."""
    batch = get_rebate_batch(batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    if batch["status"] == "draft":
        raise HTTPException(400, "Batch has not been confirmed")

    csv_files = export_batch_csvs(batch_id)
    if not csv_files:
        raise HTTPException(400, "No rebate data > 0 to export")

    if len(csv_files) == 1:
        filename, csv_bytes = csv_files[0]
        return StreamingResponse(
            io.BytesIO(csv_bytes),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, csv_bytes in csv_files:
            zf.writestr(filename, csv_bytes)
    zip_buf.seek(0)

    period_date = (batch.get("period_date") or "")[:10].replace("-", "")
    zip_name = f"rebate_export_{period_date}.zip"
    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'},
    )


@router.get("/batches/{batch_id}/preview-export")
async def api_rebate_preview_export(batch_id: int):
    """Preview which CSV files will be generated (names + row counts)."""
    batch = get_rebate_batch(batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    rows = get_rebate_records_by_batch(batch_id)

    groups: dict[str, list] = {}
    for row in rows:
        ib = (row.get("ib_name") or "NoIB").strip()
        groups.setdefault(ib, []).append(row)

    period_date = (batch.get("period_date") or "")[:10]
    try:
        from datetime import datetime
        date_str = datetime.strptime(period_date, "%Y-%m-%d").strftime("%Y%m%d")
    except Exception:
        date_str = period_date.replace("-", "")

    from app.services.rebate_export import _slugify
    files = []
    for ib_name, ib_rows in sorted(groups.items()):
        chunks = [ib_rows[i:i + MAX_PER_FILE]
                  for i in range(0, len(ib_rows), MAX_PER_FILE)]
        for seq, chunk in enumerate(chunks, start=1):
            files.append({
                "filename":     f"{_slugify(ib_name)}_{date_str}_{seq:02d}.csv",
                "ib_name":      ib_name,
                "row_count":    len(chunk),
                "total_amount": round(sum(float(r.get("rebate_amount", 0)) for r in chunk), 2),
            })

    return {"batch": batch, "files": files}
