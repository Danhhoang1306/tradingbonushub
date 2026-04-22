"""Public site page routes."""
import json
from decimal import Decimal

from datetime import datetime

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.db.repositories.cms_banners import get_active_banners
from app.db.repositories.cms_navigation import get_nav_items
from app.db.repositories.customers import count_customers, create_contact, set_unsubscribed
from app.db.repositories.emails import get_email_detail
from app.db.repositories.faq import get_faq_items
from app.db.repositories.page_content import get_all_content
from app.db.repositories.portal_settings import get_portal_settings, save_portal_settings
from app.db.connection import get_conn
from app.db.repositories.promotions import (
    get_all_brokers, get_broker_by_slug, get_all_programs,
    get_all_program_tiers, get_programs_for_broker,
)
from app.db.repositories.campaigns import get_campaign
from app.db.repositories.cms_articles import list_articles
from app.utils.i18n import t as _t
from app.utils.templates import make_templates

router = APIRouter()
public_tpl = make_templates("templates/public")


def _lang(request: Request) -> str:
    """Get language from middleware (auto-detected) or query string fallback."""
    return getattr(getattr(request, "state", None), "lang", None) or "en"


def _get_trader_count() -> int:
    """Read promo_trader_count from portal_settings; seed from real count if missing."""
    ps = get_portal_settings()
    val = ps.get("promo_trader_count")
    if val is not None:
        return int(val)
    save_portal_settings({"promo_trader_count": "789"})
    return 789


def _mask_email(email: str) -> str:
    parts = email.split("@")
    if len(parts) != 2:
        return email
    name, domain = parts
    masked = name[:2] + "*" * max(1, len(name) - 2)
    return f"{masked}@{domain}"


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    lang = _lang(request)
    pc = get_all_content(lang)
    ps = get_portal_settings()
    brokers = get_all_brokers()
    promotions = get_all_programs(active_only=True)
    all_tiers  = get_all_program_tiers()    # {program_id: [tier_dicts]}

    # Convert Decimal → float so tojson works
    def _fix_decimals(d):
        if isinstance(d, dict):
            return {k: _fix_decimals(v) for k, v in d.items()}
        if isinstance(d, list):
            return [_fix_decimals(v) for v in d]
        if isinstance(d, Decimal):
            return float(d)
        return d

    promotions = [_fix_decimals(p) for p in promotions]
    all_tiers = {k: [_fix_decimals(t) for t in v] for k, v in all_tiers.items()}

    for p in promotions:
        p["details"] = {}
        p["tiers"]   = all_tiers.get(p["id"], [])
        p["rates"]   = []
        # Localise program name for the current viewer
        if lang == "en" and (p.get("name_en") or "").strip():
            p["name"] = p["name_en"]

    backcom_promos = [p for p in promotions if "bonus" not in (p.get("type") or "").lower()]
    tier_promos    = [p for p in promotions if "bonus" in (p.get("type") or "").lower()]

    calc_promos = [
        {
            "id":          p["id"],
            "name":        p["name"],
            "broker_names": p.get("broker_names", ""),
            "type":        p.get("type", ""),
            "details":     p["details"],
            "tiers":       p["tiers"],
            "rates":       [],
        }
        for p in promotions
    ]

    # Top programs — get up to 5 backcom programs by display_order (full object for shared card)
    ranks = ["🥇", "🥈", "🥉", "4", "5"]
    top_brokers = []   # kept for backward compat (JS/template references)
    top_programs = []
    sorted_promos = sorted(promotions, key=lambda x: (x.get("display_order") or 0, x.get("id") or 0))
    for p in sorted_promos:
        if len(top_programs) >= 5:
            break
        if "bonus" in (p.get("type") or "").lower():
            continue
        rank = ranks[len(top_programs)]
        top_brokers.append({
            "rank":     rank,
            "slug":     p.get("broker_slug", ""),
            "name":     p.get("broker_name", ""),
            "best_usd": p.get("rebate_usd_per_lot"),
        })
        top_programs.append({**p, "rank": rank})

    # Enrich top_programs with broker learn_more_url + licenses/leverage fallback
    broker_by_slug = {b["slug"]: b for b in brokers}
    for p in top_programs:
        b = broker_by_slug.get(p.get("broker_slug")) or {}
        p.setdefault("broker_learn_more_url", b.get("learn_more_url") or "")
        if not p.get("licenses"):
            p["licenses"] = b.get("licenses")
        if not p.get("leverage"):
            p["leverage"] = b.get("leverage")

    # Load Gold Bonus tiers (for landing page calculator)
    with get_conn() as _c:
        _gold_prog = _c.execute(
            "SELECT id FROM programs WHERE type='gold_bonus' AND is_active=1"
        ).fetchone()
        if _gold_prog:
            _tier_rows = _c.execute(
                "SELECT target_lot, reward_value FROM program_tiers "
                "WHERE program_id=? AND reward_type='bonus_usd' ORDER BY target_lot",
                (_gold_prog["id"],),
            ).fetchall()
            bonus_tiers = [{"min_lots": float(r["target_lot"]), "bonus_usd": float(r["reward_value"])}
                           for r in _tier_rows]
        else:
            bonus_tiers = []

    # FAQ: group by broker_id (None = generic)
    all_faq = get_faq_items(active_only=True)
    faq_generic = [f for f in all_faq if f["broker_id"] is None]
    faq_by_broker: dict[int, list] = {}
    for f in all_faq:
        if f["broker_id"] is not None:
            faq_by_broker.setdefault(f["broker_id"], []).append(f)

    # Latest blog articles for homepage
    latest_articles = list_articles(status="published", limit=5, offset=0).get("items", [])

    trader_count = _get_trader_count()

    from app.db.repositories.promo_bar import get_active_promo_bar
    active_promo_bar = get_active_promo_bar()

    return public_tpl.TemplateResponse("index.html", {
        "request": request,
        "brokers": brokers,
        "top_brokers":   top_brokers,
        "top_programs":  top_programs,
        "promotions": promotions,
        "backcom_promos": backcom_promos,
        "tier_promos": tier_promos,
        "calc_promos": calc_promos,
        "bonus_tiers": bonus_tiers,
        "faq_generic": faq_generic,
        "faq_by_broker": faq_by_broker,
        "latest_articles": latest_articles,
        "lang": lang,
        "pc": pc,
        "ps": ps,
        "banners": get_active_banners("index"),
        "nav_items": get_nav_items("public_header"),
        "trader_count": trader_count,
        "promo_bar": active_promo_bar,
    })


