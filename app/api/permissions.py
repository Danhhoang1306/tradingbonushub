"""Granular role-based permissions API."""
import json

from fastapi import APIRouter, HTTPException, Request

from app.db.connection import get_conn
from app.utils.audit import log_action

router = APIRouter(prefix="/api/admin/roles", tags=["permissions"])

# All available permission modules
PERMISSION_MODULES = [
    "campaigns.*",    "templates.*",   "emails.*",
    "customers.*",    "enrollments.*", "leads.*",
    "promotions.*",   "rebate.*",      "wallet.*",
    "payment.*",      "cms.*",         "media.*",
    "faq.*",          "settings.*",    "system.*",
    "analytics.*",    "scheduling.*",  "segments.*",
    "portal_settings.*", "brokers.*",  "promo.*",
]


def _require_admin(request: Request) -> str:
    user = request.session.get("user")
    role = request.session.get("user_role", "admin")
    if not user or role != "admin":
        raise HTTPException(403, "Admin role required")
    return user


def check_permission(request: Request, module: str) -> bool:
    """Check if current user has permission for a module.

    Returns True if:
    - User role is 'admin' (has all permissions)
    - User's role includes '*' or the specific module
    """
    role = request.session.get("user_role", "admin")
    if role == "admin":
        return True

    role_id = request.session.get("role_id")
    if not role_id:
        return False

    with get_conn() as conn:
        row = conn.execute(
            "SELECT permissions FROM admin_roles WHERE id=?", (role_id,)
        ).fetchone()
        if not row:
            return False
        try:
            perms = json.loads(row["permissions"])
        except (json.JSONDecodeError, TypeError):
            return False

        if "*" in perms:
            return True

        # Check exact match or wildcard
        module_prefix = module.split(".")[0] + ".*"
        return module in perms or module_prefix in perms


@router.get("")
async def api_list_roles(request: Request):
    """List all admin roles."""
    _require_admin(request)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT r.*, "
            "(SELECT COUNT(*) FROM users u WHERE u.role_id = r.id) AS user_count "
            "FROM admin_roles r ORDER BY r.id"
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["permissions"] = json.loads(d["permissions"])
        except (json.JSONDecodeError, TypeError):
            d["permissions"] = []
        result.append(d)
    return result


@router.get("/modules")
async def api_list_modules(request: Request):
    """List all available permission modules."""
    _require_admin(request)
    return PERMISSION_MODULES


@router.post("")
async def api_create_role(request: Request):
    """Create a new admin role."""
    admin = _require_admin(request)
    data = await request.json()
    name = (data.get("name") or "").strip()
    permissions = data.get("permissions", [])

    if not name:
        raise HTTPException(400, "Role name is required")
    if not isinstance(permissions, list):
        raise HTTPException(400, "Permissions must be an array")

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM admin_roles WHERE name=?", (name,)
        ).fetchone()
        if existing:
            raise HTTPException(400, f"Role '{name}' already exists")

        row = conn.execute(
            "INSERT INTO admin_roles (name, permissions) OUTPUT INSERTED.id VALUES (?, ?)",
            (name, json.dumps(permissions)),
        ).fetchone()

    log_action(admin, "role.create", entity_type="role", entity_id=str(row["id"]),
               detail={"name": name, "permissions": permissions})
    return {"ok": True, "id": row["id"]}


@router.put("/{role_id}")
async def api_update_role(role_id: int, request: Request):
    """Update a role's name and permissions."""
    admin = _require_admin(request)
    data = await request.json()

    with get_conn() as conn:
        role = conn.execute("SELECT * FROM admin_roles WHERE id=?", (role_id,)).fetchone()
        if not role:
            raise HTTPException(404, "Role not found")

        name = (data.get("name") or role["name"]).strip()
        permissions = data.get("permissions")
        if permissions is not None:
            if not isinstance(permissions, list):
                raise HTTPException(400, "Permissions must be an array")
            perm_json = json.dumps(permissions)
        else:
            perm_json = role["permissions"]

        conn.execute(
            "UPDATE admin_roles SET name=?, permissions=? WHERE id=?",
            (name, perm_json, role_id),
        )

    log_action(admin, "role.update", entity_type="role", entity_id=str(role_id),
               detail={"name": name})
    return {"ok": True}


@router.delete("/{role_id}")
async def api_delete_role(role_id: int, request: Request):
    """Delete a role (unassigns users first)."""
    admin = _require_admin(request)

    with get_conn() as conn:
        role = conn.execute("SELECT name FROM admin_roles WHERE id=?", (role_id,)).fetchone()
        if not role:
            raise HTTPException(404, "Role not found")
        if role["name"] == "admin":
            raise HTTPException(400, "Cannot delete the 'admin' role")

        # Unassign users
        conn.execute("UPDATE users SET role_id=NULL WHERE role_id=?", (role_id,))
        conn.execute("DELETE FROM admin_roles WHERE id=?", (role_id,))

    log_action(admin, "role.delete", entity_type="role", entity_id=str(role_id),
               detail={"name": role["name"]})
    return {"ok": True}


@router.put("/users/{uid}/assign")
async def api_assign_role(uid: int, request: Request):
    """Assign a role to a user."""
    admin = _require_admin(request)
    data = await request.json()
    role_id = data.get("role_id")

    with get_conn() as conn:
        user = conn.execute("SELECT username FROM users WHERE id=?", (uid,)).fetchone()
        if not user:
            raise HTTPException(404, "User not found")

        if role_id:
            role = conn.execute("SELECT name FROM admin_roles WHERE id=?", (role_id,)).fetchone()
            if not role:
                raise HTTPException(404, "Role not found")
            conn.execute("UPDATE users SET role_id=?, role=? WHERE id=?",
                         (role_id, role["name"], uid))
        else:
            conn.execute("UPDATE users SET role_id=NULL, role='admin' WHERE id=?", (uid,))

    log_action(admin, "user.assign_role", entity_type="user", entity_id=str(uid),
               detail={"role_id": role_id})
    return {"ok": True}


@router.get("/users")
async def api_list_users_with_roles(request: Request):
    """List all admin users with their role info."""
    _require_admin(request)
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT u.id, u.username, u.role, u.role_id,
                   r.name AS role_name,
                   r.permissions AS role_permissions,
                   CASE WHEN u.totp_secret IS NOT NULL THEN 1 ELSE 0 END AS totp_enabled
            FROM users u
            LEFT JOIN admin_roles r ON r.id = u.role_id
            ORDER BY u.id
        """).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["role_permissions"] = json.loads(d["role_permissions"] or "[]")
        except (json.JSONDecodeError, TypeError):
            d["role_permissions"] = []
        result.append(d)
    return result
