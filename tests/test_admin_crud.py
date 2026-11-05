import pytest

from conftest import errors_of, flash_code, make_bonus, make_broker, titles
from app.models import AdminUser, Banner, Bonus, Broker, Campaign, ContactMessage, Post, Subscriber

ADMIN_PAGES = ["/admin", "/admin/bonus", "/admin/bonus/new", "/admin/brokers", "/admin/brokers?tab=links",
               "/admin/brokers/new", "/admin/ads", "/admin/ads?tab=stats", "/admin/ads/new", "/admin/posts",
               "/admin/posts?tab=draft", "/admin/posts/new", "/admin/media", "/admin/subscribers",
               "/admin/subscribers?tab=mail", "/admin/messages", "/admin/messages?tab=unread"] + \
              [f"/admin/home?tab={t}" for t in ("sections", "hero", "about", "why", "types", "contact", "menu")] + \
              [f"/admin/pages?tab={t}" for t in ("bonus", "san", "tin", "gioithieu", "lienhe", "terms", "privacy")] + \
              [f"/admin/settings?tab={t}" for t in ("general", "seo", "social", "tracking", "users")]


@pytest.mark.parametrize("url", ADMIN_PAGES)
def test_admin_pages_render_empty(admin, url):
    r = admin.get(url)
    assert r.status_code == 200 and "noindex" in r.headers["x-robots-tag"]


CSRF_POSTS = ["/admin/bonus/new", "/admin/brokers/new", "/admin/ads/new", "/admin/posts/new", "/admin/home/hero",
              "/admin/pages/bonus", "/admin/media/upload", "/admin/settings/general", "/admin/subscribers/mail",
              "/admin/settings/users/new"]


@pytest.mark.parametrize("url", CSRF_POSTS)
def test_admin_posts_require_csrf(admin, url):
    assert admin.c.post(url, data={"title": "x"}, follow_redirects=False).status_code == 403
    assert admin.c.post(url, data={"csrf_token": "sai"}, follow_redirects=False).status_code == 403


# ---------- Bonus ----------

def test_bonus_crud(admin, db):
    k = make_broker(db)
    r = admin.post("/admin/bonus/new", {"min_deposit": "$10", "withdrawable": "Có", "broker_id": k.id, "type": "nodep", "title": "Bonus không cần nạp",
                                         "amount": "$50", "value_num": "50", "expiry_date": "2999-12-31",
                                         "is_active": "1"})
    assert r.status_code == 303 and r.headers["location"] == "/admin/bonus"
    b = db.query(Bonus).one()
    assert b.value_num == 50 and b.expiry_date.year == 2999 and b.is_active
    assert flash_code(admin.get("/admin/bonus")) == "created"

    r = admin.post(f"/admin/bonus/{b.id}/edit", {"min_deposit": "$10", "withdrawable": "Có", "broker_id": k.id, "type": "nodep", "title": "Đã sửa",
                                                 "expiry_date": "", "is_active": "1"})
    assert r.status_code == 303
    db.expire_all()
    b = db.get(Bonus, b.id)
    assert b.title == "Đã sửa" and b.expiry_date is None

    admin.post(f"/admin/bonus/{b.id}/toggle", {"back": "/admin/bonus?tab=off"})
    db.expire_all()
    assert not db.get(Bonus, b.id).is_active
    assert admin.get("/bonus").context["bonuses"] == []

    assert admin.post(f"/admin/bonus/{b.id}/delete").status_code == 303
    assert db.query(Bonus).count() == 0


def test_bonus_validation(admin, db):
    r = admin.post("/admin/bonus/new", {"min_deposit": "$10", "withdrawable": "Có", "broker_id": "999", "type": "xx", "title": "", "value_num": "abc",
                                         "expiry_date": "31-31-2020"})
    assert r.status_code == 400
    assert set(errors_of(r)) == {"broker_id", "type", "title", "value_num", "expiry_date"}
    assert r.context["drawer"]["data"]["value_num"] == "abc"  # giữ giá trị vừa nhập
    assert db.query(Bonus).count() == 0