@router.get("/brokers", response_class=HTMLResponse)
async def public_brokers(request: Request):
    lang = _lang(request)
    ps = get_portal_settings()
    all_brokers = get_all_brokers(active_only=False)
    # Show brokers flagged for public page (need at least a logo_url or logo_color to render)
    brokers = [
        b for b in all_brokers
        if b.get("show_on_brokers_page") and (b.get("logo_url") or b.get("logo_color"))
    ]

    # Left-column content: broker review articles — all published posts whose
    # slug is referenced by a broker via review_article_slug, plus any article
    # in a "broker review" category. Falls back to latest posts if empty.
    review_slugs = {b.get("review_article_slug") for b in all_brokers if b.get("review_article_slug")}
    articles: list[dict] = []
    seen_ids: set[int] = set()

    # 1) Pull review articles linked from the brokers table
    if review_slugs:
        from app.db.repositories.cms_articles import get_article_by_slug
        for slug in review_slugs:
            art = get_article_by_slug(slug, status="published")
            if art and art["id"] not in seen_ids:
                articles.append(art)
                seen_ids.add(art["id"])

    # 2) Pull articles in a "broker review" category (slug: danh-gia-san or broker-reviews)
    from app.db.repositories.cms_articles import get_all_categories, list_articles
    review_cat_id = None
    for c in get_all_categories():
        if c["slug"] in ("danh-gia-san", "broker-reviews", "reviews", "san-uy-tin"):
            review_cat_id = c["id"]
            break
    if review_cat_id:
        for a in list_articles(status="published", category_id=review_cat_id, limit=30).get("items", []):
            if a["id"] not in seen_ids:
                articles.append(a)
                seen_ids.add(a["id"])

    # 3) Fallback — if still empty, show most recent posts so the column is not blank
    if not articles:
        articles = list_articles(status="published", type_="post", limit=10).get("items", [])

    return public_tpl.TemplateResponse("brokers.html", {
        "request": request,
        "ps": ps,
        "lang": lang,
        "brokers": brokers,
        "articles": articles,
        "now": datetime.utcnow(),
    })


