"""Language middleware — default to Vietnamese, honor explicit user choice.

Priority order:
  1. Explicit `?lang=` query parameter (user clicked switcher) — sets `lang_explicit` cookie
  2. `lang` cookie IF `lang_explicit=1` cookie present (user previously chose)
  3. Default to Vietnamese ("vi")

Two cookies are used:
  - `lang`         — the active language value ("vi" / "en")
  - `lang_explicit`— "1" when the user explicitly chose via switcher; absent otherwise
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_COOKIE_NAME = "lang"
_EXPLICIT_COOKIE = "lang_explicit"
_COOKIE_MAX_AGE = 365 * 24 * 3600  # 1 year


class LangMiddleware(BaseHTTPMiddleware):
    """Set request.state.lang — default 'vi', respect explicit user choice."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip language detection for static files — avoids BaseHTTPMiddleware
        # response-wrapping issues and improves performance
        if request.url.path.startswith("/static/"):
            return await call_next(request)

        lang: str | None = None
        set_cookie = False
        set_explicit = False

        cookie_lang = request.cookies.get(_COOKIE_NAME)
        if cookie_lang not in ("vi", "en"):
            cookie_lang = None
        explicit_cookie = request.cookies.get(_EXPLICIT_COOKIE) == "1"

        # 1. Explicit query param — user clicked switcher (highest priority)
        qs_lang = request.query_params.get("lang")
        if qs_lang in ("vi", "en"):
            lang = qs_lang
            set_cookie = True
            set_explicit = True

        # 2. User previously made an explicit choice — honor it
        if lang is None and explicit_cookie and cookie_lang:
            lang = cookie_lang

        # 3. Default to Vietnamese
        if lang is None:
            lang = "vi"

        request.state.lang = lang

        response = await call_next(request)

        if set_cookie:
            response.set_cookie(
                _COOKIE_NAME,
                lang,
                max_age=_COOKIE_MAX_AGE,
                httponly=False,  # JS needs to read it for client-side rendering
                samesite="lax",
                path="/",
            )
        if set_explicit:
            response.set_cookie(
                _EXPLICIT_COOKIE,
                "1",
                max_age=_COOKIE_MAX_AGE,
                httponly=False,
                samesite="lax",
                path="/",
            )

        return response
