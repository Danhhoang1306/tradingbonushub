"""
rebate_calculator.py — Calculate daily rebates from commission_records

Supports:
  - Program 11 (Backcom STP): backcom_pct x total_commission, tier based on cumulative_volume
  - Program 15 (Gold Trader Bonus):
      + fix_backcom : hang_hoa_lot x 5 USD/lot  (daily)
      + bonus_usd   : one-time bonus when cumulative_hang_hoa_lot passes milestone

Daily flow:
  1. Filter commission_records by uploaded_at = target_date
  2. Filter use_id by active program
  3. Compute new cumulative (SUM entire history) -> update customer_cumulative_stats
  4. Determine current tier
  5. Calculate rebate -> write rebate_records
  6. Update customer_monthly_stats
  7. (Program 15) Check bonus milestone -> write program_events
"""
from datetime import date, datetime
import structlog

from app.db.connection import get_conn

logger = structlog.get_logger(__name__)

_STP_FILTER = "%Standard STP%"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_or_create_daily_batch(conn, period_date: date) -> int:
    row = conn.execute(
        "SELECT id FROM rebate_batches WHERE CAST(period_date AS DATE)=? AND created_by='daily_auto'",
        (str(period_date),),
    ).fetchone()
    if row:
        return row["id"]
    row = conn.execute(
        "INSERT INTO rebate_batches (period_date, created_by, notes) OUTPUT INSERTED.id VALUES (?,?,?)",
        (str(period_date), "daily_auto", f"Daily rebate {period_date}"),
    ).fetchone()
    return row["id"]


def _get_program_accounts(conn, program_id: int) -> dict:
    """Return {use_id: {"ca_id": int, "joined_at": date|None}} for the given program."""
    rows = conn.execute(
        """
        SELECT id AS customer_account_id, use_id, program_joined_at
        FROM customer_accounts
        WHERE program_id=? AND use_id IS NOT NULL AND use_id != ''
        """,
        (program_id,),
    ).fetchall()
    return {
        r["use_id"]: {
            "ca_id": r["customer_account_id"],
            "joined_at": r["program_joined_at"].date() if r["program_joined_at"] else None,
        }
        for r in rows
    }


def _get_stp_accounts(conn, ca_ids: list) -> dict:
    """Return {customer_account_id: set(trading_account)} for Standard STP accounts only."""
    if not ca_ids:
        return {}
    ph = ",".join(["?"] * len(ca_ids))
    rows = conn.execute(
        f"""
        SELECT customer_account_id, trading_account
        FROM trading_accounts
        WHERE customer_account_id IN ({ph}) AND account_type LIKE ? AND is_active=1
        """,
        ca_ids + [_STP_FILTER],
    ).fetchall()
    result: dict = {}
    for r in rows:
        result.setdefault(r["customer_account_id"], set()).add(r["trading_account"])
    return result


def _get_commission_today(conn, target_date: date, use_ids: list,
                          stp_only: bool = False, stp_map: dict = None,
                          use_id_map: dict = None) -> dict:
    """
    Get commission_records for target_date for the given use_ids.
    If stp_only=True, only include trading_accounts that are Standard STP.
    Returns {use_id: {col: float, ...}}
    """
    if not use_ids:
        return {}

    ph = ",".join(["?"] * len(use_ids))
    rows = conn.execute(
        f"""
        SELECT use_id, trading_account,
               total_volume, total_commission,
               fx_lot, fx_commission,
               hang_hoa_lot, hang_hoa_commission,
               index_lot, index_commission,
               crypto_lot, crypto_commission,
               sharecfd_lot, sharecfd_commission,
               bond_lot, bond_commission,
               synthetic_lot, synthetic_commission
        FROM commission_records
        WHERE trading_date=? AND use_id IN ({ph})
        """,
        [str(target_date)] + use_ids,
    ).fetchall()

    _cols = [
        "total_volume", "total_commission",
        "fx_lot", "fx_commission",
        "hang_hoa_lot", "hang_hoa_commission",
        "index_lot", "index_commission",
        "crypto_lot", "crypto_commission",
        "sharecfd_lot", "sharecfd_commission",
        "bond_lot", "bond_commission",
        "synthetic_lot", "synthetic_commission",
    ]

    groups: dict = {}
    for r in rows:
        uid = r["use_id"]

        if stp_only and stp_map and use_id_map:
            ca_id = use_id_map[uid]
            if r["trading_account"] not in stp_map.get(ca_id, set()):
                continue

        if uid not in groups:
            groups[uid] = {c: 0.0 for c in _cols}
            groups[uid]["stp_accounts"] = []

        if stp_only:
            groups[uid]["stp_accounts"].append(r["trading_account"])

        for c in _cols:
            groups[uid][c] += float(r[c] or 0)

    return groups


