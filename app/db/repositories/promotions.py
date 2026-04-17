"""Programs, program_tiers and brokers CRUD — SQL Server."""
from app.db.connection import get_conn


# ── Brokers ───────────────────────────────────────────────────────────────────

def get_all_brokers(active_only: bool = True) -> list:
    with get_conn() as conn:
        where = "WHERE is_active=1" if active_only else ""
        rows = conn.execute(
            f"SELECT * FROM brokers {where} ORDER BY display_order"
        ).fetchall()
        return [dict(r) for r in rows]


def get_broker_by_slug(slug: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM brokers WHERE slug=?", (slug,)).fetchone()
        return dict(row) if row else None


def get_broker_by_id(broker_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM brokers WHERE id=?", (broker_id,)).fetchone()
        return dict(row) if row else None


def update_broker(broker_id: int, **fields) -> None:
    """Update broker fields."""
    allowed = {
        "name", "is_active", "display_order",
        "learn_more_url", "transfer_guide_url", "rebate_sequence",
        "logo_url", "logo_color", "rating", "licenses",
        "features", "features_en", "assets_count", "min_deposit",
        "visit_url", "review_url", "review_article_slug",
        "status", "badge_text",
        "extra_stat_label", "extra_stat_value",
        "show_on_brokers_page", "logo_font_size",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE brokers SET {set_clause} WHERE id=?",
            (*updates.values(), broker_id),
        )


# ── Programs ──────────────────────────────────────────────────────────────────

def get_all_programs(active_only: bool = False) -> list:
    with get_conn() as conn:
        where = "WHERE p.is_active=1" if active_only else ""
        rows = conn.execute(
            f"""SELECT p.*,
                       pb_first.broker_id,
                       pb_first.broker_name,
                       pb_first.broker_slug,
                       pb_all.broker_names
                FROM programs p
                LEFT JOIN (
                    SELECT pb.program_id,
                           b.id   AS broker_id,
                           b.name AS broker_name,
                           b.slug AS broker_slug,
                           ROW_NUMBER() OVER (
                               PARTITION BY pb.program_id ORDER BY b.display_order
                           ) AS rn
                    FROM program_brokers pb
                    JOIN brokers b ON b.id = pb.broker_id
                ) pb_first ON pb_first.program_id = p.id AND pb_first.rn = 1
                LEFT JOIN (
                    SELECT pb.program_id,
                           STRING_AGG(b.name, ', ') AS broker_names
                    FROM program_brokers pb
                    JOIN brokers b ON b.id = pb.broker_id
                    GROUP BY pb.program_id
                ) pb_all ON pb_all.program_id = p.id
                {where}
                ORDER BY p.display_order, p.id"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_program(program_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT p.*,
                      pb_first.broker_id,
                      pb_first.broker_name,
                      pb_first.broker_slug,
                      pb_all.broker_names
               FROM programs p
               LEFT JOIN (
                   SELECT pb.program_id,
                          b.id   AS broker_id,
                          b.name AS broker_name,
                          b.slug AS broker_slug,
                          ROW_NUMBER() OVER (
                              PARTITION BY pb.program_id ORDER BY b.display_order
                          ) AS rn
                   FROM program_brokers pb
                   JOIN brokers b ON b.id = pb.broker_id
               ) pb_first ON pb_first.program_id = p.id AND pb_first.rn = 1
               LEFT JOIN (
                   SELECT pb.program_id,
                          STRING_AGG(b.name, ', ') AS broker_names
                   FROM program_brokers pb
                   JOIN brokers b ON b.id = pb.broker_id
                   GROUP BY pb.program_id
               ) pb_all ON pb_all.program_id = p.id
               WHERE p.id=?""",
            (program_id,),
        ).fetchone()
        return dict(row) if row else None


def get_programs_for_broker(broker_id: int, active_only: bool = True) -> list:
    """Programs available at a specific broker."""
    with get_conn() as conn:
        cond = "AND p.is_active=1" if active_only else ""
        rows = conn.execute(
            f"""SELECT p.*
                FROM programs p
                JOIN program_brokers pb ON pb.program_id = p.id
                WHERE pb.broker_id = ? {cond}
                ORDER BY p.display_order""",
            (broker_id,),
        ).fetchall()
        return [dict(r) for r in rows]


CARD_TEMPLATES = ("default", "recommended", "best_rebate", "balance")
REBATE_FREQUENCIES = ("daily", "weekly", "monthly", "on_close")


def create_program(
    name: str,
    type_: str = "backcom",
    is_active: bool = True,
    display_order: int = 0,
    rebate_pct: float = 80.0,
    rebate_usd_per_lot: float | None = None,
    card_template: str = "default",
    is_recommended: bool = False,
    licenses: str | None = None,
    leverage: str | None = None,
    features: str | None = None,
    rebate_xau_label: str | None = None,
    rebate_frequency: str = "daily",
    starts_at: str | None = None,
    ends_at: str | None = None,
    description: str | None = None,
    description_en: str | None = None,
    geo_targets: str | None = None,
) -> int:
    if card_template not in CARD_TEMPLATES:
        card_template = "default"
    if rebate_frequency not in REBATE_FREQUENCIES:
        rebate_frequency = "daily"
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO programs "
            "(name, type, is_active, display_order, rebate_pct, rebate_usd_per_lot, "
            " card_template, is_recommended, licenses, leverage, features, rebate_xau_label, "
            " rebate_frequency, starts_at, ends_at, description, description_en, geo_targets) "
            "OUTPUT INSERTED.id VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (name, type_, int(is_active), display_order, rebate_pct, rebate_usd_per_lot,
             card_template, int(is_recommended), licenses, leverage, features, rebate_xau_label,
             rebate_frequency, starts_at, ends_at, description, description_en, geo_targets),
        )
        row = cur.fetchone()
        return row["id"]


