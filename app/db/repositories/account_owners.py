"""Account owner repository — delegates to the ibs table.

The account_owners table has been removed.
IBs are now stored in the ibs table (managed via promotions.py).
This module provides backward-compatible access for existing API consumers.
"""
from app.db.connection import get_conn


def get_all_account_owners(broker_id: int | None = None) -> list:
    conds, params = [], []
    if broker_id:
        conds.append("i.broker_id=?")
        params.append(broker_id)
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


def get_account_owner(oid: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT i.*, b.name AS broker_name, b.slug AS broker_slug
               FROM ibs i
               JOIN brokers b ON b.id = i.broker_id
               WHERE i.id=?""",
            (oid,),
        ).fetchone()
        return dict(row) if row else None


def create_account_owner(
    ib_name: str,
    email: str = "",
    broker_id: int | None = None,
    ib_number: str = "",
    reff_link: str = "",
    use_id: str = "",
    ib_type: str = "IB",
    is_active: bool = True,
    **_ignored,
) -> int:
    with get_conn() as conn:
        row = conn.execute(
            """INSERT INTO ibs
               (broker_id, use_id, ib_name, ib_number, email, reff_link, ib_type, is_active)
               OUTPUT INSERTED.id
               VALUES (?,?,?,?,?,?,?,?)""",
            (broker_id, use_id or "", ib_name, ib_number, email,
             reff_link, ib_type, int(is_active)),
        ).fetchone()
        return row["id"] if row else None


def update_account_owner(
    oid: int,
    ib_name: str,
    email: str = "",
    broker_id: int | None = None,
    ib_number: str = "",
    reff_link: str = "",
    use_id: str = "",
    ib_type: str = "IB",
    is_active: bool = True,
    **_ignored,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """UPDATE ibs SET
               ib_name=?, email=?, broker_id=?, ib_number=?,
               reff_link=?, use_id=?, ib_type=?, is_active=?
               WHERE id=?""",
            (ib_name, email, broker_id, ib_number,
             reff_link, use_id or "", ib_type, int(is_active), oid),
        )


def delete_account_owner(oid: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM ibs WHERE id=?", (oid,))


# ── Broker IB config (removed — stubs for import compatibility) ───────────────

def get_broker_ib_config(broker_slug: str) -> dict:
    return {}


def get_default_reg_type(broker_slug: str, ib_config: dict | None = None) -> str:
    return "default"
