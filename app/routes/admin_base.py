"""Nền tảng chung cho khu quản trị: xác thực, CSRF, sidebar, đọc form, trường ảnh."""
from dataclasses import dataclass
from urllib.parse import quote

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.datastructures import FormData, UploadFile

from app import uploads
from app.db import get_db
from app.models import AdminSession, AdminUser, Banner, Bonus, Broker, ContactMessage, MediaFile, Post, Subscriber
from app.security import csrf_ok, load_session
from app.templating import render, set_flash


class LoginRequired(Exception):
    def __init__(self, next_path: str) -> None:
        self.next_path = next_path


@dataclass
class Admin:
    request: Request
    db: Session
    session: AdminSession
    form: FormData | None = None

    @property
    def user(self) -> AdminUser:
        return self.session.user

    # --- đọc form ---
    def text(self, name: str, max_len: int = 255) -> str:
        v = self.form.get(name, "") if self.form is not None else ""
        return (v if isinstance(v, str) else "").strip()[:max_len]

    def long_text(self, name: str) -> str:
        return self.text(name, 100_000)

    def flag(self, name: str) -> bool:
        return self.text(name) in ("1", "on", "true", "yes")

    def many(self, name: str, max_len: int = 1000) -> list[str]:
        if self.form is None:
            return []
        return [v.strip()[:max_len] if isinstance(v, str) else "" for v in self.form.getlist(name)]

    def lines(self, name: str) -> list[str]:
        return [x.strip() for x in self.long_text(name).splitlines() if x.strip()]

    def rows(self, prefix: str, fields: tuple[str, ...]) -> list[dict]:
        """Đọc các trường lặp `{prefix}_{field}` (cùng thứ tự) thành list dict, bỏ dòng trống."""
        cols = [self.many(f"{prefix}_{f}") for f in fields]
        n = max((len(c) for c in cols), default=0)
        out = []
        for i in range(n):
            row = {f: (cols[j][i] if i < len(cols[j]) else "") for j, f in enumerate(fields)}
            if any(row.values()):
                out.append(row)
        return out

    def image(self, name: str, errors: dict, current: str = "") -> str:
        """Trường ảnh: file upload `{name}_file` (ưu tiên) hoặc đường dẫn chọn từ thư viện `{name}`."""
        upload = self.form.get(f"{name}_file") if self.form is not None else None
        if isinstance(upload, UploadFile) and uploads.has_file(upload):
            try:
                path = uploads.save_image(self.db, upload).path
                self.db.commit()  # ảnh vào thư viện ngay, kể cả khi form lỗi và phải gửi lại
                return path
            except uploads.UploadError as e:
                errors[name] = str(e)
                return current
        path = self.text(name)
        if not path or path == current or path.startswith("/static/img/") or uploads.is_library_path(self.db, path):
            return path
        errors[name] = "Ảnh phải chọn từ thư viện."
        return current


def _admin_session(request: Request, db: Session) -> AdminSession:
    sess = load_session(db, request)
    if sess is None:
        raise LoginRequired(request.url.path + (f"?{request.url.query}" if request.url.query else ""))
    return sess


def admin_get(request: Request, db: Session = Depends(get_db)) -> Admin:
    return Admin(request, db, _admin_session(request, db))


async def admin_post(request: Request, db: Session = Depends(get_db)) -> Admin:
    sess = _admin_session(request, db)
    form = await request.form(max_part_size=6 * 1024 * 1024)
    if not csrf_ok(sess.csrf_token, form.get("csrf_token")):
        raise HTTPException(403, "CSRF token không hợp lệ")
    return Admin(request, db, sess, form)


def require_admin_role(a: Admin) -> None:
    if a.user.role != "admin":
        raise HTTPException(403, "Chỉ tài khoản quản trị được truy cập mục này")


def login_redirect(exc: LoginRequired) -> RedirectResponse:
    return RedirectResponse(f"/admin/login?next={quote(exc.next_path, safe='/')}", status_code=303)


# --- sidebar & render ---

def nav_groups(db: Session, active: str) -> list[dict]:
    def count(model, *where):
        return db.scalar(select(func.count()).select_from(model).where(*where))

    def item(id_, label, url, n=None):
        return {"id": id_, "label": label, "url": url, "count": n, "active": active == id_}

    return [
        {"label": None, "links": [item("overview", "Tổng quan", "/admin")]},
        {"label": "Dữ liệu", "links": [
            item("bonus", "Bonus", "/admin/bonus", count(Bonus)),
            item("brokers", "Sàn", "/admin/brokers", count(Broker)),
            item("posts", "Bài viết", "/admin/posts", count(Post)),
            item("ads", "Quảng cáo", "/admin/ads", count(Banner))]},
        {"label": "Nội dung", "links": [
            item("home", "Trang chủ", "/admin/home"),
            item("pages", "Trang", "/admin/pages"),
            item("media", "Thư viện ảnh", "/admin/media", count(MediaFile))]},
        {"label": "Khách", "links": [
            item("subscribers", "Người đăng ký", "/admin/subscribers", count(Subscriber, Subscriber.status == "confirmed")),
            item("messages", "Tin nhắn", "/admin/messages", count(ContactMessage, ContactMessage.is_read.is_(False)))]},
        {"label": "Hệ thống", "links": [item("settings", "Cài đặt", "/admin/settings")]},
    ]


def _tab(value: str, tabs) -> str:
    """Tab hợp lệ hoặc tab đầu tiên."""
    return value if value in dict(tabs) else tabs[0][0]


def subtabs(base_url: str, tabs: tuple[tuple[str, str], ...], active: str) -> list[dict]:
    return [{"id": t, "label": label, "url": f"{base_url}?tab={t}", "active": t == active} for t, label in tabs]


def render_admin(a: Admin, template: str, active: str, title: str, status_code: int = 200, **ctx):
    u = a.user
    base = {
        "user": {"id": u.id, "email": u.email, "role": u.role, "is_admin": u.role == "admin"},
        "csrf_token": a.session.csrf_token,
        "nav": nav_groups(a.db, active), "active_nav": active, "title": title,
        "subtabs": [], "drawer": None, "media_library": [],
    }
    return render(a.request, template, base | ctx, status_code=status_code)


def media_library(db: Session) -> list[dict]:
    return [{"id": m.id, "path": m.path, "alt": m.alt, "width": m.width, "height": m.height}
            for m in db.scalars(select(MediaFile).order_by(MediaFile.created_at.desc(), MediaFile.id.desc()))]


def done(url: str, flash: str = "saved") -> RedirectResponse:
    return set_flash(RedirectResponse(url, status_code=303), flash)


def get_or_404(db: Session, model, id_: int):
    obj = db.get(model, id_)
    if obj is None:
        raise HTTPException(404)
    return obj
