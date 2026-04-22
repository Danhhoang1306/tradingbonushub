"""Public content routes — blog listing + article detail."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.db.repositories.cms_articles import (
    get_all_categories, get_article_by_slug, list_articles,
)
from app.db.repositories.cms_banners import get_active_banners
from app.db.repositories.cms_navigation import get_nav_items
from app.db.repositories.page_content import get_all_content
from app.db.repositories.portal_settings import get_portal_settings
from app.utils.templates import make_templates

router = APIRouter()
public_tpl = make_templates("templates/public")

LIMIT = 12


def _lang(request: Request) -> str:
    return getattr(getattr(request, "state", None), "lang", None) or "vi"


@router.get("/blog", response_class=HTMLResponse)
async def blog_list(request: Request, page: int = 1, category: str | None = None):
    lang = _lang(request)
    offset = (max(page, 1) - 1) * LIMIT

    # Resolve category_id from slug if provided
    category_id = None
    current_category = None
    if category:
        cats = get_all_categories()
        for c in cats:
            if c["slug"] == category or str(c["id"]) == category:
                category_id = c["id"]
                current_category = c["slug"]
                break

    result = list_articles(
        status="published", type_="post",
        category_id=category_id,
        limit=LIMIT, offset=offset,
    )

    categories = get_all_categories()
    pc = get_all_content(lang)
    ps = get_portal_settings()
    banners = get_active_banners("blog")
    nav_items = get_nav_items("public_header")

    return public_tpl.TemplateResponse(
        "blog.html",
        {
            "request": request,
            "articles": result["items"],
            "total": result["total"],
            "limit": LIMIT,
            "offset": offset,
            "categories": categories,
            "current_category": current_category,
            "pc": pc,
            "ps": ps,
            "banners": banners,
            "nav_items": nav_items,
            "lang": lang,
            "seo_title": None,
            "seo_desc": None,
        },
    )


@router.get("/blog/{slug}", response_class=HTMLResponse)
async def blog_article(slug: str, request: Request):
    lang = _lang(request)
    article = get_article_by_slug(slug, status="published")
    if not article:
        return RedirectResponse(url="/blog", status_code=302)

    # Related articles: same category first, then recent, exclude current
    related_items = []
    if article.get("category_id"):
        res = list_articles(status="published", category_id=article["category_id"], limit=6, offset=0)
        related_items = [a for a in res["items"] if a["id"] != article["id"]][:5]
    # Fill up to 5 with recent articles if not enough
    if len(related_items) < 5:
        res = list_articles(status="published", limit=10, offset=0)
        seen = {a["id"] for a in related_items} | {article["id"]}
        for a in res["items"]:
            if a["id"] not in seen:
                related_items.append(a)
                seen.add(a["id"])
                if len(related_items) >= 5:
                    break

    banners   = get_active_banners("blog")
    nav_items = get_nav_items("public_header")
    ps = get_portal_settings()

    return public_tpl.TemplateResponse(
        "article.html",
        {
            "request": request,
            "article": article,
            "related_articles": related_items,
            "ps": ps,
            "banners": banners,
            "nav_items": nav_items,
            "lang": lang,
        },
    )