def test_bonus_tabs_and_filters(admin, db):
    from datetime import timedelta

    from app.utils import today_vn
    k = make_broker(db)
    make_bonus(db, k, "Gần tới hạn", expiry_date=today_vn() + timedelta(days=3))
    make_bonus(db, k, "Còn lâu", expiry_date=today_vn() + timedelta(days=300), type="cashback")
    make_bonus(db, k, "Đã tắt", is_active=False)
    def listed(url):
        return titles(admin.get(url).context["bonuses"])
    assert listed("/admin/bonus?tab=exp") == ["Gần tới hạn"]
    assert listed("/admin/bonus?tab=off") == ["Đã tắt"]
    assert "Đã tắt" not in listed("/admin/bonus?tab=on")
    assert listed("/admin/bonus?type=cashback") == ["Còn lâu"]
    assert listed("/admin/bonus?q=gần") == ["Gần tới hạn"]
    assert titles(admin.get("/admin").context["expiring"]) == ["Gần tới hạn"]  # Tổng quan


# ---------- Sàn ----------

def test_broker_crud_with_lists(admin, db):
    r = admin.post("/admin/brokers/new", {
        "name": "Sàn Thử Nghiệm", "kind": "crypto", "license": "FSC", "affiliate_url": "https://example.com/a", "is_active": "1",
        "pros": "Ưu 1\n\nƯu 2", "cons": "Nhược 1",
        "account_name": ["Standard", "", "Pro"], "account_min_deposit": ["$10", "", "$200"],
        "account_spread": ["1.0", "", "0.1"], "account_commission": ["0", "", "$3"],
        "payment_method": ["USDT"], "payment_deposit": ["Miễn phí"], "payment_withdraw": ["Phí mạng"],
        "payment_time": ["Vài phút"]})
    assert r.status_code == 303
    k = db.query(Broker).one()
    assert k.slug == "san-thu-nghiem" and k.mono == "SA" and k.pros == ["Ưu 1", "Ưu 2"]
    assert [a["name"] for a in k.accounts] == ["Standard", "Pro"]
    assert k.payment_methods == [{"method": "USDT", "deposit": "Miễn phí", "withdraw": "Phí mạng", "time": "Vài phút"}]
    assert admin.get(f"/admin/brokers/{k.id}/edit").status_code == 200
    assert admin.get("/san/san-thu-nghiem").status_code == 200


def test_broker_validation(admin, db):
    make_broker(db, "Sàn A")
    r = admin.post("/admin/brokers/new", {"name": "Sàn A", "kind": "forex", "license": "FSC", "affiliate_url": "javascript:alert(1)"})
    assert r.status_code == 400
    assert {"slug", "affiliate_url"} <= set(errors_of(r))
    r = admin.post("/admin/brokers/new", {"name": "Sàn B", "kind": "forex", "license": "FSC", "affiliate_url": "ftp://x.example"})
    assert r.status_code == 400


def test_compare_limit_three(admin, db):
    ks = [make_broker(db, f"Sàn {c}") for c in "ABCD"]
    for k in ks[:3]:
        admin.post(f"/admin/brokers/{k.id}/toggle", {"field": "in_compare"})
    r = admin.post(f"/admin/brokers/{ks[3].id}/toggle", {"field": "in_compare"})
    assert r.status_code == 303
    assert flash_code(admin.get("/admin/brokers")) == "compare_limit"
    db.expire_all()
    assert db.query(Broker).filter_by(in_compare=True).count() == 3
    # qua form sửa cũng bị chặn
    r = admin.post(f"/admin/brokers/{ks[3].id}/edit", {"name": "Sàn D", "kind": "forex", "license": "FSC", "in_compare": "1", "is_active": "1"})
    assert r.status_code == 400 and "in_compare" in errors_of(r)
    # bỏ một sàn thì thêm được
    admin.post(f"/admin/brokers/{ks[0].id}/toggle", {"field": "in_compare"})
    admin.post(f"/admin/brokers/{ks[3].id}/toggle", {"field": "in_compare"})
    db.expire_all()
    assert db.get(Broker, ks[3].id).in_compare


