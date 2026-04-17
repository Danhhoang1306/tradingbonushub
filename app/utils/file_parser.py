"""CSV and Excel file parsing utilities."""
import csv
import io

import openpyxl


def parse_file(content: bytes, filename: str) -> list[dict]:
    """Parse CSV or Excel → list of dicts (preserving original column names)."""
    name = (filename or "").lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return _parse_excel(content)
    return _parse_csv(content)


def parse_file_with_custom_headers(content: bytes, filename: str) -> list[dict]:
    """Parse Excel where Row 1 = default headers, Row 2 = custom headers.

    Uses Row 2 values as column names where non-null, falls back to Row 1.
    Data starts from Row 3.
    """
    name = (filename or "").lower()
    if not (name.endswith(".xlsx") or name.endswith(".xls")):
        # CSV: no custom header support, fall back to standard parse
        return _parse_csv(content)
    return _parse_excel_custom_headers(content)


def _parse_csv(content: bytes) -> list[dict]:
    # Try encodings in order: UTF-8 BOM → UTF-8 → cp1252 (Excel Vietnamese)
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            text = content.decode(enc)
            # Reject if the decoded text contains replacement characters (bad decode)
            if "\ufffd" not in text:
                break
        except (UnicodeDecodeError, LookupError):
            continue
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _parse_excel(content: bytes) -> list[dict]:
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        wb.close()
        return []
    headers = [
        str(h).strip() if h is not None else f"Col{i}"
        for i, h in enumerate(rows[0])
    ]
    result = []
    for row in rows[1:]:
        if all(v is None for v in row):
            continue
        result.append({
            headers[i]: (str(v).strip() if v is not None else "")
            for i, v in enumerate(row)
        })
    wb.close()
    return result


def _parse_excel_custom_headers(content: bytes) -> list[dict]:
    """Parse Excel with Row 2 as custom header override.

    Row 1 = default column names (from export system).
    Row 2 = user-defined column names (overrides Row 1 where non-null).
    Row 3+ = actual data.
    """
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 3:
        wb.close()
        return []

    row1 = rows[0]  # default headers
    row2 = rows[1]  # custom headers

    # Build final headers: prefer Row 2 (non-null), fall back to Row 1
    headers: list[str] = []
    for i in range(len(row1)):
        r2 = row2[i] if i < len(row2) else None
        r1 = row1[i] if i < len(row1) else None
        if r2 is not None and str(r2).strip():
            headers.append(str(r2).strip())
        elif r1 is not None and str(r1).strip():
            headers.append(str(r1).strip())
        else:
            headers.append(f"Col{i}")

    # Filter out columns where both Row 1 and Row 2 are null (trailing empty cols)
    # Find the last meaningful column
    last_col = 0
    for i in range(len(headers)):
        r1_val = row1[i] if i < len(row1) else None
        r2_val = row2[i] if i < len(row2) else None
        if r1_val is not None or r2_val is not None:
            last_col = i
    headers = headers[:last_col + 1]

    result = []
    for row in rows[2:]:  # data starts at Row 3
        if all(v is None for v in row):
            continue
        result.append({
            headers[i]: (str(v).strip() if v is not None else "")
            for i, v in enumerate(row)
            if i < len(headers)
        })
    wb.close()
    return result


def get_columns(rows: list[dict]) -> list[str]:
    if not rows:
        return []
    return list(rows[0].keys())
