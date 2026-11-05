"""Hồi quy QA Phase 4: email, chiến dịch, banner, SEO, độ dài, nội dung mặc định."""
import io
import re
from datetime import timedelta
from unittest import mock

import pytest
from PIL import Image
from sqlalchemy import update

from conftest import errors_of, flash_code, login, make_broker, make_user, titles
from app import content, mailer
from app.models import AdminUser, Banner, Broker, Campaign, ClickLog, MediaFile, Post, Subscriber, utcnow
from app.routes import admin_people, public
from app.utils import today_vn


def subscribe(client, **data):
    return client.post("/api/subscribe", data={"email": "nannhan@example.test", "next": "/"} | data, follow_redirects=False)


# ---------- C-2 ----------

def test_confirm_email_has_no_sender_text(client):
    subscribe(client, name="TRÚNG THƯỞNG 500 USD, nhận tại http://evil.example/x")
    msg = mailer.outbox[0]
    assert "TRÚNG THƯỞNG" not in msg.get_content() and "evil.example" not in msg.get_content()
    assert "TRÚNG THƯỞNG" not in msg["Subject"]


def test_confirm_emails_limited_per_address_not_per_ip(client, db):
    for i in range(6):
        client.post("/api/subscribe", data={"email": "nannhan@example.test"}, follow_redirects=False)
        public.public_form_limiter.reset()  # mô phỏng đổi IP
    assert len(mailer.outbox) == 3
    assert db.query(Subscriber).one().confirm_count == 3
    assert client.get("/").context["flash"]["code"] == "sub_ok"  # không lộ là đã bị giới hạn


def test_limit_window_resets_after_a_day(client, db):
    for _ in range(3):
        subscribe(client)
        public.public_form_limiter.reset()
    db.expire_all()
    db.query(Subscriber).one().confirm_sent_at = utcnow() - timedelta(days=1, minutes=1)
    db.commit()
    subscribe(client)
    assert len(mailer.outbox) == 4


def test_unsubscribed_address_is_not_mailed_again(client, db):
    subscribe(client)
    token = db.query(Subscriber).one().token
    client.post(f"/huy-dang-ky/{token}")
    mailer.outbox.clear()
    for _ in range(4):
        subscribe(client)
        public.public_form_limiter.reset()
    db.expire_all()
    sub = db.query(Subscriber).one()
    assert mailer.outbox == [] and sub.status == "unsubscribed" and sub.token == token


# ---------- C-3 ----------

def test_visitor_not_told_to_check_inbox_when_send_fails(client, db):
    with mock.patch.object(mailer, "send_many", lambda messages: 0):
        subscribe(client)
    assert client.get("/").context["flash"]["code"] == "sub_failed"
    sub = db.query(Subscriber).one()
    assert sub.status == "pending" and sub.confirm_count == 0  # lần hỏng không tính vào giới hạn
    subscribe(client)
    assert client.get("/").context["flash"]["code"] == "sub_ok" and len(mailer.outbox) == 1


def _confirmed(db, *emails):
    db.add_all([Subscriber(email=e, status="confirmed", token=f"t-{e}") for e in emails])
    db.commit()


def test_campaign_total_failure_stays_resendable(admin, db):
    _confirmed(db, "a@example.test", "b@example.test")
    with mock.patch.object(admin_people, "send_many", lambda messages: 0):
        r = admin.post("/admin/subscribers/mail", {"subject": "S", "body": "B", "action": "send"})
    c = db.query(Campaign).one()
    assert c.status == "draft" and c.sent_count == 0 and c.sent_at is None
    page = admin.get(r.headers["location"])
    assert flash_code(page) == "send_failed" and page.context["mail_form"]["draft_id"] == c.id
    r = admin.post("/admin/subscribers/mail", {"subject": "S", "body": "B", "draft_id": c.id, "action": "send"})
    db.expire_all()
    assert flash_code(admin.get(r.headers["location"])) == "sent"
    assert db.get(Campaign, c.id).status == "sent" and db.get(Campaign, c.id).sent_count == 2


