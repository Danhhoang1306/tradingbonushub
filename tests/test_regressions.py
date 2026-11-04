"""Hồi quy cho các lỗi tìm được khi review."""
import io
import os
from pathlib import Path

from PIL import Image

from conftest import AdminClient, login, make_broker, make_user
from app.models import AdminSession, Broker, MediaFile


def png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, "PNG")
    return buf.getvalue()


def test_unicode_digits_do_not_crash(client, admin, db):
    make_broker(db)
    assert client.get("/san/so-sanh?ids=²,٣,1").status_code == 200
    r = admin.post("/admin/bonus/new", {"broker_id": "²", "type": "deposit", "title": "x"})
    assert r.status_code == 400


def test_upload_survives_failed_form(admin, db):
    r = admin.post("/admin/brokers/new", {"name": "", "kind": "forex"},
                   files=[("logo_path_file", ("l.png", png(), "image/png"))])
    assert r.status_code == 400
    m = db.query(MediaFile).one()  # ảnh đã vào thư viện dù form lỗi
    assert (Path(os.environ["UPLOAD_DIR"]) / m.path.rsplit("/", 1)[1]).exists()
    r = admin.post("/admin/brokers/new", {"name": "Sàn A", "kind": "forex", "logo_path": m.path})
    assert r.status_code == 303 and db.query(Broker).one().logo_path == m.path


def test_password_reset_revokes_sessions(client, db):
    from app.cli import create_admin
    make_user(db)
    login(client)
    assert db.query(AdminSession).count() == 1
    create_admin("admin@example.test", "admin", "mat-khau-moi-12345")
    assert client.get("/admin", follow_redirects=False).status_code == 303


def test_change_own_password_keeps_current_session(client, db):
    from fastapi.testclient import TestClient

    from app.main import app
    u = make_user(db)
    other = TestClient(app)
    login(other)
    login(client)
    a = AdminClient(client)
    assert a.post(f"/admin/settings/users/{u.id}/edit", {"password": "mat-khau-moi-12345"}).status_code == 303
    assert client.get("/admin").status_code == 200
    assert other.get("/admin", follow_redirects=False).status_code == 303


def test_rate_limiter_bounded_memory():
    from app.security import RateLimiter
    rl = RateLimiter(2, 60)
    rl.MAX_KEYS = 10
    for i in range(100):
        assert not rl.blocked(f"k{i}")
        rl.hit(f"k{i}")
    assert len(rl._hits) == 10
    rl.hit("x")
    rl.hit("x")
    assert rl.blocked("x")


def test_production_is_default(monkeypatch):
    import pytest

    from app.config import Config
    monkeypatch.delenv("APP_ENV")
    monkeypatch.delenv("SECRET_KEY")
    cfg = Config()
    assert cfg.is_production
    with pytest.raises(RuntimeError):
        cfg.require_secret()
    monkeypatch.setenv("SECRET_KEY", "k")
    Config().require_secret()


def test_campaign_recorded(admin, db):
    from app.models import Campaign, Subscriber
    db.add(Subscriber(email="a@example.test", status="confirmed", token="t1"))
    db.commit()
    admin.post("/admin/subscribers/mail", {"subject": "S", "body": "B", "action": "send"})
    c = db.query(Campaign).one()
    assert c.status == "sent" and c.sent_count == 1
