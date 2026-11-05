"""Form public: đăng ký nhận bonus (double opt-in, hủy) và liên hệ."""
import re

from app import mailer
from app.models import ContactMessage, Subscriber


def subscribe(client, **data):
    payload = {"name": "Khách", "email": "khach@example.test", "interests": ["deposit", "cashback", "xx"],
               "next": "/"} | data
    return client.post("/api/subscribe", data=payload, follow_redirects=False)


def test_subscribe_double_opt_in_and_unsubscribe(client, db):
    r = subscribe(client)
    assert r.status_code == 303 and r.headers["location"] == "/#dang-ky"
    sub = db.query(Subscriber).one()
    assert sub.status == "pending" and sub.interests == ["deposit", "cashback"]
    assert client.get("/").context["flash"]["code"] == "sub_ok"

    assert len(mailer.outbox) == 1
    text = mailer.outbox[0].get_content()
    confirm = re.search(r"http://testserver(/xac-nhan/\S+)", text).group(1)
    unsub = re.search(r"http://testserver(/huy-dang-ky/\S+)", text).group(1)
    assert mailer.outbox[0]["List-Unsubscribe"]

    assert client.post(confirm).status_code == 200
    db.expire_all()
    sub = db.query(Subscriber).one()
    assert sub.status == "confirmed" and sub.confirmed_at is not None

    assert client.post(unsub).status_code == 200
    db.expire_all()
    assert db.query(Subscriber).one().status == "unsubscribed"
    assert client.post(confirm).status_code == 404  # link xác nhận cũ không còn dùng được


def test_subscribe_again_after_confirmed_sends_nothing(client, db):
    subscribe(client)
    token = db.query(Subscriber).one().token
    client.post(f"/xac-nhan/{token}")
    mailer.outbox.clear()
    subscribe(client)
    assert mailer.outbox == [] and db.query(Subscriber).count() == 1


def test_resubscribe_after_unsubscribe(client, db):
    subscribe(client)
    old = db.query(Subscriber).one().token
    client.post(f"/huy-dang-ky/{old}")
    from datetime import timedelta

    from app.models import utcnow
    db.expire_all()
    db.query(Subscriber).one().confirm_sent_at = utcnow() - timedelta(days=2)  # quá hạn chờ dành cho người đã hủy
    db.commit()
    mailer.outbox.clear()
    subscribe(client, email="KHACH@example.test")
    db.expire_all()
    sub = db.query(Subscriber).one()
    assert sub.status == "unsubscribed" and sub.reconfirm_token and sub.token == old  # chưa đổi cho tới khi chủ bấm link
    assert f"/xac-nhan/{sub.reconfirm_token}" in mailer.outbox[0].get_content()
    assert client.post(f"/xac-nhan/{old}").status_code == 404  # link cũ không kích hoạt lại
    assert client.post(f"/xac-nhan/{sub.reconfirm_token}").status_code == 200
    db.expire_all()
    sub = db.query(Subscriber).one()
    assert sub.status == "confirmed" and sub.reconfirm_token is None


def test_subscribe_invalid_email(client, db):
    r = subscribe(client, email="khong-phai-email")
    assert r.status_code == 303 and db.query(Subscriber).count() == 0
    assert client.get("/").context["flash"]["code"] == "sub_invalid"


def test_subscribe_honeypot(client, db):
    r = subscribe(client, website="http://spam.example")
    assert r.status_code == 303 and db.query(Subscriber).count() == 0 and mailer.outbox == []


def test_subscribe_next_not_open_redirect(client):
    assert subscribe(client, next="//evil.example").headers["location"] == "/#dang-ky"
    assert subscribe(client, next="/\t/evil.example").headers["location"] == "/#dang-ky"
    assert subscribe(client, next="/bonus?type=nodep", email="b@example.test").headers["location"] == \
        "/bonus?type=nodep#dang-ky"


def test_subscribe_rate_limit(client, db):
    for i in range(5):
        subscribe(client, email=f"k{i}@example.test")
    subscribe(client, email="k9@example.test")
    assert db.query(Subscriber).count() == 5
    assert client.get("/").context["flash"]["code"] == "sub_rate"


def test_cf_header_ignored_from_non_loopback(client, db):
    # TestClient có host "testclient" (không phải loopback) nên header CF bị bỏ qua: không lách được rate limit.
    for i in range(6):
        client.post("/api/subscribe", data={"email": f"k{i}@example.test"},
                    headers={"CF-Connecting-IP": f"203.0.113.{i}"}, follow_redirects=False)
    assert db.query(Subscriber).count() == 5


def test_bad_tokens(client):
    assert client.get("/xac-nhan/khong-ton-tai").status_code == 404
    assert client.get("/huy-dang-ky/khong-ton-tai").status_code == 404


def test_contact_form(client, db):
    r = client.post("/api/contact", data={"topic": "Hợp tác", "name": "Khách", "email": "khach@example.test",
                                          "body": "Xin chào"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/lien-he"
    m = db.query(ContactMessage).one()
    assert m.topic == "Hợp tác" and not m.is_read
    assert client.get("/lien-he").context["flash"]["code"] == "contact_ok"


def test_contact_validation_keeps_values(client, db):
    r = client.post("/api/contact", data={"name": "Khách Lỗi", "email": "sai", "body": ""})
    assert r.status_code == 400
    form = r.context["form"]
    assert form["data"]["name"] == "Khách Lỗi" and set(form["errors"]) == {"email", "body"}
    assert db.query(ContactMessage).count() == 0


def test_contact_honeypot_and_rate_limit(client, db):
    client.post("/api/contact", data={"email": "a@example.test", "body": "x", "website": "spam"})
    assert db.query(ContactMessage).count() == 0
    for _ in range(5):
        client.post("/api/contact", data={"email": "a@example.test", "body": "x"})
    r = client.post("/api/contact", data={"email": "a@example.test", "body": "x"})
    assert r.status_code == 429 and "form" in r.context["form"]["errors"]
    assert db.query(ContactMessage).count() == 5


def test_client_ip_trusts_cf_only_from_loopback():
    from starlette.requests import Request

    from app.security import client_ip

    def req(host, cf):
        headers = [(b"cf-connecting-ip", cf.encode())] if cf else []
        return Request({"type": "http", "client": (host, 1), "headers": headers})

    assert client_ip(req("127.0.0.1", "203.0.113.5")) == "203.0.113.5"
    assert client_ip(req("198.51.100.7", "203.0.113.5")) == "198.51.100.7"
    assert client_ip(req("127.0.0.1", "")) == "127.0.0.1"
