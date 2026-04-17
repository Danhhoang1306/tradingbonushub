"""Admin user management API."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.db.repositories.users import (
    count_users, create_user, delete_user, get_all_users, get_user,
    update_password, update_user_role,
)
from app.services.auth import hash_pw_async
from app.utils.audit import log_action

router = APIRouter(prefix="/api")


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "admin"


class PasswordChange(BaseModel):
    password: str


class RoleChange(BaseModel):
    role: str


@router.get("/users")
async def list_users():
    return get_all_users()


@router.post("/users", status_code=201)
async def api_create_user(request: Request, payload: UserCreate):
    if not payload.username or not payload.password:
        raise HTTPException(400, "Username and password are required")
    if len(payload.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if get_user(payload.username):
        raise HTTPException(409, "Username already exists")
    role = payload.role if payload.role in ("admin", "editor") else "admin"
    uid = create_user(payload.username, await hash_pw_async(payload.password), role)
    log_action(request.session.get("user", ""), "user.create",
               entity_type="user", entity_id=str(uid),
               detail={"username": payload.username})
    return {"id": uid}


@router.delete("/users/{uid}")
async def api_delete_user(request: Request, uid: int):
    if count_users() <= 1:
        raise HTTPException(400, "Cannot delete the last remaining account")
    delete_user(uid)
    log_action(request.session.get("user", ""), "user.delete",
               entity_type="user", entity_id=str(uid))
    return {"ok": True}


@router.put("/users/{uid}/role")
async def api_change_role(request: Request, uid: int, payload: RoleChange):
    if payload.role not in ("admin", "editor"):
        raise HTTPException(400, "Invalid role (admin or editor)")
    update_user_role(uid, payload.role)
    log_action(request.session.get("user", ""), "user.change_role",
               entity_type="user", entity_id=str(uid),
               detail={"role": payload.role})
    return {"ok": True}


@router.put("/users/{uid}/password")
async def api_change_password(request: Request, uid: int, payload: PasswordChange):
    if not payload.password:
        raise HTTPException(400, "Password is required")
    if len(payload.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    update_password(uid, await hash_pw_async(payload.password))
    log_action(request.session.get("user", ""), "user.change_password",
               entity_type="user", entity_id=str(uid))
    return {"ok": True}