def test_featured_max_one(admin, db):
    a, b = make_broker(db, "Sàn A"), make_broker(db, "Sàn B")
    admin.post(f"/admin/brokers/{a.id}/toggle", {"field": "featured"})
    admin.post(f"/admin/brokers/{b.id}/toggle", {"field": "featured"})
    db.expire_all()
    assert [k.name for k in db.query(Broker).filter_by(featured=True)] == ["Sàn B"]
    admin.post(f"/admin/brokers/{a.id}/edit", {"name": "Sàn A", "kind": "forex", "license": "FSC", "featured": "1", "is_active": "1"})
    db.expire_all()
    assert [k.name for k in db.query(Broker).filter_by(featured=True)] == ["Sàn A"]


def test_broker_toggle_active_and_link(admin, db):
    k = make_broker(db)
    admin.post(f"/admin/brokers/{k.id}/toggle", {"field": "is_active"})
    db.expire_all()
    assert not db.get(Broker, k.id).is_active
    assert admin.post(f"/admin/brokers/{k.id}/toggle", {"field": "xx"}).status_code == 400
    admin.post(f"/admin/brokers/{k.id}/link", {"affiliate_url": "https://example.com/moi"})
    db.expire_all()
    assert db.get(Broker, k.id).affiliate_url == "https://example.com/moi"
    admin.post(f"/admin/brokers/{k.id}/link", {"affiliate_url": "javascript:x"})
    db.expire_all()
    assert db.get(Broker, k.id).affiliate_url == "https://example.com/moi"


def test_broker_delete_cascades_bonus(admin, db):
    k = make_broker(db)
    make_bonus(db, k)
    db.add(Banner(name="QC", placement="after-bonus", broker_id=k.id, target_url="https://example.com"))
    db.commit()
    admin.post(f"/admin/brokers/{k.id}/delete")
    db.expire_all()
    assert db.query(Broker).count() == 0 and db.query(Bonus).count() == 0
    assert db.query(Banner).one().broker_id is None


# ---------- Quảng cáo ----------

def test_banner_crud(admin, db):
    r = admin.post("/admin/ads/new", {"name": "QC 1", "placement": "after-bonus", "target_url": "https://example.com/x",
                                       "start_date": "2000-01-01", "end_date": "2999-01-01", "is_active": "1"})
    assert r.status_code == 303
    b = db.query(Banner).one()
    assert admin.get("/").context["ad1"]["name"] == "QC 1"
    admin.post(f"/admin/ads/{b.id}/toggle")
    assert admin.get("/").context["ad1"] is None
    r = admin.post("/admin/ads/new", {"name": "", "placement": "giua", "target_url": "javascript:x",
                                       "start_date": "2020-05-01", "end_date": "2020-01-01"})
    assert r.status_code == 400
    assert {"name", "placement", "target_url", "end_date"} <= set(errors_of(r))
    admin.post(f"/admin/ads/{b.id}/delete")
    assert db.query(Banner).count() == 0


# ---------- Bài viết ----------

