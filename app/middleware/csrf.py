"""CSRF protection middleware.

Generates a per-session CSRF token and validates it on state-changing requests
(POST, PUT, DELETE, PATCH).  The token is available in templates via
``request.state.csrf_token`` and must be submitted as a form field or header.

Exempt paths (APIs using session auth with SameSite=strict cookies, webhooks,
and tracking endpoints) are skipped.
"""
import secrets
from urllib.parse import parse_qs

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_HEADER_NAME = "X-CSRF-Token"
_FORM_FIELD = "csrf_token"
_SESSION_KEY = "_csrf_token"
_TOKEN_LENGTH = 32

# Paths exempt from CSRF checks (API endpoints already protected by
# SameSite=strict cookies + auth middleware, plus external webhooks)
_EXEMPT_PREFIXES = (
    "/api/",
    "/portal/api/",
    "/track/",
    "/click/",
    "/health",
    "/static/",
)


def _is_exempt(path: str) -> bool:
    return any(path.startswith(p) for p in _EXEMPT_PREFIXES)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip CSRF for static files — avoids BaseHTTPMiddleware wrapping
        if request.url.path.startswith("/static/"):
            return await call_next(request)

        # Ensure a CSRF token exists in the session
        session = request.scope.get("session", {})
        token = session.get(_SESSION_KEY)
        if not token:
            token = secrets.token_urlsafe(_TOKEN_LENGTH)
            session[_SESSION_KEY] = token

        # Make token available to templates via request.state
        request.state.csrf_token = token

        # Only validate on state-changing methods
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            if not _is_exempt(request.url.path):
                # Check header first, then form body
                submitted = request.headers.get(_HEADER_NAME)
                if not submitted:
                    content_type = request.headers.get("content-type", "")
                    if "application/x-www-form-urlencoded" in content_type:
                        # Read raw body and parse CSRF token manually.
                        # This avoids consuming the stream via request.form()
                        # which causes BaseHTTPMiddleware to lose the body
                        # for downstream FastAPI Form() handlers.
                        body = await request.body()
                        parsed = parse_qs(body.decode("utf-8", errors="replace"))
                        submitted = parsed.get(_FORM_FIELD, [""])[0]
                    elif "multipart/form-data" in content_type:
                        # For multipart, read raw body first to preserve it,
                        # then parse the CSRF field from the form data.
                        body = await request.body()
                        request._body = body
                        form = await request.form()
                        submitted = form.get(_FORM_FIELD, "")

                if not submitted or submitted != token:
                    return JSONResponse(
                        {"detail": "Invalid CSRF token."},
                        status_code=403,
                    )

        return await call_next(request)
