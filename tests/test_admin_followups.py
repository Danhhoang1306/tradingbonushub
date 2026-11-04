"""Hồi quy cho các mục Admin FE ghi trong docs/ISSUES.md."""
import io
import subprocess
import sys

import pytest
from PIL import Image

from conftest import ROOT, errors_of, flash_code, titles
from app import mailer
from app.models import AdminUser, Campaign, ContactMessage, MediaFile, Subscriber
from app.routes import admin_base


def png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, "PNG")
    return buf.getvalue()


# Tổng quan: thẻ banner thật + logo sidebar theo Cài đặt

def test_overview_banner_stats_from_db(admin, db):
    from app.models import Banner
    db.add_all([Banner(name="Ít click", placement="after-bonus", target_url="https://example.com/1", views=10, clicks=1),
                Banner(name="Nhiều click", placement="before-blog", target_url="https://example.com/2", views=50, clicks=9,
                       is_active=False)])
    db.commit()
    rows = admin.get("/admin").context["banners"]
    assert titles(rows, "name") == ["Nhiều click", "Ít click"]
    assert rows[0] == {"id": rows[0]["id"], "name": "Nhiều click", "placement": "before-blog", "state": "paused",
                       "views": 50, "clicks": 9, "edit_url": f"/admin/ads/{rows[0]['id']}/edit"}


def test_overview_banners_empty(admin):
    assert admin.get("/admin").context["banners"] == []


def test_admin_pages_have_branding_from_settings(admin, db):
    assert admin.get("/admin").context["branding"]["logo_path"] == "/static/img/logo.png"
    db.add(MediaFile(path="/media/logo-moi.png"))
    db.commit()
    admin.post("/admin/settings/general", {"site_name": "S", "logo_path": "/media/logo-moi.png"})
    for url in ("/admin", "/admin/bonus", "/admin/media"):
        assert admin.get(url).context["branding"]["logo_path"] == "/media/logo-moi.png"


# 1. Trang chủ: lỗi 400 giữ đủ các dòng lặp

def test_home_error_keeps_all_repeated_rows(admin, db):
    r = admin.post("/admin/home/menu", {
        "menu_label": ["Một", "Hai", "Ba"], "menu_url": ["/mot", "javascript:x", "/ba"],
        "footer_col_title": ["Cột 1", "Cột 2"], "footer_col_links": ["A | /a", "B | /b"], "risk_note": "Rủi ro mới"})
    assert r.status_code == 400
    data = r.context["form"]["data"]
    assert data["menu_label"] == ["Một", "Hai", "Ba"] and data["risk_note"] == "Rủi ro mới"
    assert titles(data["menu"], "label") == ["Một", "Hai", "Ba"]
    assert [c["title"] for c in data["columns"]] == ["Cột 1", "Cột 2"]
    assert data["columns"][1]["links"] == [{"label": "B", "url": "/b"}]
    assert "csrf_token" not in data


def test_home_single_repeated_row_is_still_a_list(admin):
    r = admin.post("/admin/home/menu", {"menu_label": ["Một"], "menu_url": ["javascript:x"]})
    assert r.context["form"]["data"]["menu_label"] == ["Một"]


def test_home_error_keeps_uploaded_image(admin, db):
    r = admin.post("/admin/home/menu", {"menu_label": "x", "menu_url": "javascript:x"})
    assert r.status_code == 400
    r = admin.post("/admin/home/about", {"title": "Về", "image_0": "https://evil.example/x.png", "point_title": ["P"]},
                   files=[("image_1_file", ("a.png", png(), "image/png"))])
    assert r.status_code == 400
    m = db.query(MediaFile).one()
    data = r.context["form"]["data"]
    assert data["image_1"] == m.path and data["points"] == [{"title": "P", "text": ""}]
    assert "image_0" in errors_of(r)


# 2. Trang và Cài đặt: lỗi 400 trả lại form.data

def test_pages_error_returns_form_data(admin):
    r = admin.post("/admin/pages/gioithieu", {"title": "", "desc": "Mô tả mới", "about_block_title": ["K1", "K2"],
                                              "about_block_text": ["a", "b"]})
    assert r.status_code == 400
    data = r.context["form"]["data"]
    assert data["desc"] == "Mô tả mới" and data["about_block_title"] == ["K1", "K2"]
    assert titles(data["about_blocks"]["about"]["blocks"]) == ["K1", "K2"]


