"""Rebate CRUD — SQL Server.

Flow:
  1. commission_records  — raw import per trading_account per batch
  2. rebate_records      — aggregated per customer_account per batch → rebate_amount
  3. program_events      — milestone bonus history

Column names match the Excel export format (record_commission.xlsx / recor_rebate.xlsx).
"""
from app.db.connection import get_conn

# Instrument column pairs (lot, commission) — same order as Excel
_INSTRUMENT_COLS = [
    ("fx_lot",        "fx_commission"),
    ("hang_hoa_lot",  "hang_hoa_commission"),
    ("index_lot",     "index_commission"),
    ("crypto_lot",    "crypto_commission"),
    ("sharecfd_lot",  "sharecfd_commission"),
    ("bond_lot",      "bond_commission"),
    ("synthetic_lot", "synthetic_commission"),
]

_ALL_COMMISSION_COLS = (
    "total_volume", "total_commission",
    "fx_lot", "fx_commission",
    "hang_hoa_lot", "hang_hoa_commission",
    "index_lot", "index_commission",
    "crypto_lot", "crypto_commission",
    "sharecfd_lot", "sharecfd_commission",
    "bond_lot", "bond_commission",
    "synthetic_lot", "synthetic_commission",
)


# ── Rebate Batches ─────────────────────────────────────────────────────────────

def create_rebate_batch(
    period_date: str,
    created_by: str = "",
    notes: str = "",
) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO rebate_batches (period_date, created_by, notes) OUTPUT INSERTED.id VALUES (?,?,?)",
            (period_date, created_by, notes),
        ).fetchone()
        return row["id"]