def test_campaign_partial_failure_resumes_without_duplicates(admin, db):
    _confirmed(db, "a@example.test", "b@example.test", "c@example.test")

    def first_only(messages):
        messages[0].delivered = True
        return 1

    with mock.patch.object(admin_people, "send_many", first_only):
        r = admin.post("/admin/subscribers/mail", {"subject": "S", "body": "B", "action": "send"})
    c = db.query(Campaign).one()
    assert c.status == "partial" and c.sent_count == 1 and len(c.sent_to) == 1
    page = admin.get(r.headers["location"])
    assert flash_code(page) == "send_partial" and page.context["campaigns"][0]["edit_url"]
    first = c.sent_to[0]
    admin.post("/admin/subscribers/mail", {"subject": "S", "body": "B", "draft_id": c.id, "action": "send"})
    db.expire_all()
    c = db.get(Campaign, c.id)
    assert c.status == "sent" and c.sent_count == 3
    assert first not in [m["To"] for m in mailer.outbox] and len(mailer.outbox) == 2


def _stuck(db, sent_to, minutes_ago=20):
    c = Campaign(subject="S", body="B", status="sending", sent_to=sent_to, sent_count=0)
    db.add(c)
    db.commit()
    db.execute(update(Campaign).where(Campaign.id == c.id).values(updated_at=utcnow() - timedelta(minutes=minutes_ago)))
    db.commit()
    return c.id


def test_stuck_sending_reopens_after_timeout(admin, db):
    _confirmed(db, "a@example.test", "b@example.test")
    cid = _stuck(db, ["a@example.test"])
    row = admin.get("/admin/subscribers?tab=mail").context["campaigns"][0]
    assert row["status"] == "partial" and row["edit_url"] and row["sent_count"] == 1
    assert admin.get(row["edit_url"]).status_code == 200
    admin.post("/admin/subscribers/mail", {"subject": "S", "body": "B", "draft_id": cid, "action": "send"})
    db.expire_all()
    assert [m["To"] for m in mailer.outbox] == ["b@example.test"] and db.get(Campaign, cid).status == "sent"


def test_stuck_without_progress_returns_to_draft(admin, db):
    cid = _stuck(db, [])
    assert admin.get(f"/admin/subscribers?tab=mail&draft={cid}").status_code == 200
    db.expire_all()
    assert db.get(Campaign, cid).status == "draft"


def test_recent_sending_is_not_released(admin, db):
    cid = _stuck(db, [], minutes_ago=1)
    assert admin.get(f"/admin/subscribers?tab=mail&draft={cid}").status_code == 404  # có thể đang gửi thật: chặn gửi trùng
    db.expire_all()
    assert db.get(Campaign, cid).status == "sending"


def test_startup_releases_every_sending(db):
    from app import queries
    cid = _stuck(db, [], minutes_ago=0)
    assert queries.release_stuck_campaigns(db, stale_minutes=0) == 1
    db.expire_all()
    assert db.get(Campaign, cid).status == "draft"


def test_progress_saved_per_batch_and_stops_on_failure(admin, db, monkeypatch):
    monkeypatch.setattr(admin_people, "SEND_BATCH", 2)
    _confirmed(db, *[f"u{i}@example.test" for i in range(5)])
    calls = []

    def fail_second_batch(messages):
        calls.append(len(messages))
        if len(calls) == 2:
            return 0
        for m in messages:
            m.delivered = True
        return len(messages)

    with mock.patch.object(admin_people, "send_many", fail_second_batch):
        admin.post("/admin/subscribers/mail", {"subject": "S", "body": "B", "action": "send"})
    c = db.query(Campaign).one()
    assert calls == [2, 2] and c.status == "partial" and len(c.sent_to) == 2 and c.sent_count == 2


def test_refused_address_does_not_stop_the_rest(admin, db, monkeypatch):
    monkeypatch.setattr(admin_people, "SEND_BATCH", 2)
    _confirmed(db, *[f"u{i}@example.test" for i in range(5)])
    refused = db.query(Subscriber).first().email

    def refuse_one(messages):  # SMTP vẫn sống, chỉ một địa chỉ bị từ chối
        good = [m for m in messages if m["To"] != refused]
        for m in good:
            m.delivered = True
        return len(good)

    with mock.patch.object(admin_people, "send_many", refuse_one):
        admin.post("/admin/subscribers/mail", {"subject": "S", "body": "B", "action": "send"})
    c = db.query(Campaign).one()
    assert c.status == "partial" and c.sent_count == 4 and refused not in c.sent_to


