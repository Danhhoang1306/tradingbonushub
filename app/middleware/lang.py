"""Language middleware — always default to Vietnamese.

No cookie persistence, no browser language detection. Users may override
per-request via `?lang=` query param (e.g. for sharing a one-off English
link), but the choice is NOT remembered. Every page load defaults to
Vietnamese.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class LangMiddleware(BaseHTTPMiddleware):
    """Set request.state.lang — default 'vi'; allow `?lang=en` per-request only."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path.startswith("/static/"):
            return await call_next(request)

        qs_lang = request.query_params.get("lang")
        if qs_lang in ("vi", "en"):
            request.state.lang = qs_lang
        else:
            request.state.lang = "vi"

        return await call_next(request)
