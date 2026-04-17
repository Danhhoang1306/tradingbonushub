"""FastAPI application factory — registers all routers and middleware."""
import asyncio
import os

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app.utils.templates import make_templates
from slowapi.errors import RateLimitExceeded
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.config import APP_ENV, SESSION_MAX_AGE, configure_logging, limiter
from app.db.connection import init_pool
from app.db.init import init_db
from app.middleware.auth import AuthMiddleware
from app.middleware.csrf import CSRFMiddleware
from app.middleware.db_session import DBSessionMiddleware
from app.middleware.lang import LangMiddleware
from app.middleware.security import SecurityHeadersMiddleware

# ── Routers ───────────────────────────────────────────────────────────────────
from app.api import (
    account_owners,
    admin_system,
    analytics,
    auto_credit,
    bonus,
    campaigns,
    cms_articles,
    cms_banners,
    cms_media,
    cms_navigation,
    content_versions,
    customers,
    emails,
    enrollments,
    faq,
    google_oauth,
    health,
    leads,
    notifications,
    page_content,
    payment,
    permissions,
    portal_settings,
    promotions,
    rebate,
    scheduling,
    segments,
    smtp,
    telegram,
    templates,
    tracking,
    users,
    wallet,
    promo,
    promo_bar,
)
from app.views import admin, cms, content, portal, public

# ── Configure logging first ───────────────────────────────────────────────────
configure_logging()

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="TradingBonusHub Platform", version="2.0.0")

# Trust proxy headers from Cloudflare and local dev
# In production, Cloudflare terminates TLS and forwards X-Forwarded-* headers.
# Restrict to known hosts to prevent header spoofing.
_TRUSTED_HOSTS = [
    "tradingbonushub.com",
    "www.tradingbonushub.com",
    "admin.tradingbonushub.com",
    "127.0.0.1",
    "localhost",
]
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=_TRUSTED_HOSTS)

# CORS — allow only the production domain and localhost (for dev)
_ALLOWED_ORIGINS = [
    "https://tradingbonushub.com",
    "https://www.tradingbonushub.com",
    "https://admin.tradingbonushub.com",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization"],
)

# Static files — served via ASGI middleware to bypass BaseHTTPMiddleware wrapping
# issues (known Starlette 0.36.x bug with mounted sub-apps + BaseHTTPMiddleware)
import pathlib as _pathlib
_STATIC_DIR = str(_pathlib.Path(__file__).resolve().parent.parent / "static")
_static_app = StaticFiles(directory=_STATIC_DIR)


class _StaticFilesMiddleware:
    """Intercept /static/ requests before BaseHTTPMiddleware stack."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/static/"):
            scope["path"] = scope["path"][len("/static"):]  # strip /static prefix
            await _static_app(scope, receive, send)
        else:
            await self.app(scope, receive, send)


app.add_middleware(_StaticFilesMiddleware)

# ── Rate limiter state ────────────────────────────────────────────────────────
app.state.limiter = limiter

_portal_tpl = make_templates("templates/customer")

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    # API routes → JSON; HTML pages → render template with error
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."},
        )
    # Detect which portal template to use based on path
    path = request.url.path
    tpl_map = {
        "/portal/forgot-password": "forgot_password.html",
        "/portal/login": "login.html",
        "/portal/register": "register.html",
    }
    tpl_name = None
    for prefix, name in tpl_map.items():
        if path.startswith(prefix):
            tpl_name = name
            break
    if tpl_name:
        from app.db.repositories.portal_settings import get_portal_settings
        return _portal_tpl.TemplateResponse(
            tpl_name,
            {"request": request, "ps": get_portal_settings(),
             "error": "Too many requests. Please try again later.", "sent": False, "customer_email": ""},
            status_code=429,
        )
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
    )


_exc_logger = structlog.get_logger("unhandled_exception")


_error_tpl = make_templates("templates/shared")


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return _error_tpl.TemplateResponse("error.html", {
        "request": request, "status_code": 404,
        "title": "Page Not Found",
        "message": "The page you are looking for does not exist or has been moved.",
    }, status_code=404)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions — log details, return safe response."""
    _exc_logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_type=type(exc).__name__,
    )
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=500,
            content={"detail": "System error. Please try again later."},
        )
    return _error_tpl.TemplateResponse("error.html", {
        "request": request, "status_code": 500,
        "title": "Something Went Wrong",
        "message": "An unexpected error occurred. Please try again later or contact support.",
    }, status_code=500)