def test_partial_with_nobody_left_finishes(admin, db):
    _confirmed(db, "a@example.test")
    c = Campaign(subject="S", body="B", status="partial", sent_to=["a@example.test"], sent_count=1)
    db.add(c)
    db.commit()
    r = admin.post("/admin/subscribers/mail", {"subject": "S", "body": "B", "draft_id": c.id, "action": "send"})
    db.expire_all()
    assert r.status_code == 303 and db.get(Campaign, c.id).status == "sent" and mailer.outbox == []


def test_resume_count_excludes_people_already_mailed(admin, db):
    _confirmed(db, "a@example.test", "b@example.test")
    c = Campaign(subject="S", body="B", status="partial", sent_to=["a@example.test"], sent_count=1)
    db.add(c)
    db.commit()
    assert admin.get(f"/admin/subscribers?tab=mail&draft={c.id}").context["audience_count"] == 1


def test_concurrent_send_only_one_wins(admin, db):
    _confirmed(db, "a@example.test")
    c = Campaign(subject="S", body="B", status="sent")
    db.add(c)
    db.commit()
    # Request thứ hai đã qua kiểm tra _draft trước khi request đầu đổi trạng thái.
    with mock.patch.object(admin_people, "_draft", lambda session, cid: session.get(Campaign, cid)):
        r = admin.post("/admin/subscribers/mail", {"subject": "S", "body": "B", "draft_id": c.id, "action": "send"})
    assert r.status_code == 404 and mailer.outbox == []


def test_shared_connection_logs_in_once(monkeypatch):
    server = mock.MagicMock()
    connect = mock.MagicMock(return_value=server)
    monkeypatch.setattr(mailer, "_connect", connect)
    monkeypatch.setattr(mailer.config, "smtp_backend", "smtp")
    with mailer.shared_connection():
        assert mailer.send_many([mailer.build("a@example.test", "S", "B")]) == 1
        assert mailer.send_many([mailer.build("b@example.test", "S", "B")]) == 1
    assert connect.call_count == 1 and server.send_message.call_count == 2 and server.quit.called


def test_unsubscribed_can_resubscribe_next_day(client, db):
    subscribe(client)
    client.post(f"/huy-dang-ky/{db.query(Subscriber).one().token}")
    db.expire_all()
    db.query(Subscriber).one().confirm_sent_at = utcnow() - timedelta(days=1, minutes=1)
    db.commit()
    mailer.outbox.clear()
    subscribe(client)
    db.expire_all()
    assert len(mailer.outbox) == 1 and db.query(Subscriber).one().status == "unsubscribed"


def test_excerpt_is_not_double_escaped(client, db):
    db.add(Post(slug="bai", title="T", category="Kiến thức", status="published", body_md="A & B"))
    db.commit()
    r = client.get("/tin-tuc/bai")
    assert r.context["meta"]["description"] == "A & B" and "&amp;amp;" not in r.text


def test_bad_referer_on_expired_post_is_not_500(client):
    r = client.post("/admin/bonus/5/toggle", data={}, follow_redirects=False, headers={"referer": "http://[bad"})
    assert r.status_code == 303 and r.headers["location"] == "/admin/login?next=/admin"


