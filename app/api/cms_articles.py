"""CMS Articles API — admin + editor."""
from datetime import datetime, timezone

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Request

from app.db.repositories.cms_articles import (
    create_article, delete_article, get_all_categories, get_article_by_id,
    list_articles, publish_article, unique_slug, unpublish_article,
    update_article, create_category, update_category, delete_category, slugify,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/cms")


def _auto_seo(d: dict, title: str, excerpt: str) -> None:
    """Auto-fill empty SEO fields from title/excerpt (both VI and EN)."""
    import re
    if not (d.get("seo_title") or "").strip():
        d["seo_title"] = title
    if not (d.get("seo_desc") or "").strip():
        plain = re.sub(r"<[^>]+>", "", excerpt or "").strip()
        d["seo_desc"] = plain[:160] if plain else title

    title_en = (d.get("title_en") or "").strip()
    excerpt_en = (d.get("excerpt_en") or "").strip()
    if title_en and not (d.get("seo_title_en") or "").strip():
        d["seo_title_en"] = title_en
    if title_en and not (d.get("seo_desc_en") or "").strip():
        plain_en = re.sub(r"<[^>]+>", "", excerpt_en or "").strip()
        d["seo_desc_en"] = plain_en[:160] if plain_en else title_en


def _int_or_none(val) -> int | None:
    """Safely convert a value to int, returning None for empty/invalid."""
    if val is None or val == "" or val == "null" or val == "None":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


# ── Categories ─────────────────────────────────────────────────────────────────

@router.get("/categories")
async def api_list_categories():
    return get_all_categories()


@router.post("/categories")
async def api_create_category(request: Request):
    d = await request.json()
    name = (d.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name is required")
    slug = (d.get("slug") or slugify(name)).strip() or slugify(name)
    parent_id = d.get("parent_id") or None
    display_order = int(d.get("display_order") or 0)
    cid = create_category(name, slug, parent_id, display_order)
    return {"ok": True, "id": cid}


@router.put("/categories/{cid}")
async def api_update_category(cid: int, request: Request):
    d = await request.json()
    name = (d.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name is required")
    slug = (d.get("slug") or slugify(name)).strip() or slugify(name)
    parent_id = d.get("parent_id") or None
    display_order = int(d.get("display_order") or 0)
    update_category(cid, name, slug, parent_id, display_order)
    return {"ok": True}


@router.delete("/categories/{cid}")
async def api_delete_category(cid: int):
    delete_category(cid)
    return {"ok": True}


# ── Articles ───────────────────────────────────────────────────────────────────

@router.get("/articles")
async def api_list_articles(
    status: str | None = None,
    type: str | None = None,
    lang: str | None = None,
    category_id: int | None = None,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
):
    return list_articles(status, type, lang, category_id, search, limit, offset)


@router.get("/articles/{aid}")
async def api_get_article(aid: int):
    art = get_article_by_id(aid)
    if not art:
        raise HTTPException(404, "Article not found")
    return art


@router.post("/articles")
async def api_create_article(request: Request):
    d = await request.json()
    author = request.session.get("user", "")
    title = (d.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title is required")

    slug = unique_slug(d.get("slug") or title)
    type_ = d.get("type") or "post"
    status = d.get("status") or "draft"
    lang = d.get("lang") or "en"

    _auto_seo(d, title, (d.get("excerpt") or "").strip())

    aid = create_article(
        slug=slug, type_=type_, status=status, lang=lang,
        title=title,
        excerpt=(d.get("excerpt") or "").strip(),
        content=(d.get("content") or ""),
        cover_image_id=_int_or_none(d.get("cover_image_id")),
        category_id=_int_or_none(d.get("category_id")),
        author=author,
        seo_title=(d.get("seo_title") or "").strip(),
        seo_desc=(d.get("seo_desc") or "").strip(),
        seo_image=(d.get("seo_image") or "").strip(),
        title_en=(d.get("title_en") or "").strip() or None,
        excerpt_en=(d.get("excerpt_en") or "").strip() or None,
        content_en=(d.get("content_en") or "") or None,
        seo_title_en=(d.get("seo_title_en") or "").strip() or None,
        seo_desc_en=(d.get("seo_desc_en") or "").strip() or None,
        cover_image_id_en=_int_or_none(d.get("cover_image_id_en")),
    )

    if status == "published":
        publish_article(aid)

    # Handle scheduling
    scheduled_at = d.get("scheduled_at")
    if scheduled_at and status == "draft":
        from app.db.connection import get_conn as _gc
        with _gc() as _c:
            _c.execute("UPDATE cms_articles SET scheduled_at=?, status='scheduled' WHERE id=?",
                       (scheduled_at, aid))

    logger.info("cms.article_created", id=aid, title=title, author=author)
    return {"ok": True, "id": aid, "slug": slug}


@router.put("/articles/{aid}")
async def api_update_article(aid: int, request: Request):
    art = get_article_by_id(aid)
    if not art:
        raise HTTPException(404, "Article not found")

    d = await request.json()
    title = (d.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title is required")

    new_slug_base = d.get("slug") or title
    slug = unique_slug(new_slug_base, exclude_id=aid)
    status = d.get("status") or art["status"]

    _auto_seo(d, title, (d.get("excerpt") or "").strip())

    # Set published_at when first publishing
    published_at = None
    if status == "published":
        published_at = art.get("published_at") or datetime.now(timezone.utc).isoformat()

    # Auto-save version before update
    try:
        from app.api.content_versions import auto_save_article_version
        auto_save_article_version(aid, request.session.get("user", ""))
    except Exception:
        pass  # Don't fail the update if version save fails

    update_article(
        aid=aid, slug=slug, type_=d.get("type") or art["type"],
        status=status, lang=d.get("lang") or art["lang"],
        title=title,
        excerpt=(d.get("excerpt") or "").strip(),
        content=(d.get("content") or ""),
        cover_image_id=_int_or_none(d.get("cover_image_id")),
        category_id=_int_or_none(d.get("category_id")),
        author=art["author"],
        seo_title=(d.get("seo_title") or "").strip(),
        seo_desc=(d.get("seo_desc") or "").strip(),
        seo_image=(d.get("seo_image") or "").strip(),
        published_at_sql=published_at,
        title_en=(d.get("title_en") or "").strip() or None,
        excerpt_en=(d.get("excerpt_en") or "").strip() or None,
        content_en=(d.get("content_en") or "") or None,
        seo_title_en=(d.get("seo_title_en") or "").strip() or None,
        seo_desc_en=(d.get("seo_desc_en") or "").strip() or None,
        cover_image_id_en=_int_or_none(d.get("cover_image_id_en")),
    )

    logger.info("cms.article_updated", id=aid, title=title)
    return {"ok": True, "slug": slug}


# ── AI Translation ───────────────────────────────────────────────────────────

@router.get("/translate/status")
async def api_translate_status():
    """Check if Ollama is online and model is available."""
    from app.services.ollama_translate import check_ollama
    return await check_ollama()


@router.post("/translate")
async def api_translate_article(request: Request):
    """Translate article fields VI<>EN using local Ollama AI."""
    from app.services.ollama_translate import check_ollama, translate_article, OLLAMA_MODEL

    d = await request.json()
    title = (d.get("title") or "").strip()
    excerpt = (d.get("excerpt") or "").strip()
    content = (d.get("content") or "")
    seo_title = (d.get("seo_title") or "").strip()
    seo_desc = (d.get("seo_desc") or "").strip()
    source_lang = d.get("source_lang", "vi")
    target_lang = d.get("target_lang", "en")

    if not title and not excerpt and not content:
        raise HTTPException(400, "Nothing to translate")
    if source_lang not in ("vi", "en") or target_lang not in ("vi", "en"):
        raise HTTPException(400, "Supported languages: vi, en")

    status = await check_ollama()
    if not status["online"]:
        raise HTTPException(503, "Ollama is not running. Start it on the host: ollama serve")
    if not status["has_model"]:
        raise HTTPException(503, f"Model {OLLAMA_MODEL} not found. Run: ollama pull {OLLAMA_MODEL}")

    try:
        result = await translate_article(
            title, excerpt, content, seo_title, seo_desc,
            source_lang, target_lang,
        )
        return {"ok": True, **result}
    except httpx.TimeoutException:
        raise HTTPException(504, "Translation timed out. Article may be too long or model too slow.")
    except Exception as e:
        logger.error("cms.translate_failed", error=str(e))
        raise HTTPException(500, f"Translation failed: {e}")


@router.post("/articles/{aid}/publish")
async def api_publish_article(aid: int):
    art = get_article_by_id(aid)
    if not art:
        raise HTTPException(404, "Article not found")
    publish_article(aid)
    logger.info("cms.article_published", id=aid)
    return {"ok": True}


@router.post("/articles/{aid}/unpublish")
async def api_unpublish_article(aid: int):
    art = get_article_by_id(aid)
    if not art:
        raise HTTPException(404, "Article not found")
    unpublish_article(aid)
    logger.info("cms.article_unpublished", id=aid)
    return {"ok": True}


@router.delete("/articles/{aid}")
async def api_delete_article(aid: int):
    art = get_article_by_id(aid)
    if not art:
        raise HTTPException(404, "Article not found")
    delete_article(aid)
    logger.info("cms.article_deleted", id=aid)
    return {"ok": True}


@router.get("/slug-preview")
async def api_slug_preview(text: str = ""):
    from app.db.repositories.cms_articles import slugify
    return {"slug": slugify(text)}