def _get_monthly_fresh(conn, use_id: str, year: int, month: int,
                        ca_id: int = None, up_to_date: date = None,
                        since: date = None) -> dict:
    """
    Sum hang_hoa_lot + volume + commission for month year/month
    from commission_records, STP accounts only, from start of month to up_to_date.
    since — only count from this date onward (program_joined_at), to avoid counting lots before joining.
    Idempotent — used to check milestones incrementally by day.
    """
    from_date = max(since, date(year, month, 1)) if since else date(year, month, 1)
    month_end = up_to_date or date.today()
    row = conn.execute(
        """
        SELECT SUM(cr.total_volume)     AS total_volume,
               SUM(cr.total_commission) AS total_commission,
               SUM(cr.hang_hoa_lot)     AS hang_hoa_lot
        FROM commission_records cr
        JOIN trading_accounts ta
          ON cr.trading_account = ta.trading_account
         AND ta.customer_account_id = ?
         AND ta.account_type LIKE ?
         AND ta.is_active = 1
        WHERE cr.use_id = ?
          AND cr.trading_date >= ?
          AND cr.trading_date <= ?
        """,
        (ca_id, _STP_FILTER, use_id, str(from_date), str(month_end)),
    ).fetchone()
    return {
        "monthly_volume":       float(row["total_volume"]     or 0),
        "monthly_commission":   float(row["total_commission"] or 0),
        "monthly_hang_hoa_lot": float(row["hang_hoa_lot"]     or 0),
    }


def _get_cumulative_fresh(conn, use_id: str,
                           stp_only: bool = False, ca_id: int = None,
                           since: date = None) -> dict:
    """
    Calculate cumulative from commission_records since date (program_joined_at).
    If since=None, calculate from entire history (not recommended).
    Idempotent — re-running does not cause double counting.
    """
    if stp_only and ca_id:
        params = [ca_id, _STP_FILTER, use_id]
        since_clause = ""
        if since:
            since_clause = "AND cr.trading_date >= ?"
            params.append(str(since))
        row = conn.execute(
            f"""
            SELECT SUM(cr.total_volume)       AS total_volume,
                   SUM(cr.total_commission)   AS total_commission,
                   SUM(cr.hang_hoa_lot)       AS hang_hoa_lot
            FROM commission_records cr
            JOIN trading_accounts ta
              ON cr.trading_account = ta.trading_account
             AND ta.customer_account_id = ?
             AND ta.account_type LIKE ?
             AND ta.is_active = 1
            WHERE cr.use_id = ?
            {since_clause}
            """,
            params,
        ).fetchone()
    else:
        params = [use_id]
        since_clause = ""
        if since:
            since_clause = "AND trading_date >= ?"
            params.append(str(since))
        row = conn.execute(
            f"""
            SELECT SUM(total_volume)     AS total_volume,
                   SUM(total_commission) AS total_commission,
                   SUM(hang_hoa_lot)     AS hang_hoa_lot
            FROM commission_records
            WHERE use_id = ?
            {since_clause}
            """,
            params,
        ).fetchone()

    return {
        "cumulative_volume":       float(row["total_volume"]     or 0),
        "cumulative_commission":   float(row["total_commission"] or 0),
        "cumulative_hang_hoa_lot": float(row["hang_hoa_lot"]     or 0),
    }


