"""Content versioning API — save/restore snapshots of articles and page content."""
import json

from fastapi import APIRouter, HTTPException, Query, Request

from app.db.connection import get_conn
from app.utils.audit import log_action

router = APIRouter(prefix="/api/versions", tags=["content-versions"])


def _require_admin(request: Request) -> str:
    user = request.session.get("user")
    if not user:
        raise HTTPException(403, "Admin required")
    return user


@router.get("/{entity_type}/{entity_id}")
async def api_list_versions(entity_type: str, entity_id: int, request: Request,
                             limit: int = Query(20, le=100)):
    """List saved versions for an entity (article, page_content, etc.)."""
    _require_admin(request)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, version_num, created_by, created_at "
            "FROM content_versions "
            "WHERE entity_type=? AND entity_id=? "
            "ORDER BY version_num DESC "
            "OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY",
            (entity_type, entity_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/{entity_type}/{entity_id}/{version_id}")
async def api_get_version(entity_type: str, entity_id: int, version_id: int,
                           request: Request):
    """Get a specific version's data."""
    _require_admin(request)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM content_versions WHERE id=? AND entity_type=? AND entity_id=?",
            (version_id, entity_type, entity_id),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Version not found")
        d = dict(row)
        try:
            d["data"] = json.loads(d["data_json"])
        except (json.JSONDecodeError, TypeError):
            d["data"] = {}
    return d


@router.post("/{entity_type}/{entity_id}")
async def api_save_version(entity_type: str, entity_id: int, request: Request):
    """Save current state as a new version."""
    admin = _require_admin(request)
    data = await request.json()
    content_data = data.get("data", {})

    with get_conn() as conn:
        # Get next version number
        max_ver = conn.execute(
            "SELECT ISNULL(MAX(version_num), 0) AS mx "
            "FROM content_versions WHERE entity_type=? AND entity_id=?",
            (entity_type, entity_id),
        ).fetchone()["mx"]

        version_num = max_ver + 1

        row = conn.execute(
            "INSERT INTO content_versions (entity_type, entity_id, version_num, data_json, created_by) "
            "OUTPUT INSERTED.id VALUES (?, ?, ?, ?, ?)",
            (entity_type, entity_id, version_num, json.dumps(content_data), admin),
        ).fetchone()

    log_action(admin, "version.save", entity_type=entity_type, entity_id=str(entity_id),
               detail={"version_num": version_num})
    return {"ok": True, "id": row["id"], "version_num": version_num}


@router.post("/{entity_type}/{entity_id}/{version_id}/restore")
async def api_restore_version(entity_type: str, entity_id: int, version_id: int,
                               request: Request):
    """Restore an entity to a previous version."""
    admin = _require_admin(request)

    with get_conn() as conn:
        ver = conn.execute(
            "SELECT * FROM content_versions WHERE id=? AND entity_type=? AND entity_id=?",
            (version_id, entity_type, entity_id),
        ).fetchone()
        if not ver:
            raise HTTPException(404, "Version not found")

        try:
            data = json.loads(ver["data_json"])
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(400, "Invalid version data")

        # Restore based on entity type
        if entity_type == "cms_article":
            _restore_article(conn, entity_id, data)
        elif entity_type == "page_content":
            _restore_page_content(conn, entity_id, data)
        else:
            raise HTTPException(400, f"Unknown entity type: {entity_type}")

    log_action(admin, "version.restore", entity_type=entity_type, entity_id=str(entity_id),
               detail={"version_id": version_id, "version_num": ver["version_num"]})
    return {"ok": True, "restored_version": ver["version_num"]}


def _restore_article(conn, article_id: int, data: dict):
    """Restore an article from version data."""
    allowed_fields = {
        "title", "excerpt", "content", "seo_title", "seo_desc", "seo_image",
        "title_en", "excerpt_en", "content_en", "seo_title_en", "seo_desc_en",
        "status", "lang", "type",
    }
    updates = {k: v for k, v in data.items() if k in allowed_fields}
    if not updates:
        return

    set_clause = ", ".join(f"{k}=?" for k in updates)
    conn.execute(
        f"UPDATE cms_articles SET {set_clause}, updated_at=GETDATE() WHERE id=?",
        (*updates.values(), article_id),
    )


def _restore_page_content(conn, content_id: int, data: dict):
    """Restore page content from version data."""
    value = data.get("value", "")
    conn.execute(
        "UPDATE page_content SET value=? WHERE id=?",
        (value, content_id),
    )


def auto_save_article_version(article_id: int, admin: str = "system"):
    """Called before article update to auto-save current version."""
    with get_conn() as conn:
        art = conn.execute(
            "SELECT title, excerpt, content, seo_title, seo_desc, seo_image, "
            "title_en, excerpt_en, content_en, seo_title_en, seo_desc_en, "
            "status, lang, type FROM cms_articles WHERE id=?",
            (article_id,),
        ).fetchone()
        if not art:
            return

        max_ver = conn.execute(
            "SELECT ISNULL(MAX(version_num), 0) AS mx "
            "FROM content_versions WHERE entity_type='cms_article' AND entity_id=?",
            (article_id,),
        ).fetchone()["mx"]

        conn.execute(
            "INSERT INTO content_versions (entity_type, entity_id, version_num, data_json, created_by) "
            "VALUES (?, ?, ?, ?, ?)",
            ("cms_article", article_id, max_ver + 1, json.dumps(dict(art)), admin),
        )