@router.get("/promotions", response_class=HTMLResponse)
async def public_promotions_index(request: Request):
    """Show all promotions from all active brokers, with optional dropdown filter."""
    lang = _lang(request)
    brokers = get_all_brokers()
    all_tiers = get_all_program_tiers()

    # Collect programs from all active brokers
    programs = []
    for b in brokers:
        if not b.get("is_active"):
            continue
        broker_programs = get_programs_for_broker(b["id"], active_only=True)
        for p in broker_programs:
            p["tiers"] = all_tiers.get(p["id"], [])
            p.setdefault("broker_slug", b["slug"])
            p.setdefault("broker_name", b["name"])
            p.setdefault("broker_learn_more_url", b.get("learn_more_url") or "")
            # Fall back to broker-level values when program row has none
            if not p.get("licenses"):
                p["licenses"] = b.get("licenses")
            if not p.get("leverage"):
                p["leverage"] = b.get("leverage")
            # Localise program name for the current viewer
            if lang == "en" and (p.get("name_en") or "").strip():
                p["name"] = p["name_en"]
        programs.extend(broker_programs)

    # FAQ for promotions page (generic only)
    all_faq = get_faq_items(active_only=True)
    faq_generic = [f for f in all_faq if f["broker_id"] is None]

    return public_tpl.TemplateResponse("promotions.html", {
        "request": request,
        "brokers": brokers,
        "programs": programs,
        "ps": get_portal_settings(),
        "trader_count": _get_trader_count(),
        "faq_generic": faq_generic,
        "lang": lang,
    })


@router.get("/promotions/{broker_slug}", response_class=HTMLResponse)
async def public_promotions(broker_slug: str, request: Request):
    """Legacy per-broker URL — redirect to main promotions page."""
    return RedirectResponse(url="/promotions", status_code=302)


@router.post("/api/trader-count-bump", response_class=JSONResponse)
async def trader_count_bump():
    """Increment the displayed trader count by 1 and persist to DB."""
    current = _get_trader_count()
    new_val = current + 1
    save_portal_settings({"promo_trader_count": str(new_val)})
    return {"count": new_val}


@router.get("/favicon.ico")
async def favicon():
    return RedirectResponse(url="/static/favicon.svg", status_code=301)


@router.get("/robots.txt")
async def robots_txt():
    from fastapi.responses import FileResponse
    return FileResponse("static/robots.txt", media_type="text/plain")


@router.get("/sitemap.xml")
async def sitemap_xml():
    """Dynamic XML sitemap for SEO — includes static pages, promotions, and blog articles."""
    base = "https://tradingbonushub.com"
    today = datetime.utcnow().strftime("%Y-%m-%d")

    urls = [
        (f"{base}/", today, "daily", "1.0"),
        (f"{base}/promotions", today, "daily", "0.9"),
        (f"{base}/brokers", today, "weekly", "0.8"),
        (f"{base}/about", today, "monthly", "0.6"),
        (f"{base}/blog", today, "daily", "0.8"),
        (f"{base}/privacy", today, "monthly", "0.3"),
        (f"{base}/terms", today, "monthly", "0.3"),
    ]

    # Add blog articles with per-article lastmod
    try:
        articles = list_articles(status="published", limit=500, offset=0).get("items", [])
        for art in articles:
            lastmod = art.get("updated_at") or art.get("published_at") or today
            if hasattr(lastmod, "strftime"):
                lastmod = lastmod.strftime("%Y-%m-%d")
            else:
                lastmod = str(lastmod)[:10]
            urls.append((f"{base}/blog/{art['slug']}", lastmod, "weekly", "0.7"))
    except Exception:
        pass

    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">')
    for loc, lastmod, freq, priority in urls:
        xml_parts.append(
            f"  <url><loc>{loc}</loc>"
            f"<lastmod>{lastmod}</lastmod>"
            f"<changefreq>{freq}</changefreq>"
            f"<priority>{priority}</priority></url>"
        )
    xml_parts.append("</urlset>")
    return Response(content="\n".join(xml_parts), media_type="application/xml")


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    lang = _lang(request)
    return public_tpl.TemplateResponse("privacy.html", {"request": request, "ps": get_portal_settings(), "lang": lang})


@router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    lang = _lang(request)
    return public_tpl.TemplateResponse("terms.html", {"request": request, "ps": get_portal_settings(), "lang": lang})


@router.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    lang = _lang(request)
    brokers = get_all_brokers()
    return public_tpl.TemplateResponse("about.html", {"request": request, "brokers": brokers, "ps": get_portal_settings(), "lang": lang})


@router.post("/contact")
async def contact_submit(
    name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    message: str = Form(""),
):
    create_contact(name, email, phone, message)
    return JSONResponse({"ok": True})


@router.get("/verify", response_class=HTMLResponse)
async def verify_ticket(request: Request, ticket: str = ""):
    lang = _lang(request)
    if not ticket:
        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>{_t('verify_title', lang)} - TradingBonusHub</title></head>