def test_get_on_post_only_admin_url_goes_to_overview(admin):
    r = admin.get("/admin/subscribers/mail", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/admin"


def test_no_recipients_keeps_typed_text(admin, db):
    r = admin.post("/admin/subscribers/mail", {"subject": "Tiêu đề", "body": "Nội dung", "action": "send"})
    assert r.status_code == 400 and flash_code(r) == "no_recipients"
    assert r.context["mail_form"]["body"] == "Nội dung" and db.query(Campaign).count() == 0


# ---------- M6 ----------

def test_delete_draft_campaign(admin, db):
    admin.post("/admin/subscribers/mail", {"subject": "Nháp", "body": "B", "action": "draft"})
    c = db.query(Campaign).one()
    url = admin.get("/admin/subscribers?tab=mail").context["campaigns"][0]["delete_url"]
    assert url == f"/admin/subscribers/campaigns/{c.id}/delete"
    assert admin.post(url).status_code == 303 and db.query(Campaign).count() == 0


def test_cannot_delete_sent_campaign(admin, db):
    db.add(Campaign(subject="S", body="B", status="sent"))
    db.commit()
    c = db.query(Campaign).one()
    assert admin.get("/admin/subscribers?tab=mail").context["campaigns"][0]["delete_url"] is None
    assert admin.post(f"/admin/subscribers/campaigns/{c.id}/delete").status_code == 404


# ---------- T-1, T-2 ----------

def test_banner_without_target_is_not_live(client, admin, db):
    k = make_broker(db, affiliate_url="https://example.com/a")
    b = Banner(name="QC", placement="after-bonus", broker_id=k.id, target_url="", is_active=True)
    db.add(b)
    db.commit()
    assert client.get("/").context["ad1"]["name"] == "QC"
    admin.post(f"/admin/brokers/{k.id}/link", {"affiliate_url": ""})
    db.expire_all()
    assert client.get("/").context["ad1"] is None
    assert admin.get("/admin/ads").context["banners"][0]["state"] == "no_link"
    assert client.get(f"/go/ad/{b.id}", follow_redirects=False).status_code == 404
    assert db.get(Banner, b.id).views == 1  # không cộng view khi không hiển thị


def test_banner_after_broker_deleted_or_hidden(client, admin, db):
    k = make_broker(db)
    b = Banner(name="QC", placement="before-blog", broker_id=k.id, target_url="", is_active=True)
    db.add(b)
    db.commit()
    admin.post(f"/admin/brokers/{k.id}/toggle", {"field": "is_active"})
    assert admin.get("/admin/ads").context["banners"][0]["state"] == "broker_hidden"
    admin.post(f"/admin/brokers/{k.id}/delete")
    db.expire_all()
    assert admin.get("/admin/ads").context["banners"][0]["state"] == "no_link"
    assert client.get("/").context["ad2"] is None


def test_dead_banner_does_not_shadow_live_one(client, db):
    db.add_all([Banner(name="Sống", placement="after-bonus", target_url="https://example.com/a", is_active=True),
                Banner(name="Chết", placement="after-bonus", target_url="", is_active=True)])
    db.commit()
    assert client.get("/").context["ad1"]["name"] == "Sống"


def test_section_off_counts_no_views(client, admin, db):
    b = Banner(name="QC", placement="after-bonus", target_url="https://example.com/a", is_active=True)
    db.add(b)
    db.commit()
    admin.post("/admin/home/sections/ad1/toggle")
    for _ in range(3):
        client.get("/")
    db.expire_all()
    assert db.get(Banner, b.id).views == 0


# ---------- T-3, nghi ngờ 2 ----------

def test_second_signup_keeps_first_link_working(client, db):
    subscribe(client)
    first = re.search(r"/xac-nhan/\S+", mailer.outbox[0].get_content()).group(0)
    subscribe(client)
    assert first in mailer.outbox[1].get_content()
    client.post(first)
    db.expire_all()
    assert db.query(Subscriber).one().status == "confirmed"


def test_get_on_email_links_changes_nothing(client, db):
    subscribe(client)
    token = db.query(Subscriber).one().token
    r = client.get(f"/xac-nhan/{token}")
    assert r.context["status"] == "ask_confirm" and r.context["action_url"] == f"/xac-nhan/{token}"
    r = client.get(f"/huy-dang-ky/{token}")
    assert r.context["status"] == "ask_unsubscribe" and r.context["action_url"] == f"/huy-dang-ky/{token}"
    db.expire_all()
    assert db.query(Subscriber).one().status == "pending"
    client.post(f"/xac-nhan/{token}")
    assert client.get(f"/xac-nhan/{token}").context["status"] == "confirmed"
    client.post(f"/huy-dang-ky/{token}")
    assert client.get(f"/huy-dang-ky/{token}").context["status"] == "unsubscribed"
    assert client.get(f"/xac-nhan/{token}").status_code == 404


def test_emails_have_one_click_unsubscribe(client):
    subscribe(client)
    assert mailer.outbox[0]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


# ---------- T-4, M5 ----------

def test_section_seo_does_not_override_item_pages(admin, client, db):
    k = make_broker(db, summary="Tóm tắt riêng của sàn")
    db.add(Post(slug="bai", title="Bài riêng", category="Kiến thức", status="published", excerpt="Tóm tắt riêng của bài"))
    db.commit()
    admin.post("/admin/pages/san", {"title": "Sàn", "meta_title": "SEO chung mục Sàn", "meta_desc": "Mô tả chung"})
    admin.post("/admin/pages/tin", {"title": "Tin", "meta_title": "SEO chung Tin", "meta_desc": "Mô tả chung Tin"})
    assert client.get("/san").context["meta"]["title"] == "SEO chung mục Sàn"
    meta = client.get(f"/san/{k.slug}").context["meta"]
    assert meta["title"].startswith("Đánh giá Sàn A") and meta["description"] == "Tóm tắt riêng của sàn"
    meta = client.get("/tin-tuc/bai").context["meta"]
    assert meta["title"].startswith("Bài riêng") and meta["description"] == "Tóm tắt riêng của bài"


def test_post_without_excerpt_gets_description_from_body(client, db):
    db.add(Post(slug="bai", title="T", category="Kiến thức", status="published", body_md="**Đoạn đầu** của bài."))
    db.commit()
    assert client.get("/tin-tuc/bai").context["meta"]["description"] == "Đoạn đầu của bài."


def test_default_pages_have_unique_seo(client):
    urls = ["/bonus", "/san", "/san/so-sanh", "/tin-tuc", "/gioi-thieu", "/gioi-thieu/cach-danh-gia", "/gioi-thieu/affiliate",
            "/lien-he", "/dieu-khoan", "/bao-mat"]
    metas = [client.get(u).context["meta"] for u in urls]
    assert len({m["title"] for m in metas}) == len(urls)
    assert len({m["description"] for m in metas}) >= len(urls) - 2  # hai trang pháp lý dùng mô tả chung của site


def test_breadcrumb_labels_come_from_settings(admin, client, db):
    k = make_broker(db)
    assert client.get("/san").context["crumbs"][-1]["label"] == "Sàn"
    admin.post("/admin/pages/san", {"title": "Sàn", "label": "Danh sách sàn"})
    assert client.get("/san").context["crumbs"][-1]["label"] == "Danh sách sàn"
    assert client.get(f"/san/{k.slug}").context["crumbs"][1]["label"] == "Danh sách sàn"
    assert client.get("/san/so-sanh").context["crumbs"][1]["label"] == "Danh sách sàn"


def test_old_form_without_label_keeps_it(admin, db):
    admin.post("/admin/pages/san", {"title": "Sàn"})
    assert content.get(db, "pages")["san"]["label"] == "Sàn"


@pytest.mark.parametrize("tab", ["compare", "method", "affiliate", "system"])
def test_new_page_tabs_render(admin, tab):
    assert admin.get(f"/admin/pages?tab={tab}").status_code == 200


def test_system_fields_list_every_key(admin):
    fields = admin.get("/admin/pages?tab=system").context["system_fields"]
    assert {f["key"] for f in fields} == set(content.DEFAULTS["system_text"])
    assert all(f["label"] and f["value"] for f in fields)


# ---------- T-5 ----------

def test_reserved_broker_slug_refused(admin):
    r = admin.post("/admin/brokers/new", {"name": "So sánh", "kind": "forex", "license": "FSC", "is_active": "1"})
    assert r.status_code == 400 and "slug" in errors_of(r)


# ---------- T-10 ----------

@pytest.mark.parametrize("url,data,key", [
    ("/admin/brokers/new", {"name": "x" * 121, "kind": "forex", "license": "L"}, "name"),
    ("/admin/brokers/new", {"name": "Sàn", "kind": "forex", "license": "L", "founded": "1" * 21}, "founded"),
    ("/admin/posts/new", {"title": "x" * 256, "category": "Kiến thức", "status": "draft"}, "title"),
    ("/admin/posts/new", {"title": "T", "category": "Kiến thức", "status": "draft", "body_md": "x" * 100001}, "body_md"),
    ("/admin/ads/new", {"name": "x" * 121, "placement": "after-bonus", "target_url": "https://example.com"}, "name"),
    ("/admin/home/why", {"title": "T", "reason_title": ["A"], "reason_text": ["x" * 5001]}, "reason_text"),
    ("/admin/home/hero", {"headline": "x" * 1001}, "headline"),
    ("/admin/pages/gioithieu", {"title": "T", "about_block_title": ["A"], "about_block_text": ["x" * 5001]}, "about_block_text"),
    ("/admin/pages/system", {"error_title": "x" * 501}, "error_title"),
    ("/admin/settings/general", {"site_name": "x" * 121}, "site_name"),
    ("/admin/subscribers/mail", {"subject": "x" * 256, "body": "B"}, "subject"),
])
def test_too_long_is_error_not_truncated(admin, url, data, key):
    r = admin.post(url, data)
    assert r.status_code == 400 and key in errors_of(r)


def test_long_about_block_now_saves_whole(admin, db):
    text = "x" * 1500
    assert admin.post("/admin/pages/gioithieu", {"title": "T", "about_block_title": ["A"],
                                                 "about_block_text": [text]}).status_code == 303
    assert content.get(db, "about_blocks")["about"]["blocks"][0]["text"] == text


def test_bonus_title_too_long_keeps_value(admin, db):
    k = make_broker(db)
    long_title = "x" * 400
    r = admin.post("/admin/bonus/new", {"min_deposit": "$10", "withdrawable": "Có", "broker_id": k.id, "type": "deposit", "title": long_title})
    assert r.status_code == 400 and r.context["drawer"]["data"]["title"] == long_title


# ---------- Thấp ----------

def test_concurrent_slug_conflict_is_400_not_500(admin, db):
    make_broker(db, "Sàn A")
    from app.routes import admin_data
    real = admin_data.Admin.check_lengths

    def race(self, errors):  # sau khi kiểm tra slug xong, sàn cùng slug xuất hiện
        real(self, errors)
        errors.pop("slug", None)

    with mock.patch.object(admin_data.Admin, "check_lengths", race):
        r = admin.post("/admin/brokers/new", {"name": "Sàn A", "kind": "forex", "license": "L"})
    assert r.status_code == 400 and "slug" in errors_of(r)
    assert db.query(Broker).count() == 1


def test_hidden_broker_does_not_take_compare_slot(admin, db):
    ks = [make_broker(db, f"Sàn {c}", in_compare=True) for c in "ABC"]
    extra = make_broker(db, "Sàn D")
    admin.post(f"/admin/brokers/{ks[0].id}/toggle", {"field": "is_active"})
    assert admin.get("/admin/brokers").context["compare_count"] == 2
    admin.post(f"/admin/brokers/{extra.id}/toggle", {"field": "in_compare"})
    db.expire_all()
    assert db.get(Broker, extra.id).in_compare
    # bật lại sàn đã ẩn khi đã đủ 3: nó mất suất, không thành 4
    admin.post(f"/admin/brokers/{ks[0].id}/toggle", {"field": "is_active"})
    db.expire_all()
    assert db.query(Broker).filter_by(in_compare=True, is_active=True).count() == 3
    assert flash_code(admin.get("/admin/brokers")) == "compare_limit"


def test_views_and_clicks_do_not_touch_updated_at(client, db):
    k = make_broker(db)
    p = Post(slug="bai", title="T", category="Kiến thức", status="published")
    b = Banner(name="QC", placement="after-bonus", target_url="https://example.com/a", is_active=True)
    db.add_all([p, b])
    db.commit()
    before = (db.get(Broker, k.id).updated_at, db.get(Post, p.id).updated_at, db.get(Banner, b.id).updated_at)
    client.get(f"/go/broker/{k.id}", follow_redirects=False)
    client.get("/tin-tuc/bai")
    client.get("/")
    client.get(f"/go/ad/{b.id}", follow_redirects=False)
    db.expire_all()
    assert db.get(Broker, k.id).clicks == 1 and db.get(Post, p.id).views == 1 and db.get(Banner, b.id).clicks == 1
    assert before == (db.get(Broker, k.id).updated_at, db.get(Post, p.id).updated_at, db.get(Banner, b.id).updated_at)


def test_delete_removes_click_logs(admin, client, db):
    k = make_broker(db)
    b = Banner(name="QC", placement="after-bonus", target_url="https://example.com/a", is_active=True)
    db.add(b)
    db.commit()
    client.get(f"/go/broker/{k.id}", follow_redirects=False)
    client.get(f"/go/ad/{b.id}", follow_redirects=False)
    assert db.query(ClickLog).count() == 2
    admin.post(f"/admin/brokers/{k.id}/delete")
    admin.post(f"/admin/ads/{b.id}/delete")
    assert db.query(ClickLog).count() == 0
    assert admin.get("/admin").context["click_total"] == 0


def test_contact_topic_must_be_in_list(client, db):
    r = client.post("/api/contact", data={"topic": "Chủ đề tự chế", "email": "a@example.test", "body": "x"})
    assert r.status_code == 400 and "topic" in r.context["form"]["errors"]


def test_contact_error_page_canonical(client):
    r = client.post("/api/contact", data={"email": "sai", "body": ""})
    meta = r.context["meta"]
    assert meta["canonical"] == "http://testserver/lien-he" and meta["noindex"] is True
    assert r.context["current_path"] == "/lien-he"
    assert client.get("/lien-he").context["meta"]["noindex"] is False


def _exif_jpeg(orientation=1) -> bytes:
    img = Image.new("RGB", (40, 20), (200, 10, 10))
    exif = img.getexif()
    exif[0x010F] = "MayAnhBiMat"
    exif[0x0112] = orientation
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def _saved(admin, db, name, data, mime):
    assert admin.post("/admin/media/upload", {}, files=[("files", (name, data, mime))]).status_code == 303
    m = db.query(MediaFile).order_by(MediaFile.id.desc()).first()
    return m, admin.get(m.path).content


def test_upload_strips_exif(admin, db):
    m, body = _saved(admin, db, "a.jpg", _exif_jpeg(), "image/jpeg")
    assert b"MayAnhBiMat" not in body and not Image.open(io.BytesIO(body)).getexif()
    assert m.size == len(body)


def test_upload_applies_orientation_before_stripping(admin, db):
    m, body = _saved(admin, db, "a.jpg", _exif_jpeg(orientation=6), "image/jpeg")  # xoay 90 độ
    assert (m.width, m.height) == (20, 40) and b"MayAnhBiMat" not in body


def test_upload_strips_png_text_and_webp_exif(admin, db):
    from PIL.PngImagePlugin import PngInfo
    info = PngInfo()
    info.add_text("GPS", "BiMatToaDo")
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, "PNG", pnginfo=info)
    _, body = _saved(admin, db, "a.png", buf.getvalue(), "image/png")
    assert b"BiMatToaDo" not in body
    img = Image.new("RGB", (8, 8))
    exif = img.getexif()
    exif[0x010F] = "MayAnhBiMat"
    buf = io.BytesIO()
    img.save(buf, "WEBP", exif=exif)
    _, body = _saved(admin, db, "a.webp", buf.getvalue(), "image/webp")
    assert b"MayAnhBiMat" not in body