def test_post_crud(admin, db):
    body = " ".join(["chữ"] * 450)
    r = admin.post("/admin/posts/new", {"title": "Hướng dẫn nhận bonus", "category": "Hướng dẫn", "body_md": body,
                                         "status": "published", "show_home": "1"})
    assert r.status_code == 303
    p = db.query(Post).one()
    assert p.slug == "huong-dan-nhan-bonus" and p.read_minutes == 3 and p.published_at is not None
    assert titles(admin.get("/").context["blog_posts"]) == ["Hướng dẫn nhận bonus"]
    r = admin.post("/admin/posts/new", {"title": "Hướng dẫn nhận bonus", "category": "Hướng dẫn", "status": "draft"})
    assert r.status_code == 400 and "slug" in errors_of(r)
    admin.post(f"/admin/posts/{p.id}/toggle")
    db.expire_all()
    assert not db.get(Post, p.id).show_home
    admin.post(f"/admin/posts/{p.id}/edit", {"title": "Hướng dẫn nhận bonus", "slug": p.slug, "category": "Kiến thức",
                                             "status": "draft"})
    assert admin.get(f"/tin-tuc/{p.slug}").status_code == 404
    admin.post(f"/admin/posts/{p.id}/delete")
    assert db.query(Post).count() == 0


# ---------- Trang chủ / Trang / Cài đặt ----------

def test_home_sections_toggle_and_move(admin, db):
    from app import content
    admin.post("/admin/home/sections/about/toggle")
    admin.post("/admin/home/sections/about/move", {"direction": "up"})
    secs = content.get(db, "sections")
    assert secs[0]["id"] == "about" and secs[0]["on"] is False
    assert "about" not in admin.get("/").context["home_sections"]
    assert admin.post("/admin/home/sections/khong-co/toggle").status_code == 404


def test_home_tabs_save(admin, db):
    from app import content
    admin.post("/admin/home/hero", {"eyebrow": "Nhãn", "headline": "Tiêu đề mới", "sub": "Mô tả", "cta": "Nút",
                                     "image_path": "/static/img/hero-bg.webp"})
    admin.post("/admin/home/about", {"title": "Về", "point_title": ["Điểm 1"], "point_text": ["Nội dung 1"]})
    admin.post("/admin/home/why", {"title": "Tại sao", "reason_title": ["A", "B"], "reason_text": ["a", "b"]})
    admin.post("/admin/home/types", {"title": "Loại", "nodep_label": "Không nạp", "nodep_short": "ND",
                                     "nodep_desc": "Mô tả", "nodep_points": "Ý 1\nÝ 2"})
    admin.post("/admin/home/contact", {"title": "Đăng ký nhé"})
    admin.post("/admin/home/sections", {"bonus_title": "Bonus nóng", "blog_title": "Đọc thêm"})
    r = admin.post("/admin/home/menu", {"menu_label": ["Trang chủ", "Bonus"], "menu_url": ["/", "/bonus"],
                                        "footer_col_title": ["Cột 1"], "footer_col_links": ["Bonus | /bonus\nLiên hệ | /lien-he"],
                                        "risk_note": "Rủi ro", "copyright": "©"})
    assert r.status_code == 303
    s = content.get_all(db)
    assert s["hero"]["headline"] == "Tiêu đề mới" and s["hero"]["image_path"] == "/static/img/hero-bg.webp"
    assert s["home_about"]["points"] == [{"title": "Điểm 1", "text": "Nội dung 1"}]
    assert len(s["home_why"]["reasons"]) == 2
    nodep = s["bonus_types"][0]
    assert nodep["label"] == "Không nạp" and nodep["points"] == ["Ý 1", "Ý 2"]
    assert len(s["bonus_types"]) == 5
    assert s["home_bonus"]["title"] == "Bonus nóng" and s["home_blog"]["title"] == "Đọc thêm"
    assert s["footer"]["columns"] == [{"title": "Cột 1", "links": [{"label": "Bonus", "url": "/bonus"},
                                                                   {"label": "Liên hệ", "url": "/lien-he"}]}]
    assert s["menu"][1] == {"label": "Bonus", "url": "/bonus"}
    r = admin.post("/admin/home/menu", {"menu_label": ["Xấu"], "menu_url": ["javascript:alert(1)"]})
    assert r.status_code == 400 and content.get(db, "menu")[1]["label"] == "Bonus"


