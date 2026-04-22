"""Security headers middleware — adds OWASP-recommended HTTP headers to all responses.

Uses per-request nonce for CSP script-src to avoid 'unsafe-inline'.
Templates access the nonce via ``request.state.csp_nonce``.
"""
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip security headers for static files — avoids BaseHTTPMiddleware
        # response-wrapping issues and static files don't need CSP headers
        if request.url.path.startswith("/static/"):
            return await call_next(request)

        # Generate per-request nonce for inline scripts
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce

        response = await call_next(request)

        # Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Clickjacking protection — allow same-origin iframes (visual editor)
        response.headers["X-Frame-Options"] = "SAMEORIGIN"

        # XSS filter (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Enforce HTTPS via HSTS (1 year, include subdomains)
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

        # Referrer policy — send origin only to same-origin, nothing to cross-origin
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy — disable unnecessary browser features
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

        # Content Security Policy
        # Note: when a nonce is present, browsers ignore 'unsafe-inline'.
        # Since this project uses inline <style> and <script> extensively
        # (in _nav.html, index.html, admin templates, etc.), we use
        # 'unsafe-inline' WITHOUT nonce to allow them.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.quilljs.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com https://cdn.quilljs.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "img-src 'self' data: blob: https:; "
            "connect-src 'self'; "
            "frame-src 'self'; "
            "frame-ancestors 'self'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        return response
