"""IB management API (replaces account owners)."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from app.db.repositories.account_owners import (
    create_account_owner, delete_account_owner, get_account_owner,
    get_all_account_owners, update_account_owner,
)
from app.db.repositories.promotions import get_all_programs

router = APIRouter(prefix="/api")


def _to_int_or_none(val) -> Optional[int]:
    try:
        v = int(val)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def _extract(data: dict) -> dict:
    return dict(
        ib_name=(data.get("ib_name") or "").strip(),
        email=(data.get("email") or data.get("gmail") or "").strip(),
        broker_id=_to_int_or_none(data.get("broker_id")),
        ib_number=(data.get("ib_number") or "").strip(),
        reff_link=(data.get("reff_link") or data.get("ib_link") or "").strip(),
        use_id=(data.get("use_id") or "").strip(),
        ib_type=(data.get("ib_type") or "IB").strip(),
        is_active=bool(data.get("is_active", True)),
    )


@router.get("/account-owners")
async def api_get_account_owners(broker_id: Optional[int] = None):
    return get_all_account_owners(broker_id=broker_id)


@router.get("/account-owners/programs-for-select")
async def api_get_programs_for_ao():
    """Programs for IB dropdowns in admin UI."""
    progs = get_all_programs(active_only=False)
    return [{"id": p["id"], "name": p["name"], "type": p.get("type", "")} for p in progs]


@router.post("/account-owners")
async def api_create_account_owner(request: Request):
    data = await request.json()
    fields = _extract(data)
    if not fields["ib_name"]:
        raise HTTPException(400, "IB name is required")
    oid = create_account_owner(**fields)
    return {"id": oid}


@router.put("/account-owners/{oid}")
async def api_update_account_owner(oid: int, request: Request):
    data = await request.json()
    owner = get_account_owner(oid)
    if not owner:
        raise HTTPException(404, "IB not found")
    fields = _extract(data)
    if not fields["ib_name"]:
        fields["ib_name"] = owner["ib_name"]
    update_account_owner(oid=oid, **fields)
    return {"ok": True}


@router.delete("/account-owners/{oid}")
async def api_delete_account_owner(oid: int):
    if not get_account_owner(oid):
        raise HTTPException(404, "IB not found")
    delete_account_owner(oid)
    return {"ok": True}