<body style="font-family:Arial,sans-serif;background:#f0f4f8;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;">
<div style="background:#fff;border-radius:8px;padding:40px;max-width:480px;width:100%;box-shadow:0 2px 12px rgba(0,0,0,.08);text-align:center;">
<div style="font-size:32px;margin-bottom:12px;">⚠️</div>
<h2 style="color:#1a3a6b;margin:0 0 8px;">{_t('verify_missing', lang)}</h2>
<p style="color:#666;font-size:14px;">{_t('verify_missing_p', lang)}</p>
</div></body></html>"""
        return HTMLResponse(html, status_code=400)

    email_row, _ = get_email_detail(ticket)
    if not email_row:
        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>{_t('verify_title', lang)} - TradingBonusHub</title></head>
<body style="font-family:Arial,sans-serif;background:#f0f4f8;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;">
<div style="background:#fff;border-radius:8px;padding:40px;max-width:480px;width:100%;box-shadow:0 2px 12px rgba(0,0,0,.08);text-align:center;">
<div style="font-size:32px;margin-bottom:12px;">❌</div>
<h2 style="color:#c0392b;margin:0 0 8px;">{_t('verify_not_found', lang)}</h2>
<p style="color:#666;font-size:14px;">{_t('verify_not_found_p', lang)}</p>
</div></body></html>"""
        return HTMLResponse(html, status_code=404)

    camp = get_campaign(email_row["campaign_id"]) if email_row.get("campaign_id") else None
    subject = camp["subject"] if camp and camp.get("subject") else "—"
    sent_at = email_row.get("created_at", "—")
    recipient = _mask_email(email_row.get("recipient_email", ""))

    html = f"""<!DOCTYPE html>
<html lang="{lang}"><head><meta charset="UTF-8">
<title>{_t('verify_title', lang)} - TradingBonusHub</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="font-family:Arial,sans-serif;background:#f0f4f8;display:flex;justify-content:center;align-items:flex-start;min-height:100vh;margin:0;padding:40px 20px;box-sizing:border-box;">
<div style="max-width:520px;width:100%;">
  <div style="background:linear-gradient(135deg,#0a1628 0%,#1a3a6b 100%);border-radius:8px 8px 0 0;padding:24px 28px;display:flex;justify-content:space-between;align-items:center;">
    <div>
      <span style="font-size:20px;font-weight:bold;color:#fff;">Trading</span><span style="font-size:20px;font-weight:bold;color:#c9a84c;">Bonus</span>
      <div style="font-size:9px;color:#8aaad4;letter-spacing:3px;text-transform:uppercase;margin-top:3px;">Email Verification</div>
    </div>
    <div style="background:rgba(201,168,76,.15);border:1px solid #c9a84c;border-radius:4px;padding:6px 12px;text-align:center;">
      <div style="font-size:10px;color:#c9a84c;letter-spacing:2px;font-weight:bold;">✓ {_t('verify_valid', lang)}</div>
    </div>
  </div>
  <div style="background:#fff;border-left:4px solid #1a3a6b;border-right:1px solid #dde3ee;padding:28px;">
    <p style="margin:0 0 20px;font-size:14px;color:#3a3a3a;">{_t('verify_body', lang)} <strong>TradingBonusHub</strong>.</p>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <tr><td style="padding:8px 0;color:#888;width:120px;">{_t('verify_recipient', lang)}</td><td style="padding:8px 0;color:#1a3a6b;font-weight:bold;">{recipient}</td></tr>
      <tr style="border-top:1px solid #f0f0f0;"><td style="padding:8px 0;color:#888;">{_t('verify_subject', lang)}</td><td style="padding:8px 0;color:#333;">{subject}</td></tr>
      <tr style="border-top:1px solid #f0f0f0;"><td style="padding:8px 0;color:#888;">{_t('verify_sent_at', lang)}</td><td style="padding:8px 0;color:#333;">{sent_at}</td></tr>
    </table>
  </div>
  <div style="background:#f4f7fc;border:1px solid #dde3ee;border-top:none;border-radius:0 0 8px 8px;padding:12px 28px;">
    <span style="font-size:9px;color:#8a9ab5;">🔒 {_t('verify_security', lang)}</span>
  </div>
</div>
</body></html>"""
    return HTMLResponse(html)


@router.get("/portal/unsubscribe/{token}", response_class=HTMLResponse)
async def portal_unsubscribe_link(request: Request, token: str):
    """Opt-out via tracking_id in email — no login required."""
    lang = _lang(request)
    email_row, _ = get_email_detail(token)
    if email_row:
        set_unsubscribed(email_row["recipient_email"], 1)
    return HTMLResponse(
        f"<h2 style='font-family:sans-serif;text-align:center;margin-top:80px'>"
        f"{_t('unsub_success', lang)}</h2>"
    )