def _get_cumulative_batch(conn, accounts: dict, stp_only: bool = False) -> dict:
    """Batch version of _get_cumulative_fresh for multiple users at once.

    accounts: {use_id: {"ca_id": int, "joined_at": date|None}}
    Returns: {use_id: {cumulative_volume, cumulative_commission, cumulative_hang_hoa_lot}}

    Uses temp table to JOIN per-user since_date — 1 query instead of N queries.
    """
    if not accounts:
        return {}

    conn.execute("""
        CREATE TABLE #cum_params (
            use_id NVARCHAR(50) NOT NULL PRIMARY KEY,
            ca_id  INT          NULL,
            since_date DATE     NULL
        )
    """)
    try:
        for uid, acc in accounts.items():
            since = acc.get("joined_at")
            conn.execute(
                "INSERT INTO #cum_params (use_id, ca_id, since_date) VALUES (?, ?, ?)",
                (uid, acc.get("ca_id"), str(since) if since else None),
            )

        if stp_only:
            rows = conn.execute("""
                SELECT cr.use_id,
                       SUM(cr.total_volume)     AS cumulative_volume,
                       SUM(cr.total_commission) AS cumulative_commission,
                       SUM(cr.hang_hoa_lot)     AS cumulative_hang_hoa_lot
                FROM commission_records cr
                JOIN #cum_params p ON cr.use_id = p.use_id
                JOIN trading_accounts ta
                  ON ta.trading_account = cr.trading_account
                 AND ta.customer_account_id = p.ca_id
                 AND ta.account_type LIKE ?
                 AND ta.is_active = 1
                WHERE p.since_date IS NULL OR cr.trading_date >= p.since_date
                GROUP BY cr.use_id
            """, (_STP_FILTER,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT cr.use_id,
                       SUM(cr.total_volume)     AS cumulative_volume,
                       SUM(cr.total_commission) AS cumulative_commission,
                       SUM(cr.hang_hoa_lot)     AS cumulative_hang_hoa_lot
                FROM commission_records cr
                JOIN #cum_params p ON cr.use_id = p.use_id
                WHERE p.since_date IS NULL OR cr.trading_date >= p.since_date
                GROUP BY cr.use_id
            """).fetchall()
    finally:
        try:
            conn.execute("DROP TABLE IF EXISTS #cum_params")
        except Exception:
            pass

    result = {}
    for r in rows:
        result[r["use_id"]] = {
            "cumulative_volume":       float(r["cumulative_volume"] or 0),
            "cumulative_commission":   float(r["cumulative_commission"] or 0),
            "cumulative_hang_hoa_lot": float(r["cumulative_hang_hoa_lot"] or 0),
        }
    for uid in accounts:
        result.setdefault(uid, {
            "cumulative_volume": 0.0, "cumulative_commission": 0.0,
            "cumulative_hang_hoa_lot": 0.0,
        })
    return result


def _get_monthly_batch(conn, accounts: dict, year: int, month: int,
                        target_date: date, stp_only: bool = False) -> dict:
    """Batch version of _get_monthly_fresh for multiple users.

    accounts: {use_id: {"ca_id": int, "joined_at": date|None}}
    Returns: {use_id: {monthly_volume, monthly_commission, monthly_hang_hoa_lot}}
    """
    if not accounts:
        return {}

    first_of_month = date(year, month, 1)

    conn.execute("""
        CREATE TABLE #mon_params (
            use_id     NVARCHAR(50) NOT NULL PRIMARY KEY,
            ca_id      INT          NULL,
            from_date  DATE         NOT NULL
        )
    """)
    try:
        for uid, acc in accounts.items():
            since = acc.get("joined_at")
            from_date = max(since, first_of_month) if since else first_of_month
            conn.execute(
                "INSERT INTO #mon_params (use_id, ca_id, from_date) VALUES (?, ?, ?)",
                (uid, acc.get("ca_id"), str(from_date)),
            )

        if stp_only:
            rows = conn.execute("""
                SELECT cr.use_id,
                       SUM(cr.total_volume)     AS monthly_volume,
                       SUM(cr.total_commission) AS monthly_commission,
                       SUM(cr.hang_hoa_lot)     AS monthly_hang_hoa_lot
                FROM commission_records cr
                JOIN #mon_params p ON cr.use_id = p.use_id
                JOIN trading_accounts ta
                  ON ta.trading_account = cr.trading_account
                 AND ta.customer_account_id = p.ca_id
                 AND ta.account_type LIKE ?
                 AND ta.is_active = 1
                WHERE cr.trading_date >= p.from_date
                  AND cr.trading_date <= ?
                GROUP BY cr.use_id
            """, (_STP_FILTER, str(target_date))).fetchall()
        else:
            rows = conn.execute("""
                SELECT cr.use_id,
                       SUM(cr.total_volume)     AS monthly_volume,
                       SUM(cr.total_commission) AS monthly_commission,
                       SUM(cr.hang_hoa_lot)     AS monthly_hang_hoa_lot
                FROM commission_records cr
                JOIN #mon_params p ON cr.use_id = p.use_id
                WHERE cr.trading_date >= p.from_date
                  AND cr.trading_date <= ?
                GROUP BY cr.use_id
            """, (str(target_date),)).fetchall()
    finally:
        try:
            conn.execute("DROP TABLE IF EXISTS #mon_params")
        except Exception:
            pass

    result = {}
    for r in rows:
        result[r["use_id"]] = {
            "monthly_volume":       float(r["monthly_volume"] or 0),
            "monthly_commission":   float(r["monthly_commission"] or 0),
            "monthly_hang_hoa_lot": float(r["monthly_hang_hoa_lot"] or 0),
        }
    for uid in accounts:
        result.setdefault(uid, {
            "monthly_volume": 0.0, "monthly_commission": 0.0,
            "monthly_hang_hoa_lot": 0.0,
        })
    return result


def _fetch_tiers(conn, program_id: int, reward_type_filter: str = None) -> list:
    """Fetch all tiers for a program once — used to cache in the loop."""
    return conn.execute(
        """
        SELECT id, tier_number, target_lot, reward_value, reward_type
        FROM program_tiers
        WHERE program_id=? AND tier_number > 0
          AND (? IS NULL OR reward_type=?)
        ORDER BY target_lot DESC
        """,
        (program_id, reward_type_filter, reward_type_filter),
    ).fetchall()


def _determine_tier(conn, program_id: int, cumulative_volume: float,
                    cumulative_hang_hoa: float, reward_type_filter: str = None) -> dict | None:
    """
    Determine current tier based on cumulative values.
    - Program 11: uses cumulative_volume, reward_type='backcom_pct'
    - Program 15 bonus: uses cumulative_hang_hoa, reward_type='bonus_usd'
    Returns row dict or None if not enough lots.
    """
    tiers = conn.execute(
        """
        SELECT id, tier_number, target_lot, reward_value, reward_type
        FROM program_tiers
        WHERE program_id=? AND tier_number > 0
          AND (? IS NULL OR reward_type=?)
        ORDER BY target_lot DESC
        """,
        (program_id, reward_type_filter, reward_type_filter),
    ).fetchall()

    check_val = cumulative_hang_hoa if reward_type_filter == "bonus_usd" else cumulative_volume

    for t in tiers:
        if check_val >= float(t["target_lot"]):
            return dict(t)
    return None


def _upsert_cumulative_stats(conn, use_id: str, program_id: int,
                              cum: dict, tier_id: int | None, today: date) -> None:
    conn.execute(
        """
        MERGE customer_cumulative_stats AS t
        USING (VALUES (?)) AS s(use_id) ON t.use_id = s.use_id
        WHEN MATCHED THEN UPDATE SET
            program_id              = ?,
            cumulative_volume       = ?,
            cumulative_commission   = ?,
            cumulative_hang_hoa_lot = ?,
            current_tier_id         = ?,
            last_updated            = ?
        WHEN NOT MATCHED THEN INSERT
            (use_id, program_id, cumulative_volume, cumulative_commission,
             cumulative_hang_hoa_lot, current_tier_id, last_updated)
        VALUES (?,?,?,?,?,?,?);
        """,
        [
            use_id,
            # UPDATE
            program_id,
            cum["cumulative_volume"], cum["cumulative_commission"],
            cum["cumulative_hang_hoa_lot"], tier_id, str(today),
            # INSERT
            use_id, program_id,
            cum["cumulative_volume"], cum["cumulative_commission"],
            cum["cumulative_hang_hoa_lot"], tier_id, str(today),
        ],
    )


def _upsert_monthly_stats(conn, use_id: str, program_id: int,
                           year: int, month: int,
                           volume: float, commission: float,
                           hang_hoa: float, rebate: float) -> None:
    conn.execute(
        """
        MERGE customer_monthly_stats AS t
        USING (VALUES (?,?,?)) AS s(use_id, year, month)
        ON t.use_id=s.use_id AND t.year=s.year AND t.month=s.month
        WHEN MATCHED THEN UPDATE SET
            monthly_volume       = ?,
            monthly_commission   = ?,
            monthly_hang_hoa_lot = ?,
            monthly_rebate       = ?,
            updated_at           = GETDATE()
        WHEN NOT MATCHED THEN INSERT
            (use_id, program_id, year, month,
             monthly_volume, monthly_commission, monthly_hang_hoa_lot,
             monthly_rebate, updated_at)
        VALUES (?,?,?,?, ?,?,?,?, GETDATE());
        """,
        [
            use_id, year, month,
            # UPDATE
            volume, commission, hang_hoa, rebate,
            # INSERT
            use_id, program_id, year, month,
            volume, commission, hang_hoa, rebate,
        ],
    )



def _upsert_rebate_record(conn, batch_id: int, ca_id: int,
                           tier_id: int, program_id: int, g: dict,
                           rebate_amount: float, period_date: date = None) -> None:
    """MERGE on (batch_id, customer_account_id, program_tier_id) — one row per tier per day."""
    conn.execute(
        """
        MERGE rebate_records AS t
        USING (VALUES (?,?,?)) AS s(batch_id, customer_account_id, program_tier_id)
        ON t.batch_id=s.batch_id
           AND t.customer_account_id=s.customer_account_id
           AND t.program_tier_id=s.program_tier_id
        WHEN MATCHED THEN UPDATE SET
            program_id           = ?,
            total_volume         = ?, total_commission    = ?,
            fx_lot               = ?, fx_commission       = ?,
            hang_hoa_lot         = ?, hang_hoa_commission = ?,
            index_lot            = ?, index_commission    = ?,
            crypto_lot           = ?, crypto_commission   = ?,
            sharecfd_lot         = ?, sharecfd_commission = ?,
            bond_lot             = ?, bond_commission     = ?,
            synthetic_lot        = ?, synthetic_commission= ?,
            rebate_amount        = ?,
            period_date          = ?,
            status               = 'pending'
        WHEN NOT MATCHED THEN INSERT (
            batch_id, customer_account_id, program_tier_id, program_id,
            total_volume, total_commission,
            fx_lot, fx_commission, hang_hoa_lot, hang_hoa_commission,
            index_lot, index_commission, crypto_lot, crypto_commission,
            sharecfd_lot, sharecfd_commission, bond_lot, bond_commission,
            synthetic_lot, synthetic_commission, rebate_amount, period_date, status
        ) VALUES (
            ?,?,?,?, ?,?, ?,?,?,?, ?,?,?,?, ?,?,?,?, ?,?, ?,?,'pending'
        );
        """,
        [
            batch_id, ca_id, tier_id,
            # UPDATE
            program_id,
            g["total_volume"],    g["total_commission"],
            g["fx_lot"],          g["fx_commission"],
            g["hang_hoa_lot"],    g["hang_hoa_commission"],
            g["index_lot"],       g["index_commission"],
            g["crypto_lot"],      g["crypto_commission"],
            g["sharecfd_lot"],    g["sharecfd_commission"],
            g["bond_lot"],        g["bond_commission"],
            g["synthetic_lot"],   g["synthetic_commission"],
            rebate_amount,
            str(period_date) if period_date else None,
            # INSERT
            batch_id, ca_id, tier_id, program_id,
            g["total_volume"],    g["total_commission"],
            g["fx_lot"],          g["fx_commission"],
            g["hang_hoa_lot"],    g["hang_hoa_commission"],
            g["index_lot"],       g["index_commission"],
            g["crypto_lot"],      g["crypto_commission"],
            g["sharecfd_lot"],    g["sharecfd_commission"],
            g["bond_lot"],        g["bond_commission"],
            g["synthetic_lot"],   g["synthetic_commission"],
            rebate_amount,
            str(period_date) if period_date else None,
        ],
    )


# ── Program 11: Backcom STP ────────────────────────────────────────────────────

def calculate_program11_daily(target_date: date) -> dict:
    """
    Calculate daily backcom by tier for Program 11.
    rebate = SUM(total_commission) x tier.backcom_pct
    Tier determined by cumulative_volume (accumulated from program start).
    """
    log = logger.bind(program=11, date=str(target_date))

    with get_conn() as conn:
        # 1. Get list of use_ids enrolled in program 11
        use_id_map = _get_program_accounts(conn, program_id=11)
        if not use_id_map:
            log.info("No accounts in program 11")
            return {"date": str(target_date), "batch_id": None,
                    "processed": 0, "total_rebate": 0.0, "details": []}

        # 2. Get today's commission data (no STP filter — program 11 applies to all)
        groups = _get_commission_today(conn, target_date, list(use_id_map.keys()))
        if not groups:
            log.info("No commission data for date")
            return {"date": str(target_date), "batch_id": None,
                    "processed": 0, "total_rebate": 0.0, "details": []}

        batch_id = _get_or_create_daily_batch(conn, target_date)

        # 3. Calculate cumulative for all users at once (1 query instead of N queries)
        active_accounts = {uid: use_id_map[uid] for uid in groups}
        cum_map = _get_cumulative_batch(conn, active_accounts, stp_only=False)

        # 4. Cache tiers once (no re-fetching inside loop)
        tiers_p11 = [dict(t) for t in _fetch_tiers(conn, 11, "backcom_pct")]

        details = []
        total_rebate = 0.0

        for use_id, g in groups.items():
            acc = use_id_map[use_id]
            ca_id     = acc["ca_id"]
            joined_at = acc["joined_at"]
            cum       = cum_map[use_id]

            # Determine tier from cached list
            cumulative_volume = cum["cumulative_volume"]
            tier = next(
                (t for t in tiers_p11 if cumulative_volume >= float(t["target_lot"])),
                None,
            )

            if not tier:
                log.info("Below minimum lot for any tier", use_id=use_id,
                         cumulative_volume=cumulative_volume)
                _upsert_cumulative_stats(conn, use_id, 11, cum, None, target_date)
                _upsert_monthly_stats(
                    conn, use_id, 11,
                    target_date.year, target_date.month,
                    g["total_volume"], g["total_commission"],
                    g.get("hang_hoa_lot", 0.0), 0.0,
                )
                continue

            # 5. Calculate rebate
            backcom_pct = tier["reward_value"]
            rebate_amount = round(g["total_commission"] * backcom_pct, 2)
            total_rebate += rebate_amount

            # 6. Write rebate_records
            _upsert_rebate_record(conn, batch_id, ca_id, tier["id"], 11, g, rebate_amount, target_date)

            # 7. Update cumulative_stats + monthly_stats
            _upsert_cumulative_stats(conn, use_id, 11, cum, tier["id"], target_date)
            _upsert_monthly_stats(
                conn, use_id, 11,
                target_date.year, target_date.month,
                g["total_volume"], g["total_commission"], 0.0, rebate_amount,
            )

            details.append({
                "use_id": use_id,
                "customer_account_id": ca_id,
                "joined_at": str(joined_at) if joined_at else None,
                "cumulative_volume": cumulative_volume,
                "tier_label": f"Tier {tier['tier_number']}",
                "backcom_pct": backcom_pct,
                "total_commission_today": round(g["total_commission"], 2),
                "rebate_amount": rebate_amount,
            })
            log.info("p11 rebate", use_id=use_id,
                     cumulative_volume=cumulative_volume,
                     tier=tier["tier_number"], rebate=rebate_amount)

        # Update batch totals
        conn.execute(
            "UPDATE rebate_batches SET total_rows=?, total_amount=? WHERE id=?",
            (len(details), round(total_rebate, 2), batch_id),
        )

        return {
            "date": str(target_date),
            "batch_id": batch_id,
            "processed": len(details),
            "total_rebate": round(total_rebate, 2),
            "details": details,
        }


# ── Program 15: Gold Trader Bonus ──────────────────────────────────────────────

def calculate_program15_daily(target_date: date) -> dict:
    """
    Program 15 — 2 types of rebate:
    A) fix_backcom: SUM(hang_hoa_lot of STP accounts) x 5 USD/lot  (daily)
    B) bonus_usd:   one-time bonus when cumulative_hang_hoa_lot passes milestone
    """
    log = logger.bind(program=15, date=str(target_date))

    with get_conn() as conn:
        # Get fix_backcom tier (id=32)
        tier_fix = conn.execute(
            "SELECT id, reward_value FROM program_tiers WHERE id=32"
        ).fetchone()
        if not tier_fix:
            raise ValueError("program_tiers id=32 (fix_backcom) does not exist")
        fix_backcom = float(tier_fix["reward_value"])

        # 1. Get list of use_ids enrolled in program 15
        use_id_map = _get_program_accounts(conn, program_id=15)
        if not use_id_map:
            log.info("No accounts in program 15")
            return {"date": str(target_date), "batch_id": None,
                    "processed": 0, "total_rebate": 0.0, "details": []}

        ca_ids = [v["ca_id"] for v in use_id_map.values()]
        # _get_commission_today expects {use_id: ca_id} — build compat map
        _use_id_ca_map = {uid: v["ca_id"] for uid, v in use_id_map.items()}

        # 2. Get STP trading accounts
        stp_map = _get_stp_accounts(conn, ca_ids)

        # 3. Get today's commission data (STP only)
        groups = _get_commission_today(
            conn, target_date, list(use_id_map.keys()),
            stp_only=True, stp_map=stp_map, use_id_map=_use_id_ca_map,
        )
        if not groups:
            log.info("No STP commission data for date")
            return {"date": str(target_date), "batch_id": None,
                    "processed": 0, "total_rebate": 0.0, "details": []}

        batch_id = _get_or_create_daily_batch(conn, target_date)

        # Filter to users with hang_hoa_lot > 0
        active_groups = {uid: g for uid, g in groups.items() if g["hang_hoa_lot"] != 0}
        active_accounts = {uid: use_id_map[uid] for uid in active_groups}

        # 4. Batch cumulative + monthly (1 query per type instead of N queries)
        cum_map = _get_cumulative_batch(conn, active_accounts, stp_only=True)
        mon_map = _get_monthly_batch(
            conn, active_accounts,
            target_date.year, target_date.month, target_date,
            stp_only=True,
        )

        # Cache bonus tiers (bonus_usd only)
        bonus_tiers_p15 = [dict(t) for t in _fetch_tiers(conn, 15, "bonus_usd")]

        details = []
        total_rebate = 0.0

        for use_id, g in active_groups.items():
            acc = use_id_map[use_id]
            ca_id = acc["ca_id"]
            cum   = cum_map[use_id]
            mon   = mon_map[use_id]
            month_hoa = mon["monthly_hang_hoa_lot"]

            # ── A) daily fix_backcom ──────────────────────────────────────
            rebate_fix = round(g["hang_hoa_lot"] * fix_backcom, 2)
            total_rebate += rebate_fix

            _upsert_rebate_record(conn, batch_id, ca_id,
                                  tier_fix["id"], 15, g, rebate_fix, target_date)

            # 5. Update cumulative_stats + monthly_stats
            bonus_tier = next(
                (t for t in bonus_tiers_p15 if month_hoa >= float(t["target_lot"])),
                None,
            )
            _upsert_cumulative_stats(
                conn, use_id, 15, cum,
                bonus_tier["id"] if bonus_tier else None,
                target_date,
            )
            monthly_rebate_total = round(month_hoa * fix_backcom, 2)
            _upsert_monthly_stats(
                conn, use_id, 15,
                target_date.year, target_date.month,
                mon["monthly_volume"], mon["monthly_commission"],
                month_hoa, monthly_rebate_total,
            )

            details.append({
                "use_id": use_id,
                "customer_account_id": ca_id,
                "stp_accounts": g["stp_accounts"],
                "hang_hoa_lot_today": round(g["hang_hoa_lot"], 4),
                "cumulative_hang_hoa_lot": round(cum["cumulative_hang_hoa_lot"], 4),
                "fix_backcom_usd": fix_backcom,
                "rebate_fix": rebate_fix,
            })
            log.info("p15 rebate", use_id=use_id,
                     hang_hoa=g["hang_hoa_lot"], rebate_fix=rebate_fix)

        # Update batch totals
        conn.execute(
            "UPDATE rebate_batches SET total_rows=?, total_amount=? WHERE id=?",
            (len(details), round(total_rebate, 2), batch_id),
        )

        return {
            "date": str(target_date),
            "batch_id": batch_id,
            "processed": len(details),
            "total_rebate": round(total_rebate, 2),
            "details": details,
        }


# ── Entry point ────────────────────────────────────────────────────────────────

def run_daily_rebate(target_date: date = None) -> dict:
    """
    Run all rebate programs for a given day.
    Call this after commission_records upload is complete.

    Usage:
        from app.services.rebate_calculator import run_daily_rebate
        result = run_daily_rebate()           # today
        result = run_daily_rebate(date(...))  # specific date
    """
    if target_date is None:
        target_date = date.today()

    logger.info("run_daily_rebate start", date=str(target_date))

    # Auto-downgrade expired promos before calculating
    try:
        from app.api.promo import downgrade_expired_promos
        downgraded = downgrade_expired_promos()
        if downgraded:
            logger.info("promo.auto_downgraded", count=downgraded)
    except Exception as exc:
        logger.warning("promo.downgrade_check_failed", error=str(exc))

    p11 = calculate_program11_daily(target_date)
    p15 = calculate_program15_daily(target_date)

    return {
        "date": str(target_date),
        "program_11": p11,
        "program_15": p15,
    }