def test_pages_save(admin, db):
    from app import content
    admin.post("/admin/pages/bonus", {"title": "Bonus hot", "desc": "Mô tả", "meta_title": "SEO bonus"})
    admin.post("/admin/pages/gioithieu", {"title": "Giới thiệu", "about_block_title": ["Khối 1"],
                                          "about_block_text": ["Chữ 1"], "method_block_title": ["Khối M"],
                                          "method_block_text": ["Chữ M"]})
    admin.post("/admin/pages/lienhe", {"title": "Liên hệ", "topics": "Chủ đề 1\nChủ đề 2", "response_note": "Sớm"})
    admin.post("/admin/pages/terms", {"title": "Điều khoản", "body_md": "## Mục 1\nNội dung điều khoản"})
    assert admin.post("/admin/pages/bonus", {"title": ""}).status_code == 400
    s = content.get_all(db)
    assert s["pages"]["bonus"]["title"] == "Bonus hot"
    assert s["about_blocks"]["about"]["blocks"] == [{"title": "Khối 1", "text": "Chữ 1"}]
    assert s["contact_page"]["topics"] == ["Chủ đề 1", "Chủ đề 2"]
    assert admin.get("/bonus").context["meta"]["title"] == "SEO bonus"
    assert "Nội dung điều khoản" in admin.get("/dieu-khoan").context["body_html"]
    assert titles(admin.get("/gioi-thieu").context["about_blocks"]) == ["Khối 1"]
    assert titles(admin.get("/gioi-thieu/cach-danh-gia").context["about_blocks"]) == ["Khối M"]
    assert admin.get("/lien-he").context["contact"]["topics"] == ["Chủ đề 1", "Chủ đề 2"]


def test_settings_save(admin, db):
    from app import content
    r = admin.post("/admin/settings/general", {"site_name": "Site Thử", "contact_email": "lien-he@example.test",
                                                "partner_email": "", "telegram": "@thu"})
    assert r.status_code == 303
    assert admin.post("/admin/settings/general", {"site_name": "", "contact_email": "sai"}).status_code == 400
    admin.post("/admin/settings/seo", {"meta_title": "Meta mới", "meta_desc": "Mô tả mới"})
    assert admin.post("/admin/settings/social", {"social_label": ["FB"], "social_url": ["javascript:1"]}).status_code == 400
    admin.post("/admin/settings/social", {"social_label": ["FB"], "social_url": ["https://facebook.com/x"]})
    admin.post("/admin/settings/tracking", {"analytics_head": "<script>gtag()</script>"})
    s = content.get_all(db)
    assert s["site_name"] == "Site Thử" and s["contact_email"] == "lien-he@example.test"
    assert s["meta_title"] == "Meta mới" and s["social"] == [{"label": "FB", "url": "https://facebook.com/x"}]
    r = admin.get("/")
    assert r.context["meta"]["title"] == "Meta mới" and r.context["site"]["telegram"] == "@thu"
    assert "'unsafe-inline' https://www.googletagmanager.com" in r.headers["content-security-policy"]
    assert admin.post("/admin/settings/users", {}).status_code == 404


def test_admin_users(admin, db):
    r = admin.post("/admin/settings/users/new", {"email": "bien-tap@example.test", "password": "mat-khau-du-dai",
                                                  "role": "editor"})
    assert r.status_code == 303
    assert admin.post("/admin/settings/users/new", {"email": "bien-tap@example.test", "password": "ngan",
                                                    "role": "x"}).status_code == 400
    me = db.query(AdminUser).filter_by(email="admin@example.test").one()
    other = db.query(AdminUser).filter_by(email="bien-tap@example.test").one()
    admin.post(f"/admin/settings/users/{me.id}/delete")
    admin.post(f"/admin/settings/users/{me.id}/toggle")
    assert admin.post(f"/admin/settings/users/{me.id}/edit", {"role": "editor"}).status_code == 400
    db.expire_all()
    assert db.get(AdminUser, me.id).is_active and db.get(AdminUser, me.id).role == "admin"
    admin.post(f"/admin/settings/users/{other.id}/edit", {"role": "admin", "password": "mat-khau-moi-123"})
    admin.post(f"/admin/settings/users/{other.id}/toggle")
    db.expire_all()
    assert db.get(AdminUser, other.id).role == "admin" and not db.get(AdminUser, other.id).is_active
    admin.post(f"/admin/settings/users/{other.id}/delete")
    assert db.query(AdminUser).count() == 1


