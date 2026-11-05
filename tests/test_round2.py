"""Hồi quy QA vòng 2 (docs/QA_REPORT.md)."""
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from conftest import ROOT, errors_of, make_broker
from app import content, mailer
from app.config import Config, ConfigError
from app.models import Bonus, Broker, Campaign, Subscriber, utcnow
from app.routes import admin_people, public
from app.utils import slugify


def subscribe(client, **data):
    return client.post("/api/subscribe", data={"email": "nannhan@example.test", "next": "/"} | data, follow_redirects=False)


def unsubscribed_row(db, email="nannhan@example.test", sent_hours_ago=25) -> Subscriber:
    sub = Subscriber(email=email, name="Chủ thật", interests=["crypto"], status="unsubscribed", token="tok-cu",
                     confirm_sent_at=utcnow() - timedelta(hours=sent_hours_ago), confirm_count=1)
    db.add(sub)
    db.commit()
    return sub


# N-1

def test_limit_holds_under_concurrent_requests(db, monkeypatch):
    from app.main import app
    monkeypatch.setattr(public.public_form_limiter, "limit", 10_000)

    def post(_):
        with TestClient(app) as c:
            return subscribe(c).status_code

    with ThreadPoolExecutor(12) as pool:
        assert set(pool.map(post, range(20))) == {303}
    assert len(mailer.outbox) == 3
    assert db.query(Subscriber).one().confirm_count == 3


def test_failed_send_returns_the_slot(client, db):
    with mock.patch.object(mailer, "send_many", lambda messages: 0):
        subscribe(client)
    sub = db.query(Subscriber).one()
    assert sub.confirm_count == 0 and sub.confirm_sent_at is None


# N-2

def test_unsubscribed_gets_one_email_and_keeps_status(client, db):
    unsubscribed_row(db)
    for _ in range(4):
        subscribe(client)
        public.public_form_limiter.reset()
    db.expire_all()
    sub = db.query(Subscriber).one()
    assert len(mailer.outbox) == 1 and sub.status == "unsubscribed" and sub.token == "tok-cu"


def test_status_changes_only_when_owner_clicks_link(client, db):
    unsubscribed_row(db)
    subscribe(client)
    db.expire_all()
    link = f"/xac-nhan/{db.query(Subscriber).one().reconfirm_token}"
    assert link in mailer.outbox[0].get_content()
    assert client.get(link).context["status"] == "ask_confirm"  # máy quét chỉ GET: chưa đổi gì
    db.expire_all()
    assert db.query(Subscriber).one().status == "unsubscribed"
    client.post(link)
    db.expire_all()
    assert db.query(Subscriber).one().status == "confirmed"


def test_second_email_next_day_reuses_same_link(client, db):
    sub = unsubscribed_row(db)
    subscribe(client)
    db.expire_all()
    first = db.get(Subscriber, sub.id).reconfirm_token
    db.get(Subscriber, sub.id).confirm_sent_at = utcnow() - timedelta(hours=25)
    db.commit()
    public.public_form_limiter.reset()
    subscribe(client)
    db.expire_all()
    assert len(mailer.outbox) == 2 and db.get(Subscriber, sub.id).reconfirm_token == first


# N-3

def test_resubscribe_within_a_day_is_told_to_wait(client, db):
    unsubscribed_row(db, sent_hours_ago=2)
    subscribe(client)
    assert mailer.outbox == []
    assert client.get("/").context["flash"]["code"] == "sub_wait"


def test_with_link_already_mailed_check_inbox_is_true(client, db):
    unsubscribed_row(db)
    subscribe(client)
    public.public_form_limiter.reset()
    subscribe(client)
    assert len(mailer.outbox) == 1
    assert client.get("/").context["flash"]["code"] == "sub_ok"


# N-4

def test_resume_does_not_resend_when_header_is_normalized(admin, db):
    odd = "a,b@example.test"
    db.add_all([Subscriber(email=odd, status="confirmed", token="t1"),
                Subscriber(email="c@example.test", status="confirmed", token="t2")])
    db.commit()

    def only_odd(messages):
        for m in messages:
            if "b@example.test" in m["To"]:
                m.delivered = True
        return sum(1 for m in messages if getattr(m, "delivered", False))

    with mock.patch.object(admin_people, "send_many", only_odd):
        admin.post("/admin/subscribers/mail", {"subject": "S", "body": "B", "action": "send"})
    c = db.query(Campaign).one()
    assert c.status == "partial" and c.sent_to == [odd]
    admin.post("/admin/subscribers/mail", {"subject": "S", "body": "B", "draft_id": c.id, "action": "send"})
    assert [m["To"] for m in mailer.outbox] == ["c@example.test"]


# N-5

def test_stranger_cannot_overwrite_pending_data(client, db):
    subscribe(client, name="Chủ thật", interests=["crypto"])
    public.public_form_limiter.reset()
    subscribe(client, name="Kẻ lạ", interests=["deposit"])
    db.expire_all()
    sub = db.query(Subscriber).one()
    assert sub.name == "Chủ thật" and sub.interests == ["crypto"]


