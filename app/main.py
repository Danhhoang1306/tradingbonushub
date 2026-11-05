import logging
import mimetypes

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import content
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

PUBLIC_BODY_LIMIT = 1024 * 1024
ADMIN_BODY_LIMIT = 64 * 1024 * 1024  # upload nhiều ảnh, mỗi ảnh tối đa 5MB
BUFFERED_BODY_LIMIT = 8 * 1024 * 1024  # không có Content-Length phải đệm vào RAM trước khi xác thực: trần thấp hơn


class SafeStaticFiles(StaticFiles):
    """Đường dẫn hệ điều hành không chấp nhận (tên quá dài, ký tự cấm trên Windows) là 404, không phải 500.
    Thư mục upload chỉ được tạo khi có ảnh đầu tiên: chưa có thư mục cũng là 404."""

    def lookup_path(self, path: str):
        try:
            return super().lookup_path(path)
        except (OSError, ValueError):
            return "", None

    async def check_config(self) -> None:
        return None


class HeadAsGet:
    """Xử lý HEAD như GET rồi bỏ thân (uptime monitor mặc định dùng HEAD). Không đếm lượt xem/click:
    /go/* giữ 405, các route khác kiểm tra `is_head`."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "HEAD" or scope["path"].startswith("/go/"):
            return await self.app(scope, receive, send)
        finished = False

        async def send_no_body(message):
            nonlocal finished
            if message["type"] == "http.response.body":
                if finished:
                    return
                finished = True
                message = {"type": "http.response.body", "body": b"", "more_body": False}
            await send(message)

        await self.app({**scope, "method": "GET", "is_head": True}, receive, send_no_body)


class BodyLimit:
    """Trần kích thước thân request. Không có Content-Length thì đọc tối đa tới trần rồi phát lại."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            return await self.app(scope, receive, send)
        path = scope["path"]
        limit = ADMIN_BODY_LIMIT if path.startswith("/admin") and path != "/admin/login" else PUBLIC_BODY_LIMIT
        too_large = PlainTextResponse("Dữ liệu gửi lên quá lớn.", status_code=413)
        length = dict(scope["headers"]).get(b"content-length")
        if length is not None:
            if length.isdigit() and int(length) > limit:
                return await too_large(scope, receive, send)
            return await self.app(scope, receive, send)
        limit = min(limit, BUFFERED_BODY_LIMIT)
        messages, total = [], 0
        while True:
            message = await receive()
            messages.append(message)
            total += len(message.get("body", b""))
            if total > limit:
                return await too_large(scope, receive, send)
            if message["type"] != "http.request" or not message.get("more_body"):
                break
        pending = iter(messages)

        async def replay():
            return next(pending, None) or await receive()

        await self.app(scope, replay, send)


def _relative_redirect(request: Request, response) -> None:
    """Redirect tự sinh (dấu / cuối URL) mang scheme nội bộ http: đổi thành đường dẫn tương đối để không hạ https."""
    location = response.headers.get("location", "")
    prefix = f"{request.url.scheme}://{request.url.netloc}"
    if 300 <= response.status_code < 400 and location.startswith(prefix + "/"):
        path = location[len(prefix):]
        if not path.startswith("//") and "\\" not in path:
            response.headers["location"] = path


def create_app() -> FastAPI:
    config.validate()
    for warning in config.warnings():
        log.warning(warning)
    from app.routes import admin, public
    from app.routes.admin_base import LoginRequired, login_redirect

    app = FastAPI(title="TradingBonusHub", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(BodyLimit)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        try:
            response = await call_next(request)
        except Exception:
            # Xử lý tại đây (không để handler Exception ở ngoài middleware) để trang 500 cũng có header bảo mật.
            log.exception("Lỗi không xử lý: %s %s", request.method, request.url.path)
            response = _error_page(request, 500)
        _relative_redirect(request, response)
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

    app.add_middleware(HeadAsGet)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404 and not request.url.path.startswith(("/static/", "/media/")):
            return _error_page(request, 404)
        if exc.status_code == 405 and request.method == "GET" and request.url.path.startswith("/admin"):
            return RedirectResponse("/admin", status_code=303)  # URL chỉ có POST (tải lại/đăng nhập lại sau trang lỗi form)
        return PlainTextResponse(str(exc.detail), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def bad_request(request: Request, exc: RequestValidationError):
        # Tham số sai kiểu (/go/broker/abc, ?page=abc): khách thấy trang 404, không thấy JSON.
        if request.method == "GET":
            return _error_page(request, 404)
        return PlainTextResponse("Dữ liệu gửi lên không hợp lệ.", status_code=400)

    @app.exception_handler(OverflowError)
    async def id_too_large(request: Request, exc: OverflowError):
        return _error_page(request, 404)  # id vượt quá số nguyên của SQLite: chắc chắn không tồn tại

    @app.exception_handler(LoginRequired)
    async def need_login(request: Request, exc: LoginRequired):
        return login_redirect(exc)

    @app.exception_handler(Exception)
    async def server_error(request: Request, exc: Exception):
        log.exception("Lỗi không xử lý: %s %s", request.method, request.url.path)
        return _error_page(request, 500)

    app.mount("/static", SafeStaticFiles(directory=str(config.static_dir), check_dir=False), name="static")
    app.mount("/media", SafeStaticFiles(directory=str(config.upload_dir), check_dir=False), name="media")
    app.include_router(public.router)
    app.include_router(admin.router)
    return app


def _error_page(request: Request, status: int):
    from app.routes.public import page_ctx
    from app.templating import render

    title_key = "not_found_title" if status == 404 else "error_title"
    db = SessionLocal()
    try:  # page_ctx tự dùng nội dung mặc định khi DB hỏng, nên trang lỗi vẫn đủ khung site
        return render(request, f"public/{status}.html", page_ctx(request, db, system_title=title_key, desc="", noindex=True),
                      status_code=status)
    except Exception:
        log.exception("Không render được trang lỗi %s", status)
        return HTMLResponse(f"<h1>{content.DEFAULTS['system_text'][title_key]}</h1>", status_code=status)
    finally:
        db.close()


app = create_app()