# ---------- Khách ----------

def test_messages(admin, db):
    m = ContactMessage(topic="Hợp tác", name="Khách", email="khach@example.test", body="Xin chào")
    db.add(m)
    db.commit()
    assert titles(admin.get("/admin/messages?tab=unread").context["messages"], "email") == ["khach@example.test"]
    assert admin.get(f"/admin/messages/{m.id}").context["selected"]["body"] == "Xin chào"
    db.expire_all()
    assert db.get(ContactMessage, m.id).is_read
    admin.post(f"/admin/messages/{m.id}/toggle")
    db.expire_all()
    assert not db.get(ContactMessage, m.id).is_read
    admin.post(f"/admin/messages/{m.id}/delete")
    assert db.query(ContactMessage).count() == 0


def test_campaign_send(admin, db):
    from app import mailer
    db.add_all([
        Subscriber(email="a@example.test", interests=["deposit"], status="confirmed", token="t-a"),
        Subscriber(email="b@example.test", interests=["crypto"], status="confirmed", token="t-b"),
        Subscriber(email="c@example.test", interests=[], status="confirmed", token="t-c"),
        Subscriber(email="d@example.test", interests=["deposit"], status="pending", token="t-d"),
        Subscriber(email="e@example.test", interests=["deposit"], status="unsubscribed", token="t-e"),
    ])
    db.commit()
    c = admin.get("/admin/subscribers?tab=mail&aud=deposit").context
    assert c["audience_count"] == 2
    assert {o["id"]: o["count"] for o in c["audience_options"]}["crypto"] == 2
    assert admin.post("/admin/subscribers/mail", {"subject": "", "body": ""}).status_code == 400
    r = admin.post("/admin/subscribers/mail", {"subject": "Bonus mới", "body": "Nội dung", "audience": ["deposit"],
                                                "action": "send"})
    assert r.status_code == 303
    assert sorted(m["To"] for m in mailer.outbox) == ["a@example.test", "c@example.test"]
    for m in mailer.outbox:
        assert "/huy-dang-ky/t-" in m.get_content() and m["List-Unsubscribe"]
    c = db.query(Campaign).one()
    assert c.status == "sent" and c.sent_count == 2
    admin.post("/admin/subscribers/mail", {"subject": "Nháp", "body": "x", "action": "draft"})
    assert db.query(Campaign).filter_by(status="draft").count() == 1
    sub = db.query(Subscriber).filter_by(email="a@example.test").one()
    admin.post(f"/admin/subscribers/{sub.id}/delete")
    assert db.query(Subscriber).count() == 4


def test_overview_stats_from_db(admin, db):
    from app.models import ClickLog
    from app.utils import today_vn
    k = make_broker(db)
    make_bonus(db, k)
    make_bonus(db, k, "Tắt", is_active=False)
    db.add(Subscriber(email="x@example.test", status="confirmed", token="tok"))
    db.add(ClickLog(kind="ad", ref_id=1, day=today_vn(), count=7))
    db.commit()
    c = admin.get("/admin").context
    stats = {s["id"]: s["value"] for s in c["stats"]}
    assert stats == {"bonus": "1/2", "banners": "0", "ad_clicks": "7", "subscribers": "1"}
