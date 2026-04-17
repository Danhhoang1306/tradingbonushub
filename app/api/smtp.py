"""SMTP configuration API."""
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.db.repositories.smtp import get_smtp_config, save_smtp_config
from app.services.mailer import test_smtp
from app.utils.audit import log_action

router = APIRouter(prefix="/api")


class SmtpSave(BaseModel):
    host: str = "localhost"
    port: int = 25
    username: str = ""
    password: str = ""
    from_email: str = ""
    from_name: str = ""
    use_tls: bool = False
    use_ssl: bool = False


@router.get("/smtp")
async def get_smtp():
    cfg = get_smtp_config()
    cfg.pop("password", None)
    return cfg


@router.post("/smtp")
async def save_smtp(request: Request, payload: SmtpSave):
    if not payload.password:
        existing = get_smtp_config()
        payload.password = existing.get("password", "")
    save_smtp_config(
        payload.host, payload.port, payload.username, payload.password,
        payload.from_email, payload.from_name, payload.use_tls, payload.use_ssl,
    )
    log_action(request.session.get("user", ""), "smtp.save",
               detail={"host": payload.host, "port": payload.port})
    return {"ok": True}


@router.post("/smtp/test")
async def smtp_test(payload: SmtpSave):
    if not payload.password:
        existing = get_smtp_config()
        payload.password = existing.get("password", "")
    cfg = payload.model_dump()
    ok, msg = await test_smtp(cfg)
    return {"ok": ok, "message": msg}