def get_rebate_batch(batch_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM rebate_batches WHERE id=?", (batch_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["period_date"] = str(d["period_date"]) if d.get("period_date") else None
        d["created_at"]  = str(d["created_at"])  if d.get("created_at")  else None
        return d


def get_all_rebate_batches() -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM rebate_batches ORDER BY created_at DESC"
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["period_date"] = str(d["period_date"]) if d.get("period_date") else None
            d["created_at"]  = str(d["created_at"])  if d.get("created_at")  else None
            result.append(d)
        return result


def update_batch_totals(batch_id: int, total_rows: int, total_amount: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE rebate_batches SET total_rows=?, total_amount=? WHERE id=?",
            (total_rows, total_amount, batch_id),
        )


def update_batch_status(batch_id: int, status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE rebate_batches SET status=? WHERE id=?",
            (status, batch_id),
        )


# ── Commission Records ─────────────────────────────────────────────────────────

_COMMISSION_MERGE_SQL = """
MERGE commission_records AS t
USING (VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)) AS s(
    batch_id, trading_account, use_id, lots_type,
    total_volume, total_commission,
    fx_lot, fx_commission,
    hang_hoa_lot, hang_hoa_commission,
    index_lot, index_commission,
    crypto_lot, crypto_commission,
    sharecfd_lot, sharecfd_commission,
    bond_lot, bond_commission,
    synthetic_lot, synthetic_commission,
    uploaded_at
)
ON t.batch_id = s.batch_id AND t.trading_account = s.trading_account
   AND t.lots_type = s.lots_type
WHEN MATCHED THEN UPDATE SET
    use_id               = s.use_id,
    total_volume         = s.total_volume,
    total_commission     = s.total_commission,
    fx_lot               = s.fx_lot,
    fx_commission        = s.fx_commission,
    hang_hoa_lot         = s.hang_hoa_lot,
    hang_hoa_commission  = s.hang_hoa_commission,
    index_lot            = s.index_lot,
    index_commission     = s.index_commission,
    crypto_lot           = s.crypto_lot,
    crypto_commission    = s.crypto_commission,
    sharecfd_lot         = s.sharecfd_lot,
    sharecfd_commission  = s.sharecfd_commission,
    bond_lot             = s.bond_lot,
    bond_commission      = s.bond_commission,
    synthetic_lot        = s.synthetic_lot,
    synthetic_commission = s.synthetic_commission,
    uploaded_at          = COALESCE(s.uploaded_at, t.uploaded_at)
WHEN NOT MATCHED THEN INSERT (
    batch_id, trading_account, use_id, lots_type,
    total_volume, total_commission,
    fx_lot, fx_commission,
    hang_hoa_lot, hang_hoa_commission,
    index_lot, index_commission,
    crypto_lot, crypto_commission,
    sharecfd_lot, sharecfd_commission,
    bond_lot, bond_commission,
    synthetic_lot, synthetic_commission,
    uploaded_at
) VALUES (
    s.batch_id, s.trading_account, s.use_id, s.lots_type,
    s.total_volume, s.total_commission,
    s.fx_lot, s.fx_commission,
    s.hang_hoa_lot, s.hang_hoa_commission,
    s.index_lot, s.index_commission,
    s.crypto_lot, s.crypto_commission,
    s.sharecfd_lot, s.sharecfd_commission,
    s.bond_lot, s.bond_commission,
    s.synthetic_lot, s.synthetic_commission,
    COALESCE(s.uploaded_at, GETDATE())
);
"""


def _commission_params(
    batch_id, trading_account, use_id, lots_type, uploaded_at,
    total_volume, total_commission,
    fx_lot, fx_commission,
    hang_hoa_lot, hang_hoa_commission,
    index_lot, index_commission,
    crypto_lot, crypto_commission,
    sharecfd_lot, sharecfd_commission,
    bond_lot, bond_commission,
    synthetic_lot, synthetic_commission,
):
    return (
        batch_id, trading_account, use_id, lots_type,
        total_volume, total_commission,
        fx_lot, fx_commission,
        hang_hoa_lot, hang_hoa_commission,
        index_lot, index_commission,
        crypto_lot, crypto_commission,
        sharecfd_lot, sharecfd_commission,
        bond_lot, bond_commission,
        synthetic_lot, synthetic_commission,
        uploaded_at,
    )


def upsert_commission_record(
    batch_id: int,
    trading_account: str,
    use_id: str = "",
    lots_type: str = "Standard",
    uploaded_at: str = None,
    *,
    total_volume: float = 0,
    total_commission: float = 0,
    fx_lot: float = 0,             fx_commission: float = 0,
    hang_hoa_lot: float = 0,       hang_hoa_commission: float = 0,
    index_lot: float = 0,          index_commission: float = 0,
    crypto_lot: float = 0,         crypto_commission: float = 0,
    sharecfd_lot: float = 0,       sharecfd_commission: float = 0,
    bond_lot: float = 0,           bond_commission: float = 0,
    synthetic_lot: float = 0,      synthetic_commission: float = 0,
) -> None:
    """MERGE on (batch_id, trading_account, lots_type) — replaces existing row.

    uploaded_at: trading date (YYYY-MM-DD). If None, DB keeps GETDATE() on INSERT.
    """
    with get_conn() as conn:
        conn.execute(
            _COMMISSION_MERGE_SQL,
            _commission_params(
                batch_id, trading_account, use_id, lots_type, uploaded_at,
                total_volume, total_commission,
                fx_lot, fx_commission,
                hang_hoa_lot, hang_hoa_commission,
                index_lot, index_commission,
                crypto_lot, crypto_commission,
                sharecfd_lot, sharecfd_commission,
                bond_lot, bond_commission,
                synthetic_lot, synthetic_commission,
            ),
        )


def bulk_upsert_commission_records(batch_id: int, records: list[dict],
                                    period_date: str = None) -> None:
    """Batch insert commission records from a list of dicts (Excel import).

    period_date: trading date (YYYY-MM-DD) stored as uploaded_at so the
                 rebate calculator can filter by date correctly.
                 If None, uses GETDATE() (upload time — legacy behavior).
    Each dict should have keys matching Excel columns:
      trading_account, use_id, total_volume, total_commission,
      fx_lot, fx_commission, hang_hoa_lot, hang_hoa_commission,
      index_lot, index_commission, crypto_lot, crypto_commission,
      sharecfd_lot, sharecfd_commission, bond_lot, bond_commission,
      synthetic_lot, synthetic_commission

    All records are written in a single DB transaction — much faster than
    calling upsert_commission_record() per row.
    """
    with get_conn() as conn:
        for r in records:
            conn.execute(
                _COMMISSION_MERGE_SQL,
                _commission_params(
                    batch_id,
                    str(r.get("trading_account", "")),
                    str(r.get("use_id", "")),
                    str(r.get("lots_type", "Standard")),
                    period_date,
                    float(r.get("total_volume", 0)),
                    float(r.get("total_commission", 0)),
                    float(r.get("fx_lot", 0)),
                    float(r.get("fx_commission", 0)),
                    float(r.get("hang_hoa_lot", 0)),
                    float(r.get("hang_hoa_commission", 0)),
                    float(r.get("index_lot", 0)),
                    float(r.get("index_commission", 0)),
                    float(r.get("crypto_lot", 0)),
                    float(r.get("crypto_commission", 0)),
                    float(r.get("sharecfd_lot", 0)),
                    float(r.get("sharecfd_commission", 0)),
                    float(r.get("bond_lot", 0)),
                    float(r.get("bond_commission", 0)),
                    float(r.get("synthetic_lot", 0)),
                    float(r.get("synthetic_commission", 0)),
                ),
            )


def get_commission_records_by_batch(batch_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM commission_records WHERE batch_id=? ORDER BY use_id, trading_account",
            (batch_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_commission_records_by_use_id(batch_id: int, use_id: str) -> list:
    """All commission records for a client (use_id) within a batch."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM commission_records WHERE batch_id=? AND use_id=?",
            (batch_id, str(use_id)),
        ).fetchall()
        return [dict(r) for r in rows]


def aggregate_commission_for_use_id(batch_id: int, use_id: str) -> dict:
    """Sum all trading_account rows for a client into a single aggregate dict."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT
                SUM(total_volume)         AS total_volume,
                SUM(total_commission)     AS total_commission,
                SUM(fx_lot)               AS fx_lot,
                SUM(fx_commission)        AS fx_commission,
                SUM(hang_hoa_lot)         AS hang_hoa_lot,
                SUM(hang_hoa_commission)  AS hang_hoa_commission,
                SUM(index_lot)            AS index_lot,
                SUM(index_commission)     AS index_commission,
                SUM(crypto_lot)           AS crypto_lot,
                SUM(crypto_commission)    AS crypto_commission,
                SUM(sharecfd_lot)         AS sharecfd_lot,
                SUM(sharecfd_commission)  AS sharecfd_commission,
                SUM(bond_lot)             AS bond_lot,
                SUM(bond_commission)      AS bond_commission,
                SUM(synthetic_lot)        AS synthetic_lot,
                SUM(synthetic_commission) AS synthetic_commission
               FROM commission_records
               WHERE batch_id=? AND use_id=?""",
            (batch_id, str(use_id)),
        ).fetchone()
        if not row:
            return {}
        return {k: float(v or 0) for k, v in dict(row).items()}


# ── Rebate Records ─────────────────────────────────────────────────────────────

def upsert_rebate_record(
    batch_id: int,
    customer_account_id: int,
    program_tier_id: int,
    rebate_amount: float,
    status: str = "pending",
    *,
    total_volume: float = 0,
    total_commission: float = 0,
    fx_lot: float = 0,             fx_commission: float = 0,
    hang_hoa_lot: float = 0,       hang_hoa_commission: float = 0,
    index_lot: float = 0,          index_commission: float = 0,
    crypto_lot: float = 0,         crypto_commission: float = 0,
    sharecfd_lot: float = 0,       sharecfd_commission: float = 0,
    bond_lot: float = 0,           bond_commission: float = 0,
    synthetic_lot: float = 0,      synthetic_commission: float = 0,
) -> None:
    """MERGE on (batch_id, customer_account_id)."""
    with get_conn() as conn:
        conn.execute(
            """
            MERGE rebate_records AS t
            USING (VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)) AS s(
                batch_id, customer_account_id, program_tier_id, rebate_amount, status,
                total_volume, total_commission,
                fx_lot, fx_commission,
                hang_hoa_lot, hang_hoa_commission,
                index_lot, index_commission,
                crypto_lot, crypto_commission,
                sharecfd_lot, sharecfd_commission,
                bond_lot, bond_commission,
                synthetic_lot, synthetic_commission
            )
            ON t.batch_id = s.batch_id AND t.customer_account_id = s.customer_account_id
            WHEN MATCHED THEN UPDATE SET
                program_tier_id      = s.program_tier_id,
                rebate_amount        = s.rebate_amount,
                status               = s.status,
                total_volume         = s.total_volume,
                total_commission     = s.total_commission,
                fx_lot               = s.fx_lot,
                fx_commission        = s.fx_commission,
                hang_hoa_lot         = s.hang_hoa_lot,
                hang_hoa_commission  = s.hang_hoa_commission,
                index_lot            = s.index_lot,
                index_commission     = s.index_commission,
                crypto_lot           = s.crypto_lot,
                crypto_commission    = s.crypto_commission,
                sharecfd_lot         = s.sharecfd_lot,
                sharecfd_commission  = s.sharecfd_commission,
                bond_lot             = s.bond_lot,
                bond_commission      = s.bond_commission,
                synthetic_lot        = s.synthetic_lot,
                synthetic_commission = s.synthetic_commission
            WHEN NOT MATCHED THEN INSERT (
                batch_id, customer_account_id, program_tier_id, rebate_amount, status,
                total_volume, total_commission,
                fx_lot, fx_commission,
                hang_hoa_lot, hang_hoa_commission,
                index_lot, index_commission,
                crypto_lot, crypto_commission,
                sharecfd_lot, sharecfd_commission,
                bond_lot, bond_commission,
                synthetic_lot, synthetic_commission
            ) VALUES (
                s.batch_id, s.customer_account_id, s.program_tier_id, s.rebate_amount, s.status,
                s.total_volume, s.total_commission,
                s.fx_lot, s.fx_commission,
                s.hang_hoa_lot, s.hang_hoa_commission,
                s.index_lot, s.index_commission,
                s.crypto_lot, s.crypto_commission,
                s.sharecfd_lot, s.sharecfd_commission,
                s.bond_lot, s.bond_commission,
                s.synthetic_lot, s.synthetic_commission
            );
            """,
            (
                batch_id, customer_account_id, program_tier_id, rebate_amount, status,
                total_volume, total_commission,
                fx_lot, fx_commission,
                hang_hoa_lot, hang_hoa_commission,
                index_lot, index_commission,
                crypto_lot, crypto_commission,
                sharecfd_lot, sharecfd_commission,
                bond_lot, bond_commission,
                synthetic_lot, synthetic_commission,
            ),
        )


def get_rebate_records_by_batch(batch_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT rr.*,
                      ca.use_id, ca.ib_number, ca.broker_email, ca.client_name,
                      ca.customer_id,
                      c.login_email,
                      b.name AS broker_name, b.slug AS broker_slug,
                      pt.target_lot, pt.reward_value, pt.reward_type, pt.label AS tier_label,
                      ib.ib_name, ib.ib_number AS ib_account_number
               FROM rebate_records rr
               JOIN customer_accounts ca ON ca.id = rr.customer_account_id
               JOIN brokers b ON b.id = ca.broker_id
               LEFT JOIN customers c ON c.id = ca.customer_id
               LEFT JOIN program_tiers pt ON pt.id = rr.program_tier_id
               LEFT JOIN ibs ib ON ib.broker_id = ca.broker_id AND ib.ib_number = ca.ib_number
               WHERE rr.batch_id = ?
               ORDER BY ib.ib_name, ca.client_name""",
            (batch_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            result.append(d)
        return result


def get_rebate_records_by_customer_account(customer_account_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT rr.*, rb.period_date, rb.status AS batch_status
               FROM rebate_records rr
               JOIN rebate_batches rb ON rb.id = rr.batch_id
               WHERE rr.customer_account_id = ?
               ORDER BY rb.period_date DESC""",
            (customer_account_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["period_date"] = str(d["period_date"]) if d.get("period_date") else None
            result.append(d)
        return result


def update_rebate_record_status(batch_id: int, customer_account_id: int, status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE rebate_records SET status=? WHERE batch_id=? AND customer_account_id=?",
            (status, batch_id, customer_account_id),
        )


def bulk_update_rebate_status(batch_id: int, status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE rebate_records SET status=? WHERE batch_id=?",
            (status, batch_id),
        )


# ── Program Events (bonus milestone) ──────────────────────────────────────────

def get_paid_bonus_tiers(customer_account_id: int) -> set:
    """Return set of program_tier_ids already paid for this customer_account."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT DISTINCT program_tier_id FROM program_events
               WHERE customer_account_id=? AND event_type='bonus_paid'""",
            (customer_account_id,),
        ).fetchall()
        return {r["program_tier_id"] for r in rows}


def record_bonus_paid(
    customer_account_id: int,
    program_tier_id: int,
    lots_at_event: float,
    amount_usd: float,
    batch_id: int | None = None,
    period_date: str | None = None,
    note: str = "",
) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO program_events
               (customer_account_id, program_tier_id, batch_id, event_type,
                lots_at_event, amount_usd, period_date, note)
               VALUES (?,?,?,?,?,?,?,?)""",
            (customer_account_id, program_tier_id, batch_id, "bonus_paid",
             lots_at_event, amount_usd, period_date, note),
        )


def get_program_events(customer_account_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT pe.*, pt.target_lot, pt.reward_value, pt.label AS tier_label,
                      p.name AS program_name
               FROM program_events pe
               JOIN program_tiers pt ON pt.id = pe.program_tier_id
               JOIN programs p ON p.id = pt.program_id
               WHERE pe.customer_account_id = ?
               ORDER BY pe.created_at DESC""",
            (customer_account_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["period_date"] = str(d["period_date"]) if d.get("period_date") else None
            d["created_at"]  = str(d["created_at"])  if d.get("created_at")  else None
            result.append(d)
        return result