def test_upload_without_metadata_keeps_bytes(admin, db):
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, "JPEG")
    _, body = _saved(admin, db, "a.jpg", buf.getvalue(), "image/jpeg")
    assert body == buf.getvalue()


def test_expired_session_on_post_returns_to_page_not_post_route(client, db):
    make_user(db)
    r = client.post("/admin/bonus/5/toggle", data={"csrf_token": "x"}, follow_redirects=False,
                    headers={"referer": "http://testserver/admin/bonus?tab=off"})
    assert r.status_code == 303 and "toggle" not in r.headers["location"]
    assert r.headers["location"] == "/admin/login?next=/admin/bonus%3Ftab%3Doff"
    r = client.post("/admin/bonus/5/toggle", data={}, follow_redirects=False, headers={"referer": "https://evil.example/admin/x"})
    assert r.headers["location"] == "/admin/login?next=/admin"
    assert client.get("/admin/login?next=/admin/bonus%3Ftab%3Doff").context["next"] == "/admin/bonus?tab=off"


def test_password_with_spaces_and_long_works(admin, client, db):
    password = "  mat khau co khoang trang  "
    assert admin.post("/admin/settings/users/new", {"email": "u@example.test", "password": password,
                                                    "role": "editor"}).status_code == 303
    from app.security import verify_password
    assert verify_password(db.query(AdminUser).filter_by(email="u@example.test").one().password_hash, password)
    r = admin.post("/admin/settings/users/new", {"email": "v@example.test", "password": "x" * 201, "role": "editor"})
    assert r.status_code == 400 and "password" in errors_of(r)
    u = db.query(AdminUser).filter_by(email="u@example.test").one()
    r = admin.post(f"/admin/settings/users/{u.id}/edit", {"role": "admin", "password": "ngan"})
    assert r.status_code == 400 and r.context["form"]["data"]["edit_role"] == "admin"


