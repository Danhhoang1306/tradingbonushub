import hashlib
import hmac
import secrets
import threading
import time
from collections import OrderedDict, deque
from datetime import timedelta
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import config
from app.models import AdminSession, AdminUser, utcnow

SESSION_COOKIE = "tbh_session"
LOGIN_CSRF_COOKIE = "tbh_login_csrf"
FLASH_COOKIE = "tbh_flash"
SESSION_DAYS = 7

_hasher = PasswordHasher()  # argon2id


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


_DUMMY_HASH = hash_password(secrets.token_hex(16))


def verify_dummy(password: str) -> None:
    """Tốn thời gian như khi kiểm tra thật, để không lộ email có tồn tại."""
    verify_password(_DUMMY_HASH, password)


def token_hash(token: str) -> str:
    config.require_secret()
    return hmac.new(config.secret_key.encode(), token.encode(), hashlib.sha256).hexdigest()


def create_session(db: Session, user: AdminUser) -> str:
    token = secrets.token_urlsafe(32)
    db.execute(delete(AdminSession).where(AdminSession.expires_at < utcnow()))
    db.add(AdminSession(token_hash=token_hash(token), user_id=user.id,
                        expires_at=utcnow() + timedelta(days=SESSION_DAYS), csrf_token=secrets.token_urlsafe(32)))
    user.last_login_at = utcnow()
    db.commit()
    return token


def load_session(db: Session, request: Request) -> AdminSession | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    sess = db.scalar(select(AdminSession).where(AdminSession.token_hash == token_hash(token)))
    if sess is None or sess.expires_at < utcnow() or not sess.user.is_active:
        return None
    return sess


def revoke_sessions(db: Session, user_id: int, keep_token: str | None = None) -> None:
    """Xóa mọi phiên của user (trừ phiên đang dùng nếu truyền keep_token)."""
    q = delete(AdminSession).where(AdminSession.user_id == user_id)
    if keep_token:
        q = q.where(AdminSession.token_hash != token_hash(keep_token))
    db.execute(q)


def destroy_session(db: Session, request: Request) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db.execute(delete(AdminSession).where(AdminSession.token_hash == token_hash(token)))
        db.commit()


def cookie_kwargs() -> dict:
    return {"httponly": True, "samesite": "lax", "secure": config.is_production, "path": "/"}


def csrf_ok(expected: str | None, given: str | None) -> bool:
    return bool(expected) and bool(given) and hmac.compare_digest(expected, given)


def client_ip(request: Request) -> str:
    host = request.client.host if request.client else ""
    # Site chạy sau Cloudflare Tunnel: mọi request đến từ loopback, IP thật nằm ở CF-Connecting-IP.
    if host in ("127.0.0.1", "::1"):
        cf = request.headers.get("cf-connecting-ip", "").strip()
        if cf:
            return cf
    return host or "unknown"


class RateLimiter:
    """Đếm sự kiện trong cửa sổ trượt, lưu trong bộ nhớ (app chạy một process)."""

    MAX_KEYS = 50_000

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit, self.window = limit, window_seconds
        self._hits: OrderedDict[str, deque] = OrderedDict()
        self._lock = threading.Lock()

    def _count(self, key: str, now: float) -> int:
        q = self._hits.get(key)
        if q is None:
            return 0
        while q and q[0] <= now - self.window:
            q.popleft()
        if not q:
            del self._hits[key]
        return len(q)

    def blocked(self, key: str) -> bool:
        with self._lock:
            return self._count(key, time.monotonic()) >= self.limit

    def hit(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._count(key, now)
            self._hits.setdefault(key, deque()).append(now)
            self._hits.move_to_end(key)
            while len(self._hits) > self.MAX_KEYS:  # LRU: chặn phình bộ nhớ khi bị spam khóa ngẫu nhiên
                self._hits.popitem(last=False)

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


login_limiter = RateLimiter(5, 15 * 60)       # 5 lần sai / 15 phút theo IP+email
public_form_limiter = RateLimiter(5, 10 * 60)  # subscribe/contact: 5 lần / 10 phút theo IP
ad_view_limiter = RateLimiter(30, 60)          # beacon đếm view quảng cáo dọc theo IP


def is_http_url(url: str) -> bool:
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc) and " " not in url.strip()


def is_local_path(url: str) -> bool:
    """Đường dẫn nội bộ an toàn để redirect (chặn //evil.com, /\\evil.com, /<tab>/evil.com)."""
    if any(ord(ch) < 0x21 or ord(ch) == 0x7F for ch in url):  # trình duyệt bỏ tab/xuống dòng trong URL
        return False
    return url.startswith("/") and not url.startswith("//") and "\\" not in url


def is_link(url: str) -> bool:
    """Link do admin nhập cho menu/footer: đường dẫn nội bộ, http(s), mailto hoặc #neo."""
    u = url.strip()
    return is_local_path(u) or is_http_url(u) or u.startswith("mailto:") or (u.startswith("#") and len(u) > 1)


def new_token() -> str:
    return secrets.token_urlsafe(32)