def test_settings_error_returns_form_data(admin):
    r = admin.post("/admin/settings/general", {"site_name": "Tên mới", "contact_email": "sai"})
    assert r.status_code == 400
    assert r.context["form"]["data"]["site_name"] == "Tên mới"
    assert r.context["form"]["data"]["contact_email"] == "sai"
    r = admin.post("/admin/settings/social", {"social_label": ["FB", "X"], "social_url": ["https://a.example", "sai"]})
    assert r.status_code == 400 and titles(r.context["form"]["data"]["social"], "label") == ["FB", "X"]
    assert admin.get("/admin/settings?tab=general").context["form"]["data"] == {}


# 3. Cài đặt › Tài khoản: tách lỗi form sửa và form thêm

def test_user_edit_and_create_errors_are_separate(admin, db):
    other = AdminUser(email="khac@example.test", password_hash="x", role="editor")
    db.add(other)
    db.commit()
    r = admin.post(f"/admin/settings/users/{other.id}/edit", {"role": "x", "password": "ngan"})
    form = r.context["form"]
    assert r.status_code == 400 and form["errors_user_id"] == other.id
    assert set(form["errors"]) == {"edit_role", "edit_password"}
    r = admin.post("/admin/settings/users/new", {"email": "sai", "password": "ngan", "role": "x"})
    form = r.context["form"]
    assert r.status_code == 400 and form["errors_user_id"] is None
    assert set(form["errors"]) == {"email", "password", "role"}
    assert form["data"]["email"] == "sai" and "password" not in form["data"]


# 4. Tin nhắn: toggle và xóa theo `back`

def _message(db) -> ContactMessage:
    m = ContactMessage(email="k@example.test", body="x")
    db.add(m)
    db.commit()
    return m


def test_message_actions_keep_tab(admin, db):
    a, b = _message(db), _message(db)
    assert admin.get("/admin/messages?tab=unread").context["messages"][0]["open_url"] == f"/admin/messages/{b.id}?tab=unread"
    r = admin.post(f"/admin/messages/{a.id}/toggle", {"back": "/admin/messages?tab=unread"})
    assert r.headers["location"] == "/admin/messages?tab=unread"
    r = admin.post(f"/admin/messages/{a.id}/delete", {"back": "/admin/messages?tab=unread"})
    assert r.headers["location"] == "/admin/messages?tab=unread"
    r = admin.post(f"/admin/messages/{b.id}/delete", {"back": f"/admin/messages/{b.id}?tab=unread"})
    assert r.headers["location"] == "/admin/messages?tab=unread"  # không quay về tin vừa xóa


@pytest.mark.parametrize("back", ["https://evil.example/admin/messages", "//evil.example", "/\t/evil.example",
                                  "/admin/bonus", "/admin/messages-evil"])
def test_message_back_rejects_foreign_paths(admin, db, back):
    m = _message(db)
    assert admin.post(f"/admin/messages/{m.id}/toggle", {"back": back}).headers["location"] == "/admin/messages"


# 5 + 7. media_library

@pytest.mark.parametrize("url,expected", [
    ("/admin/settings?tab=seo", True), ("/admin/settings?tab=general", True), ("/admin/settings?tab=social", False),
    ("/admin/settings?tab=tracking", False), ("/admin/settings?tab=users", False),
    ("/admin/home?tab=hero", True), ("/admin/home?tab=why", True), ("/admin/home?tab=sections", False),
    ("/admin/home?tab=menu", False), ("/admin/pages?tab=gioithieu", True), ("/admin/pages?tab=bonus", False),
    ("/admin/pages?tab=terms", False),
])
def test_media_library_only_on_tabs_with_images(admin, db, url, expected):
    db.add(MediaFile(path="/media/a.png"))
    db.commit()
    assert bool(admin.get(url).context["media_library"]) is expected


def test_media_library_is_limited(admin, db, monkeypatch):
    monkeypatch.setattr(admin_base, "MEDIA_PICKER_LIMIT", 2)
    db.add_all([MediaFile(path=f"/media/{i}.png") for i in range(3)])
    db.commit()
    assert titles(admin.get("/admin/settings?tab=seo").context["media_library"], "path") == ["/media/2.png", "/media/1.png"]


# 6. Route JSON đếm người nhận

def test_audience_count_json(admin, db):
    db.add_all([Subscriber(email="a@example.test", interests=["deposit"], status="confirmed", token="1"),
                Subscriber(email="b@example.test", interests=["crypto"], status="confirmed", token="2"),
                Subscriber(email="c@example.test", interests=["deposit"], status="pending", token="3")])
    db.commit()
    assert admin.get("/admin/subscribers/audience-count").json() == {"count": 2}
    assert admin.get("/admin/subscribers/audience-count?aud=deposit").json() == {"count": 1}
    assert admin.get("/admin/subscribers/audience-count?aud=deposit&aud=crypto&aud=xx").json() == {"count": 2}


