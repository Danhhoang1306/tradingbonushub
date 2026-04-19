"""Authentication middleware for admin and customer portals."""
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Admin subdomain — all requests here go to /admin/*
_ADMIN_HOST = "admin.tradingbonushub.com"

# Paths that editors (non-admin) are allowed to access
_EDITOR_ALLOWED_PATHS = {
    "/admin/login", "/admin/logout",
}
_EDITOR_ALLOWED_PREFIXES = (
    "/admin/cms/",
    "/api/cms/",
    "/static/",
    "/track/",
)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        host = request.headers.get("host", "").split(":")[0].lower()

        # Always allow static files, tracking pixel, and health check
        if (path.startswith("/static/")
                or path.startswith("/track/")
                or path == "/health"
                or path == "/favicon.ico"
                or path == "/robots.txt"):
            return await call_next(request)

        # ── Admin subdomain: admin.tradingbonushub.com ────────────────────────
        if host == _ADMIN_HOST:
            # Redirect root to /admin/
            if path == "/" or path == "":
                return RedirectResponse(url="/admin/", status_code=302)
            # Redirect any non-admin path to /admin/ equivalent
            if not path.startswith("/admin/") and not path.startswith("/api/") and not path.startswith("/static/"):
                return RedirectResponse(url="/admin/", status_code=302)

        # ── Block admin paths on main domain (security) ───────────────────────
        # Only allow admin routes from the admin subdomain or localhost
        if path.startswith("/admin/") and host not in (_ADMIN_HOST, "localhost", "127.0.0.1"):
            return RedirectResponse(url=f"https://{_ADMIN_HOST}/admin/login", status_code=301)

        # Admin routes
        if path.startswith("/admin/"):
            if path in ("/admin/login", "/admin/totp-verify", "/admin/totp-setup"):
                return await call_next(request)
            user = request.session.get("user")
            if not user:
                return RedirectResponse(url="/admin/login", status_code=302)
            # Role check: editors can only access CMS paths
            role = request.session.get("user_role", "admin")
            if role == "editor":
                allowed = (
                    path in _EDITOR_ALLOWED_PATHS
                    or any(path.startswith(p) for p in _EDITOR_ALLOWED_PREFIXES)
                )
                if not allowed:
                    return RedirectResponse(url="/admin/cms/articles", status_code=302)
            return await call_next(request)

        # Customer portal routes
        if path.startswith("/portal/"):
            exempt = {
                "/portal/login", "/portal/register", "/portal/forgot-password",
                "/portal/send-transfer", "/portal/oauth/callback",
                "/portal/verify-email", "/portal/confirm-vantage-email",
                "/portal/verify-broker-email",
            }
            if (path in exempt
                    or path.startswith("/portal/reset-password/")
                    or path.startswith("/portal/verify-email/")):
                return await call_next(request)
            if not request.session.get("customer_email"):
                return RedirectResponse(url="/portal/login", status_code=302)
            # Check if customer account is locked
            if request.session.get("_account_locked"):
                request.session.clear()
                return RedirectResponse(url="/portal/login", status_code=302)
            # Force password change on first login
            if path != "/portal/change-password" and request.session.get("must_change_password"):
                return RedirectResponse(url="/portal/change-password", status_code=302)
            return await call_next(request)

        # API routes — require admin session
        if path.startswith("/api/"):
            # These endpoints are called by the customer portal (not admin)
            _portal_api_exempt = {"/api/enrollments/check-promo"}
            if path in _portal_api_exempt or path.startswith("/api/wallet/me"):
                if not request.session.get("customer_email"):
                    return JSONResponse({"detail": "Unauthorized"}, status_code=401)
                return await call_next(request)
            if not request.session.get("user"):
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
            return await call_next(request)

        # Public routes (/, /contact, etc.)
        return await call_next(request)
