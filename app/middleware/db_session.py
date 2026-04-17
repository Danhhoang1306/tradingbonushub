"""DB-backed server-side session middleware.

Replaces Starlette's cookie-signed SessionMiddleware with server-side storage.
Session data is stored in the `sessions` table; only a signed session_id is
kept in an HttpOnly cookie.

Interface: sets request.scope["session"] so that the standard
`request.session` property (from Starlette) works unchanged.  All existing
code that uses `request.session[...]` continues to work without modification.

Activity timeout: sessions expire after SESSION_IDLE_TIMEOUT seconds of
inactivity (last request timestamp tracked in session data).
"""
import hashlib
import json
import secrets
import time

import structlog
from itsdangerous import BadSignature, TimestampSigner
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import SECRET_KEY, SESSION_MAX_AGE
from app.db.repositories.sessions import (
    create_session, delete_session, get_session, update_session,
)

logger = structlog.get_logger(__name__)

_COOKIE_NAME = "session_id"
_signer = TimestampSigner(SECRET_KEY)
_IDLE_TIMEOUT = 1800  # 30 minutes of inactivity → session expires


def _session_hash(data: dict) -> str:
    return hashlib.md5(
        json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


class DBSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip session handling for static files — avoids BaseHTTPMiddleware
        # response-wrapping issues and improves performance
        if request.url.path.startswith("/static/"):
            return await call_next(request)

        session_id: str | None = None

        # ── Load session from signed cookie ────────────────────────────────────
        raw_cookie = request.cookies.get(_COOKIE_NAME)
        if raw_cookie:
            try:
                session_id = _signer.unsign(raw_cookie, max_age=SESSION_MAX_AGE).decode()
                session_data = get_session(session_id)
                if session_data is None:
                    session_id = None
                    session_data = {}
                elif session_data.get("_last_active"):
                    # Check idle timeout — expire if no activity for _IDLE_TIMEOUT
                    if time.time() - session_data["_last_active"] > _IDLE_TIMEOUT:
                        delete_session(session_id)
                        session_id = None
                        session_data = {}
            except (BadSignature, Exception):
                session_id = None
                session_data = {}
        else:
            session_data = {}

        # Initial hash to detect changes — avoid DB write when unnecessary
        _initial_hash = _session_hash(session_data)

        # Set scope["session"] so request.session works normally
        request.scope["session"] = session_data

        response = await call_next(request)

        # ── Persist session after response ─────────────────────────────────────
        current_data: dict = request.scope.get("session", {})
        # Track last activity for idle timeout
        if current_data and ("user" in current_data or "customer_email" in current_data):
            current_data["_last_active"] = time.time()
        _changed = _session_hash(current_data) != _initial_hash

        try:
            if current_data:
                if session_id:
                    if _changed:
                        update_session(session_id, current_data)
                else:
                    session_id = secrets.token_urlsafe(32)
                    create_session(session_id, current_data)
                signed = _signer.sign(session_id.encode()).decode()
                response.set_cookie(
                    _COOKIE_NAME,
                    signed,
                    max_age=SESSION_MAX_AGE,
                    httponly=True,
                    samesite="strict",  # Prevents CSRF from cross-site requests
                    secure=False,       # Cloudflare handles HTTPS termination externally
                )
            elif session_id and not current_data:
                # Session was cleared (logout)
                delete_session(session_id)
                response.delete_cookie(_COOKIE_NAME)
        except Exception as e:
            logger.error("db_session.save_failed", error=str(e))

        return response
