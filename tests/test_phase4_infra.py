"""Hồi quy QA Phase 4: cấu hình, request rác, header, HEAD, redirect, CLI."""
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from conftest import ROOT, login, make_broker, make_user
from app.config import Config, ConfigError
from app.models import AdminUser

GOOD_PROD = {"APP_ENV": "production", "SECRET_KEY": "k" * 32, "BASE_URL": "https://site.example", "SMTP_BACKEND": "console"}


def cfg(monkeypatch, **env) -> Config:
    for name in ("APP_ENV", "SECRET_KEY", "BASE_URL", "SMTP_BACKEND", "SMTP_HOST", "FROM_EMAIL"):
        monkeypatch.delenv(name, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return Config()


# C-1, T-8, Thấp 21

def test_good_production_config_passes(monkeypatch):
    c = cfg(monkeypatch, **GOOD_PROD)
    c.validate()
    assert any("KHÔNG được gửi" in w for w in c.warnings())


@pytest.mark.parametrize("change,needle", [
    ({"BASE_URL": ""}, "BASE_URL"), ({"BASE_URL": "khong-phai-url"}, "BASE_URL"), ({"SMTP_BACKEND": ""}, "SMTP_BACKEND"),
    ({"SMTP_BACKEND": "gmail"}, "SMTP_BACKEND"), ({"SECRET_KEY": ""}, "SECRET_KEY"), ({"SECRET_KEY": "x"}, "SECRET_KEY"),
    ({"APP_ENV": "prod"}, "APP_ENV"), ({"SMTP_BACKEND": "smtp"}, "SMTP_HOST"),
])
def test_bad_production_config_refused(monkeypatch, change, needle):
    c = cfg(monkeypatch, **(GOOD_PROD | change))
    with pytest.raises(ConfigError, match=needle):
        c.validate()


def test_smtp_backend_needs_from_email(monkeypatch):
    c = cfg(monkeypatch, **(GOOD_PROD | {"SMTP_BACKEND": "smtp", "SMTP_HOST": "mail.example"}))
    with pytest.raises(ConfigError, match="FROM_EMAIL"):
        c.validate()


def test_unknown_app_env_is_treated_as_production(monkeypatch):
    c = cfg(monkeypatch, APP_ENV="prod")
    assert c.is_production and c.secret_key == ""


def test_development_needs_nothing(monkeypatch):
    c = cfg(monkeypatch, APP_ENV="development")
    c.validate()
    assert c.smtp_backend == "console" and c.base_url.startswith("http://127.0.0.1")


def test_run_py_refuses_without_traceback(tmp_path):
    env = {k: v for k, v in os.environ.items() if k not in ("APP_ENV", "SECRET_KEY", "BASE_URL", "SMTP_BACKEND")}
    env |= {"DATABASE_URL": f"sqlite:///{(tmp_path / 'x.db').as_posix()}", "PORT": "8019"}
    r = subprocess.run([sys.executable, "run.py"], cwd=ROOT, env=env, capture_output=True, encoding="utf-8", timeout=60)
    assert r.returncode == 2 and "Traceback" not in r.stderr
    assert "SECRET_KEY" in r.stderr and "BASE_URL" in r.stderr and "SMTP_BACKEND" in r.stderr


# T-6

@pytest.mark.parametrize("url", ["/go/broker/99999999999999999999999", "/go/ad/99999999999999999999999"])
def test_huge_id_is_404(client, url):
    assert client.get(url, follow_redirects=False).status_code == 404


def test_huge_id_beacon_and_admin(admin):
    huge = "9" * 25
    assert admin.c.post(f"/api/ad-view/{huge}").status_code == 404
    assert admin.get(f"/admin/bonus/{huge}/edit").status_code == 404
    assert admin.post(f"/admin/bonus/{huge}/delete").status_code == 404


@pytest.mark.parametrize("token", ["é", "tiếng việt"])
def test_non_ascii_csrf_is_rejected_not_500(client, db, token):
    make_user(db)
    client.get("/admin/login")
    r = client.post("/admin/login", data={"email": "admin@example.test", "password": "x", "csrf_token": token},
                    follow_redirects=False)
    assert r.status_code == 403


def test_non_ascii_or_file_csrf_when_logged_in(admin):
    assert admin.c.post("/admin/logout", data={"csrf_token": "é"}).status_code == 403
    r = admin.c.post("/admin/logout", files={"csrf_token": ("a.txt", b"x")})
    assert r.status_code == 403


@pytest.mark.parametrize("url", ["/static/a%3Fb", "/media/" + "a" * 5000, "/static/" + "b" * 400, "/media/a%00b"])
def test_bad_static_paths_are_404(client, url):
    assert client.get(url).status_code == 404


# T-7

def test_500_page_has_security_headers(monkeypatch):
    from app import main
    from app.routes import public
    monkeypatch.setattr(public.queries, "visible_bonus_counts", lambda db: 1 / 0)
    monkeypatch.setattr(main.config, "is_production", True)
    r = TestClient(main.app, raise_server_exceptions=False).get("/bonus")
    assert r.status_code == 500 and r.template.name == "public/500.html"
    for header in ("content-security-policy", "x-content-type-options", "x-frame-options", "strict-transport-security"):
        assert header in r.headers, header


# T-9

def test_password_reset_keeps_role(db):
    from app.cli import create_admin, main
    make_user(db, "bien-tap@example.test", role="editor")
    assert create_admin("bien-tap@example.test", None, "mat-khau-moi-1234") == 0
    db.expire_all()
    assert db.query(AdminUser).one().role == "editor"
    assert create_admin("moi@example.test", None, "mat-khau-moi-1234") == 0
    assert db.query(AdminUser).filter_by(email="moi@example.test").one().role == "admin"
    assert create_admin("bien-tap@example.test", "admin", "mat-khau-moi-1234") == 0  # đổi vai trò phải nói rõ
    db.expire_all()
    assert db.query(AdminUser).filter_by(email="bien-tap@example.test").one().role == "admin"
    with pytest.raises(SystemExit):
        main(["create-admin"])  # --email vẫn bắt buộc


# Thấp 3, 4

@pytest.mark.parametrize("url", ["/tin-tuc?page=abc", "/tin-tuc?page=", "/tin-tuc?page=1.5", "/go/broker/abc", "/go/ad/x"])
def test_bad_param_shows_404_page_not_json(client, url):
    r = client.get(url, follow_redirects=False)
    assert r.status_code == 404 and r.headers["content-type"].startswith("text/html")


def test_bad_form_field_type_is_400_not_json(client):
    r = client.post("/api/contact", files={"email": ("a.txt", b"x")})
    assert r.status_code == 400 and not r.headers["content-type"].startswith("application/json")


@pytest.mark.parametrize("url", ["/", "/bonus", "/health", "/sitemap.xml", "/robots.txt", "/static/css/site.css"])
def test_head_works(client, url):
    r = client.head(url)
    assert r.status_code == 200 and r.content == b""


def test_head_does_not_count(client, db):
    from app.models import Banner, Broker, Post
    k = make_broker(db)
    b = Banner(name="QC", placement="after-bonus", target_url="https://example.com/a", is_active=True)
    p = Post(slug="bai", title="Bài", category="Kiến thức", status="published")
    db.add_all([b, p])
    db.commit()
    assert client.head("/").status_code == 200 and client.head("/tin-tuc/bai").status_code == 200
    assert client.head(f"/go/broker/{k.id}").status_code == 405
    db.expire_all()
    assert db.get(Banner, b.id).views == 0 and db.get(Post, p.id).views == 0 and db.get(Broker, k.id).clicks == 0


# Thấp 15

def test_trailing_slash_redirect_is_relative(client):
    r = client.get("/bonus/?type=nodep", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "/bonus?type=nodep"


def test_trailing_slash_redirect_is_not_open_redirect(client):
    location = client.get("//evil.example/", follow_redirects=False).headers.get("location", "")
    assert not location.startswith("//")


# Thấp 22: đã bỏ /docs ở mọi môi trường (test_public.test_no_api_docs)

# Nghi ngờ 3

def test_login_limit_per_ip_across_emails(client, db):
    make_user(db)
    for i in range(20):
        assert login(client, email=f"u{i}@example.test", password="sai").status_code == 401
    assert login(client, email="khac@example.test", password="sai").status_code == 429
    assert login(client).status_code == 429


# Nghi ngờ 9

def test_body_limit_public(client):
    r = client.post("/api/contact", content=b"x" * (1024 * 1024 + 1),
                    headers={"content-type": "application/x-www-form-urlencoded"})
    assert r.status_code == 413 and "x-content-type-options" in r.headers


def test_body_limit_without_content_length(client):
    def chunks():
        for _ in range(3):
            yield b"x" * (600 * 1024)
    r = client.post("/api/contact", content=chunks(), headers={"content-type": "application/x-www-form-urlencoded"})
    assert r.status_code == 413


def test_chunked_admin_body_has_lower_limit_before_auth(client):
    def chunks():
        for _ in range(9):
            yield b"x" * (1024 * 1024)
    r = client.post("/admin/media/upload", content=chunks(), headers={"content-type": "application/x-www-form-urlencoded"})
    assert r.status_code == 413


def test_small_chunked_body_still_works(client, db):
    from app.models import ContactMessage

    def chunks():
        yield b"email=a%40example.test&"
        yield b"body=xin+chao"
    r = client.post("/api/contact", content=chunks(), headers={"content-type": "application/x-www-form-urlencoded"},
                    follow_redirects=False)
    assert r.status_code == 303 and db.query(ContactMessage).one().body == "xin chao"


# Thấp 6, 7, 19, 2

@pytest.mark.parametrize("value", ["inf", "-inf", "1e999", "nan"])
def test_value_num_rejects_non_finite(admin, db, value):
    k = make_broker(db)
    r = admin.post("/admin/bonus/new", {"min_deposit": "$10", "withdrawable": "Có", "broker_id": k.id, "type": "deposit", "title": "x", "value_num": value})
    assert r.status_code == 400


def test_markdown_keeps_headings_and_fenced_code():
    from app.utils import render_markdown
    html = render_markdown("# Một\n\n##### Năm\n\n```\ndòng 1\ndòng 2\n```\n")
    assert "<h2>Một</h2>" in html and "<h4>Năm</h4>" in html and "<h1" not in html
    assert "dòng 1\ndòng 2" in html and "<pre>" in html


def test_mono_for_non_latin_name():
    from app.utils import mono_from_name
    assert mono_from_name("日本証券") == "日本"
    assert mono_from_name("Sàn Thử") == "SA"


def test_slugify_long_title_ends_clean():
    from app.utils import slugify
    slug = slugify("a" * 119 + " bcd")
    assert slug == "a" * 119 and len(slug) <= 120
