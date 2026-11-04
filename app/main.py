import logging
import mimetypes

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import config
from app.db import SessionLocal

log = logging.getLogger("app")

# Registry Windows có thể thiếu/sai kiểu ảnh; đặt cố định để /media trả đúng Content-Type (đi kèm nosniff).
for _ext, _type in ((".webp", "image/webp"), (".png", "image/png"), (".jpg", "image/jpeg"), (".svg", "image/svg+xml"),
                    (".css", "text/css"), (".js", "text/javascript")):
    mimetypes.add_type(_type, _ext)

CSP_BASE = ("default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; "
            "object-src 'none'")
CSP_SCRIPTS = "script-src 'self'; connect-src 'self'"
# Chỉ bật khi admin đã cấu hình analytics_head (Google Analytics cần script inline).
CSP_SCRIPTS_ANALYTICS = ("script-src 'self' 'unsafe-inline' https://www.googletagmanager.com https://www.google-analytics.com; "
                         "connect-src 'self' https://www.google-analytics.com https://*.google-analytics.com "
                         "https://*.analytics.google.com https://www.googletagmanager.com")


def create_app() -> FastAPI:
    config.require_secret()
    from app.routes import admin, public
    from app.routes.admin_base import LoginRequired, login_redirect

    docs = None if config.is_production else "/docs"
    app = FastAPI(title="TradingBonusHub", docs_url=docs, redoc_url=None,
                  openapi_url=None if config.is_production else "/openapi.json")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        analytics = getattr(request.state, "analytics", False)
        h = response.headers
        h.setdefault("Content-Security-Policy", f"{CSP_BASE}; {CSP_SCRIPTS_ANALYTICS if analytics else CSP_SCRIPTS}")
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if config.is_production:
            h.setdefault("Strict-Transport-Security", "max-age=31536000")
        if path.startswith("/admin"):
            h["X-Robots-Tag"] = "noindex, nofollow"
            h.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404 and not request.url.path.startswith(("/static/", "/media/")):
            return _error_page(request, 404)
        return PlainTextResponse(str(exc.detail), status_code=exc.status_code)

    @app.exception_handler(LoginRequired)
    async def need_login(request: Request, exc: LoginRequired):
        return login_redirect(exc)

    @app.exception_handler(Exception)
    async def server_error(request: Request, exc: Exception):
        log.exception("Lỗi không xử lý: %s %s", request.method, request.url.path)
        return _error_page(request, 500)

    config.upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(config.static_dir), check_dir=False), name="static")
    app.mount("/media", StaticFiles(directory=str(config.upload_dir)), name="media")
    app.include_router(public.router)
    app.include_router(admin.router)
    return app


def _error_page(request: Request, status: int):
    from app.routes.public import page_ctx
    from app.templating import render

    title = "Không tìm thấy trang" if status == 404 else "Đã có lỗi xảy ra"
    db = SessionLocal()
    try:
        return render(request, f"public/{status}.html", page_ctx(request, db, title=title, desc="", noindex=True),
                      status_code=status)
    except Exception:
        log.exception("Không render được trang lỗi %s", status)
        return HTMLResponse(f"<h1>{title}</h1>", status_code=status)
    finally:
        db.close()


app = create_app()