def test_static_image_path_rejects_traversal(admin, db):
    r = admin.post("/admin/home/hero", {"headline": "H", "image_path": "/static/img/../../admin/logout.png"})
    assert r.status_code == 400 and "image_path" in errors_of(r)
    assert admin.post("/admin/home/hero", {"headline": "H", "image_path": "/static/img/logo.png"}).status_code == 303


# ---------- back khi xóa ----------

def test_delete_keeps_list_filter(admin, db):
    k = make_broker(db)
    db.add(Subscriber(email="a@example.test", status="confirmed", token="t"))
    db.commit()
    s = db.query(Subscriber).one()
    r = admin.post(f"/admin/subscribers/{s.id}/delete", {"back": "/admin/subscribers?status=confirmed"})
    assert r.headers["location"] == "/admin/subscribers?status=confirmed"
    r = admin.post(f"/admin/brokers/{k.id}/delete", {"back": f"/admin/brokers/{k.id}/edit"})
    assert r.headers["location"] == "/admin/brokers"


# ---------- nghi ngờ 4 ----------

def test_future_post_hidden_until_its_date(admin, client, db):
    future = (today_vn() + timedelta(days=3)).isoformat()
    admin.post("/admin/posts/new", {"title": "Bài hẹn giờ", "category": "Kiến thức", "status": "published",
                                    "published_at": future, "show_home": "1"})
    p = db.query(Post).one()
    assert client.get("/tin-tuc").context["posts"] == []
    assert client.get(f"/tin-tuc/{p.slug}").status_code == 404
    assert client.get("/").context["blog_posts"] == []
    assert p.slug not in client.get("/sitemap.xml").text
    assert {t["id"]: t["count"] for t in client.get("/tin-tuc").context["tabs"]}["all"] == 0
    row = admin.get("/admin/posts").context["posts"][0]
    assert row["scheduled"] is True and row["view_url"] is None


