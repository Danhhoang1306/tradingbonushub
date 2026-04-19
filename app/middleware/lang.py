"""Language detection middleware — auto-detect language from IP geolocation.

Priority order:
  1. Explicit `?lang=` query parameter (user clicked switcher) — sets `lang_explicit` cookie
  2. `lang` cookie IF `lang_explicit=1` cookie present (user previously chose)
  3. Cloudflare CF-IPCountry header (auto-detect by IP) — overrides stale auto-detected cookie
  4. `lang` cookie without explicit flag (last resort if no geo signal)
  5. Accept-Language header (dev / non-CF environments)
  6. Default to English ("en")

Two cookies are used:
  - `lang`         — the active language value ("vi" / "en")
  - `lang_explicit`— "1" when the user explicitly chose via switcher; absent otherwise
This lets region-based detection override an old auto-detected cookie, while
still respecting an explicit user choice across sessions.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Countries that default to Vietnamese
_VN_COUNTRIES = {"VN"}

# Cookie settings
_COOKIE_NAME = "lang"
_EXPLICIT_COOKIE = "lang_explicit"
_COOKIE_MAX_AGE = 365 * 24 * 3600  # 1 year


def _detect_from_accept_language(header: str) -> str | None:
    """Parse Accept-Language header — return 'vi' if Vietnamese preferred, else None."""
    if not header:
        return None
    # Take the primary language tag (before first comma / semicolon)
    primary = header.split(",", 1)[0].split(";", 1)[0].strip().lower()
    if primary.startswith("vi"):
        return "vi"
    return None


class LangMiddleware(BaseHTTPMiddleware):
    """Detect preferred language and inject into request.state.lang."""

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

        # 3. Geo-detect via Cloudflare header — overrides stale auto-detected cookie.
        #    Only upgrade to Vietnamese for VN visitors; don't force English on
        #    other countries (let them fall through to cookie / Accept-Language /
        #    final fallback instead).
        if lang is None:
            country = request.headers.get("cf-ipcountry", "").upper()
            if country in _VN_COUNTRIES:
                lang = "vi"
                if cookie_lang != "vi":
                    set_cookie = True

        # 4. Non-explicit cookie (no CF header available)
        if lang is None and cookie_lang:
            lang = cookie_lang

        # 5. Accept-Language header — helps dev / non-Cloudflare environments
        if lang is None:
            lang = _detect_from_accept_language(
                request.headers.get("accept-language", "")
            )
            if lang:
                set_cookie = True

        # 6. Fallback — default to English for international users
        if lang is None:
            lang = "en"

        # Store on request.state so routes/templates can access it
        request.state.lang = lang

        response = await call_next(request)

        # Persist language cookie if newly determined or refreshed
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
