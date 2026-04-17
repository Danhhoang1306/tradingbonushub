"""Broker rebate column mappings — used by customers.py and rebate.py.

Python field names match DB column names in commission_records / rebate_records.
Add a broker-specific entry in BROKER_COL_MAPS when you have that broker's
actual column header names. Until then, the broker falls back to Vantage format.
"""

REBATE_COL_MAP: dict[str, str] = {
    "Tên":                               "name",
    "ID người dùng":                     "use_id",
    "Tài Khoản":                         "trading_account",
    "Lots Type":                         "lots_type",
    "Loại tài khoản":                    "account_type",
    "TỔNG HOA HỒNGUSD":                  "total_commission",
    "Tổng số lô":                        "total_volume",
    "TỔNG KHỐI LƯỢNG(NGOẠI HỐI)":        "fx_lot",
    "Hoa Hồng(NGOẠI HỐI)":              "fx_commission",
    "TỔNG KHỐI LƯỢNG(HÀNG HÓA)":         "hang_hoa_lot",
    "Hoa Hồng(HÀNG HÓA)":               "hang_hoa_commission",
    "TỔNG KHỐI LƯỢNG(CHỈ SỐ)":           "index_lot",
    "Hoa Hồng(CHỈ SỐ)":                 "index_commission",
    "TỔNG KHỐI LƯỢNG(TIỀN ĐIỆN TỬ)":    "crypto_lot",
    "Hoa Hồng(TIỀN ĐIỆN TỬ)":           "crypto_commission",
    "TỔNG KHỐI LƯỢNG(shareCFD)":        "sharecfd_lot",
    "Hoa Hồng(shareCFD)":               "sharecfd_commission",
    "TỔNG KHỐI LƯỢNG(bond)":            "bond_lot",
    "Hoa Hồng(bond)":                   "bond_commission",
    "TỔNG KHỐI LƯỢNG(CHỈ SỐ TỔNG HỢP)": "synthetic_lot",
    "Hoa Hồng(CHỈ SỐ TỔNG HỢP)":        "synthetic_commission",
}

ASSET_KEYS: list[str] = [
    "fx_lot",        "fx_commission",
    "hang_hoa_lot",  "hang_hoa_commission",
    "index_lot",     "index_commission",
    "crypto_lot",    "crypto_commission",
    "sharecfd_lot",  "sharecfd_commission",
    "bond_lot",      "bond_commission",
    "synthetic_lot", "synthetic_commission",
]

# ── Per-broker column maps ──────────────────────────────────────────────────────
# Add broker-specific maps here once you obtain a sample file from each broker.
# Keys are broker slugs (same as brokers.slug in DB).
# Each map: { "Excel column header": "python_field_name" }
# Minimum required field: "trading_account"
#
# TODO: replace placeholder maps below with real column headers once
#       sample files from each broker are available.

_EXNESS_COL_MAP: dict[str, str] = {
    # Placeholder — update with actual Exness report headers
    # "Login":            "trading_account",
    # "Client ID":        "use_id",
    # "Name":             "name",
    # "Volume (lots)":    "total_volume",
    # "Commission (USD)": "total_commission",
}

_EC_COL_MAP: dict[str, str] = {
    # Placeholder — update with actual EC (Eightcap) report headers
}

_VT_MARKET_COL_MAP: dict[str, str] = {
    # Placeholder — update with actual VT Market report headers
}

_DUPOIN_COL_MAP: dict[str, str] = {
    # Placeholder — update with actual Dupoin report headers
}

BROKER_COL_MAPS: dict[str, dict] = {
    "vantage":   REBATE_COL_MAP,
    "exness":    _EXNESS_COL_MAP or REBATE_COL_MAP,
    "ec":        _EC_COL_MAP    or REBATE_COL_MAP,
    "vt-market": _VT_MARKET_COL_MAP or REBATE_COL_MAP,
    "dupoin":    _DUPOIN_COL_MAP or REBATE_COL_MAP,
}


def get_col_map(broker_slug: str) -> dict:
    """Return column map for the given broker slug, falling back to Vantage."""
    return BROKER_COL_MAPS.get(broker_slug) or REBATE_COL_MAP
