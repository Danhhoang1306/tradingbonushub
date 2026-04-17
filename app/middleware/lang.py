"""Language detection middleware — auto-detect language from IP geolocation.

Priority order:
  1. Explicit `?lang=` query parameter (user clicked switcher)
  2. `lang` cookie (returning visitor who already chose)
  3. Cloudflare CF-IPCountry header (auto-detect by IP)
  4. Default to English ("en")

When auto-detected or explicitly chosen, a `lang` cookie is set so the
detection only runs once per browser.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Countries that default to Vietnamese
_VN_COUNTRIES = {"VN"}

# Cookie settings
_COOKIE_NAME = "lang"
_COOKIE_MAX_AGE = 365 * 24 * 3600  # 1 year


class LangMiddleware(BaseHTTPMiddleware):
    """Detect preferred language and inject into request.state.lang."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip language detection for static files — avoids BaseHTTPMiddleware
        # response-wrapping issues and improves performance
        if request.url.path.startswith("/static/"):
            return await call_next(request)

        lang = None
        set_cookie = False

        # 1. Explicit query parameter — highest priority
        qs_lang = request.query_params.get("lang")
        if qs_lang in ("vi", "en"):
            lang = qs_lang
            set_cookie = True  # remember explicit choice

        # 2. Cookie — returning visitor
        if lang is None:
            cookie_lang = request.cookies.get(_COOKIE_NAME)
            if cookie_lang in ("vi", "en"):
                lang = cookie_lang

        # 3. Cloudflare CF-IPCountry header — geo-detect
        if lang is None:
            country = request.headers.get("cf-ipcountry", "").upper()
            if country and country != "XX":  # XX = unknown
                lang = "vi" if country in _VN_COUNTRIES else "en"
                set_cookie = True  # persist auto-detected result

        # 4. Fallback — default to English for international users
        if lang is None:
            lang = "en"

        # Store on request.state so routes/templates can access it
        request.state.lang = lang

        response = await call_next(request)

        # Set cookie if language was just determined
        if set_cookie:
            response.set_cookie(
                _COOKIE_NAME,
                lang,
                max_age=_COOKIE_MAX_AGE,
                httponly=False,  # JS needs to read it for client-side rendering
                samesite="lax",
                path="/",
            )

        return response