def test_audience_count_requires_login(client):
    r = client.get("/admin/subscribers/audience-count", follow_redirects=False)
    assert r.status_code == 401


# 8. Bản nháp và gửi thử

def test_draft_reopen_update_and_send(admin, db):
    db.add(Subscriber(email="a@example.test", status="confirmed", token="t"))
    db.commit()
    r = admin.post("/admin/subscribers/mail", {"subject": "Nháp 1", "body": "B", "audience": ["deposit"], "action": "draft"})
    c = db.query(Campaign).one()
    assert r.headers["location"] == f"/admin/subscribers?tab=mail&draft={c.id}"
    page = admin.get(r.headers["location"])
    mf = page.context["mail_form"]
    assert (mf["subject"], mf["body"], mf["audience"], mf["draft_id"]) == ("Nháp 1", "B", ["deposit"], c.id)
    assert page.context["current_tab"] == "mail"
    assert page.context["campaigns"][0]["edit_url"] == f"/admin/subscribers?tab=mail&draft={c.id}"

    admin.post("/admin/subscribers/mail", {"subject": "Nháp 2", "body": "B2", "draft_id": c.id, "action": "draft"})
    db.expire_all()
    assert db.query(Campaign).count() == 1 and db.get(Campaign, c.id).subject == "Nháp 2"

    admin.post("/admin/subscribers/mail", {"subject": "Nháp 2", "body": "B2", "draft_id": c.id, "action": "send"})
    db.expire_all()
    assert db.get(Campaign, c.id).status == "sent" and len(mailer.outbox) == 1
    assert admin.get("/admin/subscribers?tab=mail").context["campaigns"][0]["edit_url"] is None
    # đã gửi thì không mở lại, không gửi lại được
    assert admin.get(f"/admin/subscribers?tab=mail&draft={c.id}").status_code == 404
    r = admin.post("/admin/subscribers/mail", {"subject": "S", "body": "B", "draft_id": c.id, "action": "send"})
    assert r.status_code == 404 and len(mailer.outbox) == 1


def test_mail_test_goes_only_to_current_admin(admin, db):
    db.add(Subscriber(email="a@example.test", status="confirmed", token="t"))
    db.commit()
    r = admin.post("/admin/subscribers/mail/test", {"subject": "Tiêu\nđề", "body": "Nội dung", "audience": ["crypto"]})
    assert r.status_code == 200 and flash_code(r) == "test_sent"
    assert [m["To"] for m in mailer.outbox] == ["admin@example.test"]
    assert mailer.outbox[0]["Subject"] == "[Gửi thử] Tiêu đề"
    assert r.context["mail_form"]["body"] == "Nội dung" and r.context["mail_form"]["audience"] == ["crypto"]
    assert db.query(Campaign).count() == 0
    assert admin.post("/admin/subscribers/mail/test", {"subject": "", "body": ""}).status_code == 400
    assert len(mailer.outbox) == 1


def test_mail_test_reports_send_failure(admin, monkeypatch):
    from app.routes import admin_people
    monkeypatch.setattr(admin_people, "send_email", lambda *a, **k: False)
    r = admin.post("/admin/subscribers/mail/test", {"subject": "S", "body": "B"})
    assert r.status_code == 502 and flash_code(r) == "test_failed"


def test_mail_test_requires_csrf(admin):
    assert admin.c.post("/admin/subscribers/mail/test", data={"subject": "S", "body": "B"},
                        follow_redirects=False).status_code == 403


# 9. CLI không tương tác

def _cli(env_password: str | None, email: str):
    import os
    env = {k: v for k, v in os.environ.items() if k != "ADMIN_PASSWORD" and k != "PYTHONIOENCODING"}
    if env_password:
        env["ADMIN_PASSWORD"] = env_password
    return subprocess.run([sys.executable, "-m", "app.cli", "create-admin", "--email", email], cwd=ROOT, env=env,
                          stdin=subprocess.DEVNULL, capture_output=True, encoding="utf-8", timeout=60)


def test_cli_uses_env_password_without_console(db):
    r = _cli("mat-khau-tu-env-123", "env@example.test")
    assert r.returncode == 0, r.stderr
    assert "env@example.test" in r.stdout
    from app.security import verify_password
    u = db.query(AdminUser).filter_by(email="env@example.test").one()
    assert verify_password(u.password_hash, "mat-khau-tu-env-123")


def test_cli_without_console_or_env_fails_cleanly(db):
    r = _cli(None, "khong@example.test")
    assert r.returncode == 2 and "ADMIN_PASSWORD" in r.stderr
    assert db.query(AdminUser).count() == 0


def test_cli_has_no_password_argument():
    assert "--password" not in (ROOT / "app" / "cli.py").read_text(encoding="utf-8")
