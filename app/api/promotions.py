"""Programs and brokers API (replaces old promotions API)."""
from fastapi import APIRouter, HTTPException, Request

from app.db.repositories.promotions import (
    create_program, delete_program, get_all_brokers, get_all_programs,
    get_broker_by_id, get_program, get_program_broker_ids, get_program_tiers,
    set_program_brokers, set_program_tiers, update_broker, update_program,
)

router = APIRouter(prefix="/api")


@router.get("/brokers")
async def api_get_brokers():
    return get_all_brokers(active_only=False)


@router.put("/brokers/{broker_id}")
async def api_update_broker(broker_id: int, request: Request):
    b = get_broker_by_id(broker_id)
    if not b:
        raise HTTPException(404, "Broker not found")
    data = await request.json()
    update_broker(broker_id, **data)
    return {"ok": True}


@router.get("/promotions")
async def api_get_promotions():
    """List all programs (legacy endpoint name kept for admin UI compatibility)."""
    return get_all_programs(active_only=False)


def _card_fields(data: dict, p: dict | None = None) -> dict:
    """Extract broker card display fields from request data, falling back to existing program."""
    import json as _json
    p = p or {}
    r_usd = data.get("rebate_usd_per_lot", p.get("rebate_usd_per_lot"))
    # Also parse rebate_per_lot from details_json (legacy rebate_settings save path)
    if r_usd is None and data.get("details_json"):
        try:
            _d = _json.loads(data["details_json"])
            r_usd = _d.get("rebate_per_lot")
        except Exception:
            pass
    def _s(key): return data.get(key, p.get(key)) or None
    return {
        "rebate_usd_per_lot": float(r_usd) if r_usd not in (None, "") else None,
        "card_template":      data.get("card_template", p.get("card_template", "default")) or "default",
        "is_recommended":     bool(data.get("is_recommended", p.get("is_recommended", False))),
        "licenses":           _s("licenses"),
        "leverage":           _s("leverage"),
        "features":           _s("features"),
        "rebate_xau_label":   _s("rebate_xau_label"),
    }


@router.post("/promotions")
async def api_create_promotion(request: Request):
    data = await request.json()
    cf = _card_fields(data)
    pid = create_program(
        name=data["name"].strip(),
        name_en=(data.get("name_en") or "").strip() or None,
        type_=data.get("type", "backcom").strip(),
        is_active=bool(data.get("is_active", True)),
        display_order=int(data.get("display_order", 0)),
        rebate_pct=float(data.get("rebate_pct", 80)),
        rebate_frequency=data.get("rebate_frequency", "daily").strip(),
        starts_at=data.get("starts_at"),
        ends_at=data.get("ends_at"),
        description=data.get("description"),
        description_en=data.get("description_en"),
        geo_targets=data.get("geo_targets"),
        **cf,
    )
    broker_ids = data.get("broker_ids") or []
    if broker_ids:
        set_program_brokers(pid, [int(b) for b in broker_ids])
    return {"id": pid}


@router.put("/promotions/{pid}")
async def api_update_promotion(pid: int, request: Request):
    data = await request.json()
    p = get_program(pid)
    if not p:
        raise HTTPException(404, "Program not found")
    cf = _card_fields(data, p)
    update_program(
        program_id=pid,
        name=data.get("name", p["name"]).strip(),
        name_en=(data.get("name_en") if "name_en" in data else p.get("name_en")) or None,
        type_=data.get("type", p.get("type", "backcom")).strip(),
        is_active=bool(data.get("is_active", p["is_active"])),
        display_order=int(data.get("display_order", p["display_order"])),
        rebate_pct=float(data.get("rebate_pct", p.get("rebate_pct", 80))),
        rebate_frequency=data.get("rebate_frequency", p.get("rebate_frequency", "daily")).strip(),
        starts_at=data.get("starts_at", p.get("starts_at")),
        ends_at=data.get("ends_at", p.get("ends_at")),
        description=data.get("description", p.get("description")),
        description_en=data.get("description_en", p.get("description_en")),
        geo_targets=data.get("geo_targets", p.get("geo_targets")),
        **cf,
    )
    broker_ids = data.get("broker_ids")
    if broker_ids is not None:
        set_program_brokers(pid, [int(b) for b in broker_ids])
    return {"ok": True}


@router.delete("/promotions/{pid}")
async def api_delete_promotion(pid: int):
    if not get_program(pid):
        raise HTTPException(404, "Program not found")
    delete_program(pid)
    return {"ok": True}


@router.get("/promotions/{pid}/tiers")
async def api_get_tiers(pid: int):
    if not get_program(pid):
        raise HTTPException(404, "Program not found")
    return get_program_tiers(pid)


@router.put("/promotions/{pid}/tiers")
async def api_upsert_tiers(pid: int, request: Request):
    """Replace all tiers for a program.
    Body: list of {tier_number, target_lot, reward_value, reward_type, label}
    """
    if not get_program(pid):
        raise HTTPException(404, "Program not found")
    data = await request.json()
    if not isinstance(data, list):
        raise HTTPException(400, "Body must be an array")
    set_program_tiers(pid, data)
    return {"ok": True}


@router.get("/promotions/{pid}/brokers")
async def api_get_program_brokers(pid: int):
    if not get_program(pid):
        raise HTTPException(404, "Program not found")
    return get_program_broker_ids(pid)


@router.put("/promotions/{pid}/brokers")
async def api_set_program_brokers(pid: int, request: Request):
    """Set broker list for a program. Body: list of broker_ids."""
    if not get_program(pid):
        raise HTTPException(404, "Program not found")
    data = await request.json()
    if not isinstance(data, list):
        raise HTTPException(400, "Body must be an array of broker_ids")
    set_program_brokers(pid, [int(b) for b in data])
    return {"ok": True}