def test_post_dated_today_is_public_now(admin, client, db):
    admin.post("/admin/posts/new", {"title": "Bài hôm nay", "category": "Kiến thức", "status": "published",
                                    "published_at": today_vn().isoformat()})
    assert titles(client.get("/tin-tuc").context["posts"]) == ["Bài hôm nay"]


def test_past_date_is_public_and_clearing_future_date_publishes(admin, client, db):
    admin.post("/admin/posts/new", {"title": "Bài", "category": "Kiến thức", "status": "published",
                                    "published_at": (today_vn() + timedelta(days=3)).isoformat()})
    p = db.query(Post).one()
    admin.post(f"/admin/posts/{p.id}/edit", {"title": "Bài", "slug": p.slug, "category": "Kiến thức", "status": "published"})
    assert titles(client.get("/tin-tuc").context["posts"]) == ["Bài"]


# ---------- license, nội dung mặc định ----------

def test_broker_requires_license(admin, db):
    r = admin.post("/admin/brokers/new", {"name": "Sàn K", "kind": "forex", "is_active": "1"})
    assert r.status_code == 400 and "license" in errors_of(r) and db.query(Broker).count() == 0


def test_default_content_has_no_unbacked_claims(db):
    blob = str(content.resolve({}))
    for banned in ("100%", "khối lượng yêu cầu", "Khối lượng yêu cầu", "lot phải đạt", "Tối đa một email mỗi tuần",
                   "hằng ngày", "khi có bonus mới", "Nhận tư vấn", "1–2 ngày", "hero-bg", "2026"):
        assert banned not in blob, banned