def update_program(
    program_id: int,
    name: str,
    type_: str = "backcom",
    is_active: bool = True,
    display_order: int = 0,
    rebate_pct: float = 80.0,
    rebate_usd_per_lot: float | None = None,
    card_template: str = "default",
    is_recommended: bool = False,
    licenses: str | None = None,
    leverage: str | None = None,
    features: str | None = None,
    rebate_xau_label: str | None = None,
    rebate_frequency: str = "daily",
    starts_at: str | None = None,
    ends_at: str | None = None,
    description: str | None = None,
    description_en: str | None = None,
    geo_targets: str | None = None,
) -> None:
    if card_template not in CARD_TEMPLATES:
        card_template = "default"
    if rebate_frequency not in REBATE_FREQUENCIES:
        rebate_frequency = "daily"
    with get_conn() as conn:
        conn.execute(
            "UPDATE programs SET name=?, type=?, is_active=?, display_order=?, rebate_pct=?, "
            "rebate_usd_per_lot=?, card_template=?, is_recommended=?, licenses=?, leverage=?, "
            "features=?, rebate_xau_label=?, rebate_frequency=?, "
            "starts_at=?, ends_at=?, description=?, description_en=?, geo_targets=? WHERE id=?",
            (name, type_, int(is_active), display_order, rebate_pct, rebate_usd_per_lot,
             card_template, int(is_recommended), licenses, leverage, features, rebate_xau_label,
             rebate_frequency, starts_at, ends_at, description, description_en, geo_targets,
             program_id),
        )


def delete_program(program_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM program_brokers WHERE program_id=?", (program_id,))
        conn.execute("DELETE FROM program_tiers   WHERE program_id=?", (program_id,))
        conn.execute("DELETE FROM programs        WHERE id=?",         (program_id,))


# ── Program Brokers ───────────────────────────────────────────────────────────

def set_program_brokers(program_id: int, broker_ids: list[int]) -> None:
    """Replace the broker list for a program."""
    with get_conn() as conn:
        conn.execute("DELETE FROM program_brokers WHERE program_id=?", (program_id,))
        for bid in broker_ids:
            conn.execute(
                "INSERT INTO program_brokers (program_id, broker_id) VALUES (?,?)",
                (program_id, bid),
            )


def get_program_broker_ids(program_id: int) -> list[int]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT broker_id FROM program_brokers WHERE program_id=?", (program_id,)
        ).fetchall()
        return [r["broker_id"] for r in rows]


# ── Program Tiers ─────────────────────────────────────────────────────────────
#
# target_lot   — minimum cumulative lots for this tier (from Excel backcom_promo.xlsx)
# reward_type  — 'backcom_pct' (fraction, e.g. 0.6 = 60%) | 'bonus_usd' (USD amount)

def get_program_tiers(program_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM program_tiers
               WHERE program_id=?
               ORDER BY target_lot""",
            (program_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_program_tiers() -> dict[int, list]:
    """Return {program_id: [tier_dicts]} for all programs."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM program_tiers ORDER BY program_id, target_lot"
        ).fetchall()
    result: dict[int, list] = {}
    for r in rows:
        pid = r["program_id"]
        result.setdefault(pid, []).append(dict(r))
    return result