def test_stranger_cannot_overwrite_unsubscribed_data(client, db):
    unsubscribed_row(db)
    subscribe(client, name="Kẻ lạ", interests=["deposit"])
    db.expire_all()
    sub = db.query(Subscriber).one()
    assert sub.name == "Chủ thật" and sub.interests == ["crypto"]


# N-6

@pytest.mark.parametrize("text,slug", [("Ðồng Eth", "dong-eth"), ("đồng ĐÔ", "dong-do"), ("ðỏ", "do"), ("", "")])
def test_slugify_all_d_letters(text, slug):
    assert slugify(text) == slug


# N-7

@pytest.mark.parametrize("name", ["PORT", "SMTP_PORT"])
@pytest.mark.parametrize("value", ["abc", "0", "70000", "-1"])
def test_bad_port_is_a_config_problem(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    c = Config()  # không được ném lỗi lúc import
    with pytest.raises(ConfigError, match=name):
        c.validate()


def test_run_py_bad_port_exits_2_without_traceback(tmp_path):
    env = os.environ | {"PORT": "abc", "DATABASE_URL": f"sqlite:///{(tmp_path / 'x.db').as_posix()}"}
    r = subprocess.run([sys.executable, "run.py"], cwd=ROOT, env=env, capture_output=True, encoding="utf-8", timeout=60)
    assert r.returncode == 2 and "Traceback" not in r.stderr and "PORT" in r.stderr


# N-8

@pytest.mark.parametrize("secret", [" " * 40, "\t" * 40, "x" + " " * 39])
def test_blank_secret_key_refused(monkeypatch, secret):
    for k, v in {"APP_ENV": "production", "SECRET_KEY": secret, "BASE_URL": "https://site.example",
                 "SMTP_BACKEND": "console"}.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(ConfigError, match="SECRET_KEY"):
        Config().validate()


# N-9

@pytest.mark.parametrize("tab,url", [("terms", "/dieu-khoan"), ("privacy", "/bao-mat")])
def test_legal_breadcrumb_uses_label(admin, client, tab, url):
    admin.post(f"/admin/pages/{tab}", {"title": "Tiêu đề dài", "label": "Nhãn ngắn", "body_md": "x"})
    assert client.get(url).context["crumbs"][-1] == {"label": "Nhãn ngắn", "url": url}


# N-10, N-11

def test_readme_restore_and_production_blocks():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    prod = readme[readme.index("Production:"):readme.index("Tạo tài khoản quản trị")]
    assert '$env:APP_ENV = "production"' in prod
    restore = readme[readme.index("Phục hồi"):]
    assert restore.index("Remove-Item -Recurse -Force data\\uploads") < restore.index("Copy-Item -Recurse backup-uploads data\\uploads")
    assert "Copy-Item backup.db data\\app.db" in restore


# N2

def _bonus(admin, broker, **data):
    return admin.post("/admin/bonus/new", {"broker_id": broker.id, "type": "deposit", "title": "T",
                                           "min_deposit": "$10", "withdrawable": "Có"} | data)


@pytest.mark.parametrize("field", ["min_deposit", "withdrawable"])
@pytest.mark.parametrize("value", ["", "—"])
def test_bonus_conditions_are_optional(admin, db, field, value):
    assert _bonus(admin, make_broker(db), **{field: value}).status_code == 303
    assert getattr(db.query(Bonus).one(), field) == value


@pytest.mark.parametrize("value", ["$0", "Không", "Lợi nhuận"])
def test_bonus_accepts_real_conditions(admin, db, value):
    assert _bonus(admin, make_broker(db), withdrawable=value, min_deposit="$0").status_code == 303


# N3

@pytest.mark.parametrize("value", ["-", "—", "...", "n/a", "Không có"])
def test_license_rejects_placeholders(admin, db, value):
    r = admin.post("/admin/brokers/new", {"name": "Sàn", "kind": "forex", "license": value, "is_active": "1"})
    assert r.status_code == 400 and "license" in errors_of(r) and db.query(Broker).count() == 0


# N5

def test_featured_labels_are_settings(admin, client, db):
    site = client.get("/").context["site"]
    assert site["hero"]["card_label"] == "Nổi bật tuần này" and site["home_compare"]["featured_label"] == "Phổ biến"
    admin.post("/admin/home/sections", {"compare_featured_label": "Được chọn nhiều"})
    assert content.get(db, "home_compare")["featured_label"] == "Được chọn nhiều"
    admin.post("/admin/home/sections", {"compare_title": "Tiêu đề"})  # form không gửi trường này: giữ nguyên
    assert content.get(db, "home_compare")["featured_label"] == "Được chọn nhiều"


# N6

def test_privacy_promises_only_what_admin_can_do(client):
    html = client.get("/bao-mat").context["body_html"].lower()
    assert "sửa" not in html and "xóa dữ liệu" in html and "hủy nhận email" in html