def test_empty_defaults(db):
    s = content.resolve({})
    assert s["hero"]["image_path"] == "" and s["home_why"]["stat_value"] == "" and s["home_about"]["badge"] == ""
    assert s["system_text"]["header_cta_page"] == "Xem bonus"


def test_copyright_year_is_current(client, db):
    assert client.get("/").context["site"]["footer"]["copyright"] == f"Copyright © {today_vn().year} TradingBonusHub."
    assert "{year}" in content.get(db, "footer")["copyright"]  # admin vẫn thấy mẫu để sửa


def test_legal_defaults_render_and_are_honest(client):
    for url, words in (("/dieu-khoan", ("affiliate", "không phải lời khuyên đầu tư", "hủy đăng ký")),
                       ("/bao-mat", ("địa chỉ email", "cookie", "Google Fonts", "bấm", "Liên hệ"))):
        html = client.get(url).context["body_html"].lower()
        for w in words:
            assert w.lower() in html, w
        assert "<h2>" in html
    assert 'href="/lien-he"' in client.get("/bao-mat").context["body_html"]


def test_login_still_works(client, db):
    make_user(db)
    assert login(client).status_code == 303


def test_about_subpage_label_shows_in_breadcrumb(admin, client):
    admin.post("/admin/pages/method", {"title": "Cách đánh giá", "label": "Nhãn riêng"})
    assert "Nhãn riêng" in client.get("/gioi-thieu/cach-danh-gia").text