def get_tier_by_id(tier_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT pt.*, p.name AS program_name, p.type AS program_type "
            "FROM program_tiers pt JOIN programs p ON p.id=pt.program_id "
            "WHERE pt.id=?",
            (tier_id,),
        ).fetchone()
        return dict(row) if row else None


def resolve_tier_for_volume(program_id: int, total_volume: float) -> dict | None:
    """Return the highest matching tier for a given total_volume (lots traded).

    Backcom: pick tier where target_lot <= total_volume (highest wins).
    Bonus milestone: same logic — caller checks program_events to avoid double-pay.
    """
    with get_conn() as conn:
        row = conn.execute(
            """SELECT TOP 1 * FROM program_tiers
               WHERE program_id=? AND target_lot <= ?
               ORDER BY target_lot DESC""",
            (program_id, total_volume),
        ).fetchone()
        return dict(row) if row else None


def set_program_tiers(program_id: int, tiers: list[dict]) -> None:
    """Replace all tiers for a program (delete + insert).

    Each dict: {tier_number, target_lot, reward_value, reward_type, label}
    """
    with get_conn() as conn:
        conn.execute("DELETE FROM program_tiers WHERE program_id=?", (program_id,))
        for i, t in enumerate(tiers, 1):
            conn.execute(
                """INSERT INTO program_tiers
                   (program_id, tier_number, target_lot, reward_value, reward_type, label)
                   VALUES (?,?,?,?,?,?)""",
                (
                    program_id,
                    int(t.get("tier_number", i)),
                    float(t.get("target_lot", 0)),
                    float(t.get("reward_value", 0)),
                    str(t.get("reward_type", "backcom_pct")),
                    str(t.get("label", "")),
                ),
            )


# ── IB accounts ───────────────────────────────────────────────────────────────

def get_all_ibs(broker_id: int | None = None, active_only: bool = False) -> list:
    conds, params = [], []
    if broker_id:
        conds.append("i.broker_id=?")
        params.append(broker_id)
    if active_only:
        conds.append("i.is_active=1")
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT i.*, b.name AS broker_name, b.slug AS broker_slug
                FROM ibs i
                JOIN brokers b ON b.id = i.broker_id
                {where}
                ORDER BY b.display_order, i.ib_name""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def get_ib_by_number(broker_id: int, ib_number: str) -> dict | None:
    """Find an IB by their trading account number at a specific broker."""
    if not ib_number or not str(ib_number).strip():
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM ibs WHERE broker_id=? AND ib_number=?",
            (broker_id, str(ib_number).strip()),
        ).fetchone()
        return dict(row) if row else None


def upsert_ib(
    broker_id: int,
    use_id: str,
    *,
    ib_name: str = "",
    ib_number: str = "",
    email: str = "",
    country: str = "",
    reff_link: str = "",
    link_spread: float | None = None,
    ib_type: str = "IB",
    is_active: bool = True,
) -> int:
    """Insert or update IB by (broker_id, use_id). Returns ib id."""
    uid = str(use_id).strip() if use_id else ""
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM ibs WHERE broker_id=? AND use_id=?",
            (broker_id, uid),
        ).fetchone() if uid else None

        if existing:
            conn.execute(
                """UPDATE ibs SET
                   ib_name     = CASE WHEN ?<>'' THEN ? ELSE ib_name END,
                   ib_number   = CASE WHEN ?<>'' THEN ? ELSE ib_number END,
                   email       = CASE WHEN ?<>'' THEN ? ELSE email END,
                   country     = CASE WHEN ?<>'' THEN ? ELSE country END,
                   reff_link   = CASE WHEN ?<>'' THEN ? ELSE reff_link END,
                   link_spread = CASE WHEN ? IS NOT NULL THEN ? ELSE link_spread END,
                   ib_type     = ?,
                   is_active   = ?
                   WHERE id=?""",
                (
                    ib_name, ib_name,
                    ib_number, ib_number,
                    email, email,
                    country, country,
                    reff_link, reff_link,
                    link_spread, link_spread,
                    ib_type, int(is_active),
                    existing["id"],
                ),
            )
            return existing["id"]
        else:
            row = conn.execute(
                """INSERT INTO ibs
                   (broker_id, use_id, ib_name, ib_number, email, country,
                    reff_link, link_spread, ib_type, is_active)
                   OUTPUT INSERTED.id
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (broker_id, uid, ib_name, ib_number, email, country,
                 reff_link, link_spread, ib_type, int(is_active)),
            ).fetchone()
            return row["id"] if row else None
