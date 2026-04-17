"""Admin CMS page routes — articles, media, navigation, banners."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.db.repositories.cms_articles import get_all_categories, get_article_by_id
from app.utils.templates import make_templates

router = APIRouter()
# Use templates/admin as root so cms/ templates can extend base.html
cms_tpl = make_templates("templates/admin")


def _ctx(request: Request, **kwargs):
    return {"request": request, "user": request.session.get("user", ""), **kwargs}


# ── Articles ───────────────────────────────────────────────────────────────────

@router.get("/admin/cms/articles", response_class=HTMLResponse)
async def cms_articles(request: Request):
    return cms_tpl.TemplateResponse(
        "cms/articles.html", _ctx(request, active="cms_articles")
    )


@router.get("/admin/cms/articles/new", response_class=HTMLResponse)
async def cms_article_new(request: Request):
    categories = get_all_categories()
    return cms_tpl.TemplateResponse(
        "cms/article_edit.html",
        _ctx(request, article=None, categories=categories, active="cms_articles"),
    )


@router.get("/admin/cms/articles/{aid}/edit", response_class=HTMLResponse)
async def cms_article_edit(aid: int, request: Request):
    article    = get_article_by_id(aid)
    categories = get_all_categories()
    return cms_tpl.TemplateResponse(
        "cms/article_edit.html",
        _ctx(request, article=article, categories=categories, active="cms_articles"),
    )


# ── Media ──────────────────────────────────────────────────────────────────────

@router.get("/admin/cms/media", response_class=HTMLResponse)
async def cms_media(request: Request):
    return cms_tpl.TemplateResponse(
        "cms/media.html", _ctx(request, active="cms_media")
    )


# ── Navigation ─────────────────────────────────────────────────────────────────

@router.get("/admin/cms/navigation", response_class=HTMLResponse)
async def cms_navigation(request: Request):
    return cms_tpl.TemplateResponse(
        "cms/navigation.html", _ctx(request, active="cms_navigation")
    )


# ── Banners ────────────────────────────────────────────────────────────────────

@router.get("/admin/cms/banners", response_class=HTMLResponse)
async def cms_banners(request: Request):
    return cms_tpl.TemplateResponse(
        "cms/banners.html", _ctx(request, active="cms_banners")
    )
