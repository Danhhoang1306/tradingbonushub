"""Đăng nhập/đăng xuất và Tổng quan. Các nhóm khác nằm ở admin_*.py, gom vào `router` ở cuối file."""
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import content, queries
from app.db import get_db
from app.models import AdminUser, Banner, Bonus, Broker, ContactMessage, Subscriber
from app.routes.admin_base import Admin, admin_get, admin_post, render_admin
from app.security import (LOGIN_CSRF_COOKIE, SESSION_COOKIE, SESSION_DAYS, client_ip, cookie_kwargs, create_session,
                          csrf_ok, destroy_session, is_local_path, load_session, login_ip_limiter, login_limiter, verify_dummy,
                          verify_password)
from app.templating import render, set_flash
from app.utils import today_vn

router = APIRouter(prefix="/admin")


def _safe_next(next_path: str) -> str:
    return next_path if is_local_path(next_path) and next_path.startswith("/admin") else "/admin"


def _login_page(request: Request, next_path: str, email: str = "", error: str | None = None, status_code: int = 200):
    token = secrets.token_urlsafe(32)
    resp = render(request, "admin/login.html",
                  {"csrf_token": token, "next": _safe_next(next_path), "email": email, "error": error,
                   "action": "/admin/login"}, status_code=status_code)
    resp.set_cookie(LOGIN_CSRF_COOKIE, token, max_age=3600, **cookie_kwargs())
    return resp


@router.get("/login")
def login_form(request: Request, next: str = "/admin", db: Session = Depends(get_db)):
    if load_session(db, request):
        return RedirectResponse(_safe_next(next), status_code=303)
    return _login_page(request, next)


@router.post("/login")
def login(request: Request, db: Session = Depends(get_db), email: str = Form(""), password: str = Form(""),
          csrf_token: str = Form(""), next: str = Form("/admin")):
    email = email.strip().lower()[:255]
    if not csrf_ok(request.cookies.get(LOGIN_CSRF_COOKIE), csrf_token):
        return _login_page(request, next, email, "Phiên đăng nhập đã hết hạn, vui lòng thử lại.", 403)
    ip = client_ip(request)
    key = f"{ip}|{email}"
    if login_limiter.blocked(key) or login_ip_limiter.blocked(ip):
        return _login_page(request, next, email, "Đăng nhập sai quá nhiều lần. Vui lòng thử lại sau 15 phút.", 429)
    user = db.scalar(select(AdminUser).where(AdminUser.email == email))
    if user is None:
        verify_dummy(password)
    if user is None or not verify_password(user.password_hash, password) or not user.is_active:
        login_limiter.hit(key)
        login_ip_limiter.hit(ip)
        return _login_page(request, next, email, "Email hoặc mật khẩu không đúng.", 401)
    login_limiter.reset(key)
    token = create_session(db, user)
    resp = RedirectResponse(_safe_next(next), status_code=303)
    resp.set_cookie(SESSION_COOKIE, token, max_age=SESSION_DAYS * 86400, **cookie_kwargs())
    resp.delete_cookie(LOGIN_CSRF_COOKIE, path="/")
    return resp


@router.post("/logout")
def logout(a: Admin = Depends(admin_post)):
    destroy_session(a.db, a.request)
    resp = set_flash(RedirectResponse("/admin/login", status_code=303), "logged_out")
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


@router.get("")
def overview(a: Admin = Depends(admin_get)):
    db = a.db
    today = today_vn()
    labels = content.type_labels(content.get_all(db))
    total_bonus = db.scalar(select(func.count()).select_from(Bonus))
    visible = sum(queries.visible_bonus_counts(db).values())
    banners = db.scalars(select(Banner)).all()
    running = sum(1 for b in banners if queries.banner_state(b, today) == "running")

    def clicks(kind):
        return sum(d["clicks"] for d in queries.daily_clicks(db, 30, kind=kind))

    confirmed = db.scalar(select(func.count()).select_from(Subscriber).where(Subscriber.status == "confirmed"))
    expiring = db.scalars(
        select(Bonus).join(Bonus.broker).where(queries.bonus_visible_clause(today), Bonus.expiry_date.is_not(None),
                                               Bonus.expiry_date <= today + timedelta(days=queries.EXPIRING_DAYS))
        .order_by(Bonus.expiry_date)).all()
    top = db.scalars(select(Broker).where(Broker.clicks > 0).order_by(Broker.clicks.desc()).limit(5)).all()
    days = queries.daily_clicks(db, 30)
    unread = db.scalar(select(func.count()).select_from(ContactMessage).where(ContactMessage.is_read.is_(False)))
    return render_admin(
        a, "admin/overview.html", "overview", "Tổng quan",
        stats=[
            {"id": "bonus", "label": "Bonus đang hiển thị", "value": f"{visible}/{total_bonus}"},
            {"id": "banners", "label": "Banner đang chạy", "value": str(running)},
            {"id": "ad_clicks", "label": "Click quảng cáo (30 ngày)", "value": str(clicks("ad"))},
            {"id": "broker_clicks", "label": "Click affiliate (30 ngày)", "value": str(clicks("broker"))},
            {"id": "subscribers", "label": "Người đăng ký", "value": str(confirmed)},
        ],
        expiring=[queries.bonus_view(b, labels) for b in expiring],
        click_days=days,
        click_total=sum(d["clicks"] for d in days),
        top_brokers=[{"id": k.id, "name": k.name, "clicks": k.clicks} for k in top],
        banners=[{"id": b.id, "name": b.name, "placement": b.placement, "state": queries.banner_state(b, today),
                  "views": b.views, "clicks": b.clicks, "edit_url": f"/admin/ads/{b.id}/edit"}
                 for b in sorted(banners, key=lambda b: (-b.clicks, -b.views, b.id))[:5]],
        unread_messages=unread,
    )


# Gom các nhóm quản trị khác (import ở cuối để tránh vòng lặp import).
from app.routes import admin_content, admin_data, admin_people  # noqa: E402

for _r in (admin_data.router, admin_content.router, admin_people.router):
    router.include_router(_r)