# ── Middleware (added in reverse order — last added = outermost = runs first) ─
# Execution order: SecurityHeaders → DBSession → CSRF → Auth → Lang → handler
app.add_middleware(LangMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(DBSessionMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# ── Include routers ───────────────────────────────────────────────────────────
# API routes
app.include_router(health.router)
app.include_router(tracking.router)
app.include_router(smtp.router)
app.include_router(templates.router)
app.include_router(campaigns.router)
app.include_router(emails.router)
app.include_router(users.router)
app.include_router(customers.router)
app.include_router(leads.router)
app.include_router(promotions.router)
app.include_router(enrollments.router)
app.include_router(account_owners.router)
app.include_router(portal_settings.router)
app.include_router(google_oauth.router)
app.include_router(rebate.router)
app.include_router(bonus.router)
app.include_router(payment.router)
app.include_router(faq.router)
app.include_router(page_content.router)
app.include_router(telegram.router)
# CMS API
app.include_router(cms_articles.router)
app.include_router(cms_media.router)
app.include_router(cms_navigation.router)
app.include_router(cms_banners.router)
app.include_router(promo.router)
app.include_router(promo_bar.router)
app.include_router(wallet.router)
# New admin control APIs
app.include_router(analytics.router)
app.include_router(scheduling.router)
app.include_router(permissions.router)
app.include_router(segments.router)
app.include_router(auto_credit.router)
app.include_router(content_versions.router)
app.include_router(notifications.router)
# System administration
app.include_router(admin_system.router)

# Page routes
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(cms.router)
app.include_router(content.router)
app.include_router(portal.router)


# ── Startup ───────────────────────────────────────────────────────────────────

async def _session_cleanup_loop() -> None:
    """Delete expired sessions from DB every hour to prevent accumulation."""
    import structlog as _sl
    _logger = _sl.get_logger("session_cleanup")
    while True:
        await asyncio.sleep(3600)
        try:
            from app.db.repositories.sessions import cleanup_expired
            cleanup_expired()
        except Exception as exc:
            _logger.warning("session_cleanup.failed", error=str(exc))


async def _daily_cleanup_loop() -> None:
    """Nightly cleanup of accumulated log/queue tables to prevent unbounded growth.

    Runs every 24 hours. Retains:
      - audit_log       : 90 days
      - job_queue       : completed/failed jobs older than 7 days
      - login_attempts  : older than 30 days
    """
    import structlog as _sl
    _logger = _sl.get_logger("cleanup")

    while True:
        await asyncio.sleep(86400)  # 24 hours
        try:
            from app.db.connection import get_conn as _gc
            with _gc() as conn:
                # Audit log: keep 90 days
                r = conn.execute(
                    "DELETE FROM audit_log WHERE created_at < DATEADD(DAY, -90, GETDATE())"
                )
                # Job queue: only delete finished jobs older than 7 days
                conn.execute(
                    "DELETE FROM job_queue "
                    "WHERE status IN ('done','failed') "
                    "  AND finished_at < DATEADD(DAY, -7, GETDATE())"
                )
                # Login attempts: keep 30 days
                conn.execute(
                    "DELETE FROM login_attempts WHERE attempted_at < DATEADD(DAY, -30, GETDATE())"
                )
                # Email tracking: archive opens/clicks older than 2 years
                conn.execute(
                    "DELETE FROM opens WHERE opened_at < DATEADD(YEAR, -2, GETDATE())"
                )
                conn.execute(
                    "DELETE FROM clicks WHERE clicked_at < DATEADD(YEAR, -2, GETDATE())"
                )
                # Withdrawal OTPs: clean up expired/used OTPs older than 7 days
                conn.execute(
                    "DELETE FROM withdrawal_otps WHERE created_at < DATEADD(DAY, -7, GETDATE())"
                )
            _logger.info("daily_cleanup.done")
        except Exception as exc:
            import structlog as _sl2
            _sl2.get_logger("cleanup").warning("daily_cleanup.failed", error=str(exc))


async def _scheduling_loop() -> None:
    """Process scheduled programs, articles, and campaigns every 5 minutes."""
    import structlog as _sl
    _logger = _sl.get_logger("scheduler")
    while True:
        await asyncio.sleep(300)  # every 5 minutes
        try:
            from app.api.scheduling import (
                process_scheduled_programs,
                process_scheduled_articles,
                process_scheduled_campaigns,
            )
            progs = process_scheduled_programs()
            arts = process_scheduled_articles()
            camps = process_scheduled_campaigns()
            if progs["activated"] or progs["deactivated"] or arts or camps:
                _logger.info("scheduler.run",
                             programs_activated=progs["activated"],
                             programs_deactivated=progs["deactivated"],
                             articles_published=arts,
                             campaigns_fired=camps)
        except Exception as exc:
            _logger.warning("scheduler.failed", error=str(exc))


async def _promo_downgrade_loop() -> None:
    """Check and downgrade expired promos every hour."""
    import structlog as _sl
    _logger = _sl.get_logger("promo")
    while True:
        try:
            from app.api.promo import downgrade_expired_promos
            count = downgrade_expired_promos()
            if count:
                _logger.info("promo.downgraded", count=count)
        except Exception as exc:
            _logger.warning("promo.downgrade_failed", error=str(exc))
        await asyncio.sleep(3600)  # every hour


@app.on_event("startup")
async def startup():
    # Only allow OAuth over HTTP in non-production (Cloudflare handles HTTPS in prod)
    if APP_ENV != "production":
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    # Initialize DB schema + migrations
    init_db()

    # Initialize connection pool (after DB exists)
    init_pool()

    # Start campaign job worker
    from app.services.job_worker import start_worker
    asyncio.create_task(start_worker())

    # Periodic session cleanup (every hour)
    asyncio.create_task(_session_cleanup_loop())

    # Nightly cleanup for audit_log / job_queue / login_attempts
    asyncio.create_task(_daily_cleanup_loop())

    # Auto-downgrade expired promos on startup + periodic check
    asyncio.create_task(_promo_downgrade_loop())

    # Scheduling processor — auto-activate/deactivate programs, publish articles, fire campaigns
    asyncio.create_task(_scheduling_loop())
