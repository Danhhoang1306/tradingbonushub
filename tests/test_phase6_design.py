"""Phase 6: trả về đúng thiết kế (brief mục 13)."""
from datetime import date, datetime, timedelta

import pytest
from conftest import make_bonus, make_broker, titles

from app import content, mailer
from app.config import config
from app.models import Banner, Bonus, Broker, Campaign, Post, Subscriber
from app.templating import ctr, expiry_label, login_day
from app.utils import date_range_label, parse_date_range, today_vn


# ---------- câu chữ ----------

@pytest.mark.parametrize("text", [
    "Mỗi ưu đãi ghi rõ khối lượng yêu cầu, thời hạn và giấy phép.",
    "khối lượng lot phải đạt, phần nào rút được, thời hạn và khu vực áp dụng.",
    "Cập nhật ưu đãi hằng ngày",
    "cần giao dịch bao nhiêu lot và bonus có bị trừ khi rút tiền hay không.",
    "Khối lượng yêu cầu, phần rút được và thời hạn hiển thị ngay trên mỗi ưu đãi.",
    "Ưu đãi có tóm tắt điều kiện rút tiền",
    "Chọn loại ưu đãi bạn quan tâm. Tối đa một email mỗi tuần.",
    "Quy đổi yêu cầu khối lượng sang số lot cụ thể để dễ so sánh giữa các sàn.",
    "Chúng tôi phản hồi trong 1–2 ngày làm việc. Chúng tôi không tư vấn đầu tư cá nhân.",
    "Nổi bật tuần này", "Phổ biến", "Nhận tư vấn", "Sàn uy tín",
])
def test_design_text_is_default(text):
    assert text in str(content.resolve({}))


def test_hero_image_is_design_image():
    assert content.resolve({})["hero"]["image_path"] == "/static/img/hero-bg.webp"


def test_stat_card_stays_hidden_by_default():
    assert content.resolve({})["home_why"]["stat_value"] == ""


# ---------- header chung, SEO riêng ----------

@pytest.mark.parametrize("url,head,crumb,seo", [
    ("/san/so-sanh", "Sàn giao dịch uy tín", "Sàn uy tín", "So sánh sàn giao dịch – TradingBonusHub"),
    ("/gioi-thieu/cach-danh-gia", "Về TradingBonusHub", "Giới thiệu", "Cách chúng tôi đánh giá – TradingBonusHub"),
    ("/gioi-thieu/affiliate", "Về TradingBonusHub", "Giới thiệu", "Công bố affiliate – TradingBonusHub"),
    ("/lien-he", "Về TradingBonusHub", "Giới thiệu", "Liên hệ – TradingBonusHub"),
])
def test_section_header_and_own_seo(client, url, head, crumb, seo):
    c = client.get(url).context
    assert c["page"]["title"] == head and c["meta"]["title"] == seo
    assert [x["label"] for x in c["crumbs"]] == ["Trang chủ", crumb]


def test_page_meta_fields_still_win(admin, client):
    admin.post("/admin/pages/compare", {"title": "So sánh", "meta_title": "SEO so sánh", "meta_desc": "Mô tả riêng"})
    c = client.get("/san/so-sanh").context
    assert c["meta"]["title"] == "SEO so sánh" and c["meta"]["description"] == "Mô tả riêng"
    assert c["page"]["title"] == "Sàn giao dịch uy tín"


def test_menu_label_home_and_subpage(client):
    label = lambda url: next(m["label"] for m in client.get(url).context["site"]["menu"] if m["url"] == "/san")  # noqa: E731
    assert label("/") == "Sàn" and label("/bonus") == "Sàn uy tín"
    assert label("/") == "Sàn"  # không ghi đè vào dữ liệu dùng chung


def test_contact_highlights_about_in_menu(client):
    c = client.get("/lien-he").context
    assert c["nav_path"] == "/gioi-thieu" and c["current_path"] == "/lien-he"
    assert client.get("/bonus").context["nav_path"] == "/bonus"


# ---------- thứ tự ----------

def test_brokers_in_input_order(client, db):
    make_broker(db, "Zeta")
    make_broker(db, "alpha", featured=True)
    make_broker(db, "Beta")
    assert titles(client.get("/san").context["brokers"], "name") == ["Zeta", "alpha", "Beta"]


@pytest.mark.parametrize("featured,expected", [("A", ["B", "A", "C"]), ("B", ["A", "B", "C"]), ("C", ["A", "C", "B"])])
def test_home_compare_featured_in_middle(client, db, featured, expected):
    for n in "ABC":
        make_broker(db, n, in_compare=True, featured=n == featured, slug=n.lower())
    assert titles(client.get("/").context["compare_brokers"], "name") == expected


def test_home_compare_without_three_keeps_order(client, db):
    make_broker(db, "A", in_compare=True, slug="a")
    make_broker(db, "B", in_compare=True, featured=True, slug="b")
    assert titles(client.get("/").context["compare_brokers"], "name") == ["A", "B"]


def test_compare_columns_follow_list_order(client, db):
    a, b = make_broker(db, "A", slug="a"), make_broker(db, "B", slug="b")
    assert titles(client.get(f"/san/so-sanh?ids={b.id},{a.id}").context["compare_brokers"], "name") == ["A", "B"]


def test_broker_detail_bonuses_in_input_order(client, db):
    k = make_broker(db)
    make_bonus(db, k, "Đầu", value_num=1)
    make_bonus(db, k, "Sau", value_num=99)
    assert titles(client.get(f"/san/{k.slug}?tab=bonus").context["bonuses"]) == ["Đầu", "Sau"]


# ---------- tin tức ----------

def _post(db, slug, category="Kiến thức", **kw):
    p = Post(slug=slug, title=slug, category=category, status="published", read_minutes=6, **kw)
    db.add(p)
    db.commit()
    return p


def test_post_list_shows_everything(client, db):
    for i in range(14):
        _post(db, f"bai-{i}")
    c = client.get("/tin-tuc").context
    assert len(c["posts"]) == 14 and "pagination" not in c


def test_post_detail_head_and_meta(client, db):
    _post(db, "bai", excerpt="Tóm tắt riêng")
    _post(db, "bai-khac")
    c = client.get("/tin-tuc/bai").context
    assert c["page"]["desc"] == "Kiến thức · 6 phút đọc" and c["meta"]["description"] == "Tóm tắt riêng"
    assert "related_posts" not in c


def test_back_to_list_keeps_category(client, db):
    _post(db, "bai")
    url = client.get("/tin-tuc?cat=Kiến thức").context["posts"][0]["url"]
    assert client.get(url).context["back_url"] == "/tin-tuc?cat=Ki%E1%BA%BFn+th%E1%BB%A9c"
    assert client.get("/tin-tuc").context["posts"][0]["url"] == "/tin-tuc/bai"
    assert client.get("/tin-tuc/bai").context["back_url"] == "/tin-tuc"
    assert client.get("/tin-tuc/bai?cat=<script>").context["back_url"] == "/tin-tuc"
    assert client.get(url).context["meta"]["canonical"] == "http://testserver/tin-tuc/bai"


# ---------- định dạng ----------

def test_formats():
    assert expiry_label(date(2026, 12, 31)) == "31/12" and expiry_label(None) == "Liên tục"
    assert ctr(312, 18420) == "1.7%" and ctr(0, 0) == "—"
    assert login_day(None) == "" and login_day(datetime(2026, 1, 1, 12)) == "01/01/2026"


def test_login_day_today():
    now = datetime.utcnow()
    assert login_day(now) == "Hôm nay"


@pytest.mark.parametrize("text,start,end", [
    ("", None, None),
    ("01/11 – 30/11", date(2026, 11, 1), date(2026, 11, 30)),
    ("01/11-30/11", date(2026, 11, 1), date(2026, 11, 30)),
    ("01/12 – 31/01", date(2026, 12, 1), date(2027, 1, 31)),
    ("01/12/2025 – 31/01", date(2025, 12, 1), date(2026, 1, 31)),
    ("01/11 –", date(2026, 11, 1), None),
    ("– 30/11", None, date(2026, 11, 30)),
])
def test_date_range_parse(text, start, end):
    assert parse_date_range(text, date(2026, 11, 5)) == (start, end)


@pytest.mark.parametrize("text", ["abc", "32/01 – 02/02", "01/11 – 02/02 – 03/03", "01/12/2026 – 01/01/2026"])
def test_date_range_rejects(text):
    with pytest.raises(ValueError):
        parse_date_range(text, date(2026, 11, 5))


@pytest.mark.parametrize("start,end", [(date(2026, 11, 1), date(2026, 11, 30)), (date(2025, 12, 1), date(2026, 1, 31)),
                                       (date(2026, 12, 1), date(2027, 1, 31)), (None, date(2027, 1, 1)), (None, None)])
def test_date_range_label_round_trip(start, end):
    today = date(2026, 11, 5)
    assert parse_date_range(date_range_label(start, end, today), today) == (start, end)


# ---------- đăng ký khi không có SMTP thật ----------

def _subscribe(client, **data):
    return client.post("/api/subscribe", data={"email": "ban@example.test", "next": "/"} | data, follow_redirects=False)


def _set_flash(r) -> str:
    """Production đặt cookie Secure nên TestClient http không gửi lại: đọc thẳng từ phản hồi."""
    return r.headers["set-cookie"].split(";")[0].split("=", 1)[1]


@pytest.fixture
def prod_console(monkeypatch):
    monkeypatch.setattr(config, "is_production", True)
    monkeypatch.setattr(config, "smtp_backend", "console")


def test_subscribe_production_console_fails_and_saves_nothing(client, db, prod_console):
    r = _subscribe(client)
    assert r.status_code == 303 and r.headers["location"] == "/#lien-he"
    assert _set_flash(r) == "sub_failed"
    assert db.query(Subscriber).count() == 0 and mailer.outbox == []


def test_subscribe_production_console_existing_address_untouched(client, db, prod_console):
    db.add(Subscriber(email="ban@example.test", status="confirmed", token="t"))
    db.commit()
    assert _set_flash(_subscribe(client)) == "sub_failed" and mailer.outbox == []


def test_subscribe_production_console_keeps_guards(client, db, prod_console):
    assert _set_flash(_subscribe(client, email="sai")) == "sub_invalid"
    assert _set_flash(_subscribe(client, website="bot")) == "sub_ok"  # honeypot vẫn giả vờ thành công


def test_subscribe_production_smtp_still_sends(client, db, monkeypatch):
    monkeypatch.setattr(config, "is_production", True)
    monkeypatch.setattr(config, "smtp_backend", "smtp")
    sent = []
    monkeypatch.setattr("app.routes.public.send_email", lambda *a, **k: sent.append(a) or True)
    assert _set_flash(_subscribe(client)) == "sub_ok" and len(sent) == 1
    assert db.query(Subscriber).count() == 1


def test_subscribe_dev_console_still_works(client, db):
    _subscribe(client)
    assert client.get("/").context["flash"]["code"] == "sub_ok" and len(mailer.outbox) == 1


# ---------- admin ----------

def test_nav_is_flat_in_design_order(admin):
    nav = admin.get("/admin").context["nav"]
    assert len(nav) == 1 and nav[0]["label"] is None
    assert [i["label"] for i in nav[0]["links"]] == [
        "Tổng quan", "Bonus", "Sàn", "Quảng cáo", "Nội dung trang chủ", "Bài viết", "Người đăng ký", "Cài đặt",
        "Trang", "Thư viện ảnh", "Tin nhắn"]


def test_nav_counts_every_subscriber(admin, db):
    db.add_all([Subscriber(email="a@example.test", status="pending", token="a"),
                Subscriber(email="b@example.test", status="confirmed", token="b")])
    db.commit()
    links = {i["id"]: i for i in admin.get("/admin").context["nav"][0]["links"]}
    assert links["subscribers"]["count"] == 2


def test_overview_has_four_stats_only(admin):
    c = admin.get("/admin").context
    assert [s["label"] for s in c["stats"]] == ["Bonus đang hiển thị", "Banner đang chạy", "Click quảng cáo (tháng)", "Người đăng ký"]
    assert not {"click_days", "click_total", "top_brokers", "unread_messages"} & set(c.keys())


def test_overview_thousand_separator(admin, db):
    from app.models import ClickLog
    db.add(ClickLog(kind="ad", ref_id=1, day=today_vn(), count=4215))
    db.commit()
    stats = {s["id"]: s["value"] for s in admin.get("/admin").context["stats"]}
    assert stats["ad_clicks"] == "4.215"


def test_overview_banner_broker_name(admin, db):
    k = make_broker(db)
    db.add(Banner(name="B", placement="after-bonus", broker_id=k.id, target_url="https://example.com/1"))
    db.commit()
    assert admin.get("/admin").context["banners"][0]["broker"] == k.name


def test_expiring_threshold_60_days(admin, db):
    k = make_broker(db)
    today = today_vn()
    make_bonus(db, k, "Biên", expiry_date=today + timedelta(days=60))
    make_bonus(db, k, "Quá", expiry_date=today + timedelta(days=61))
    assert titles(admin.get("/admin").context["expiring"]) == ["Biên"]
    assert titles(admin.get("/admin/bonus?tab=exp").context["bonuses"]) == ["Biên"]


def test_expiring_card_limited_to_four(admin, db):
    k = make_broker(db)
    for i in range(6):
        make_bonus(db, k, f"B{i}", expiry_date=today_vn() + timedelta(days=i + 1))
    assert len(admin.get("/admin").context["expiring"]) == 4


def test_bonus_subtabs_keep_filter(admin):
    tabs = admin.get("/admin/bonus?tab=on&type=cashback&q=abc").context["subtabs"]
    assert tabs[2]["url"] == "/admin/bonus?tab=off&type=cashback&q=abc"


def test_drawer_keeps_list_filter(admin, db):
    k = make_broker(db)
    b = make_bonus(db, k, type="cashback", is_active=False)
    c = admin.get("/admin/bonus?tab=off&type=cashback").context
    edit = c["bonuses"][0]["edit_url"]
    assert edit == f"/admin/bonus/{b.id}/edit?tab=off&type=cashback"
    assert c["add_url"] == "/admin/bonus/new?tab=off&type=cashback"
    d = admin.get(edit).context
    assert d["current_tab"] == "off" and d["drawer"]["close_url"] == "/admin/bonus?tab=off&type=cashback"
    assert d["drawer"]["action"] == edit
    r = admin.post(edit, {"broker_id": k.id, "type": "cashback", "title": "Mới"})
    assert r.status_code == 303 and r.headers["location"] == "/admin/bonus?tab=off&type=cashback"
    r = admin.post(edit, {"broker_id": k.id, "type": "cashback", "title": ""})
    assert r.status_code == 400 and r.context["current_tab"] == "off" and r.context["current_type"] == "cashback"


def test_admin_broker_order_is_input_order(admin, db):
    make_broker(db, "Zeta")
    make_broker(db, "Alpha", featured=True)
    assert titles(admin.get("/admin/brokers").context["brokers"], "name") == ["Zeta", "Alpha"]


def test_admin_posts_draft_last(admin, db):
    db.add_all([Post(slug="nhap", title="Nháp", category="Kiến thức", status="draft"),
                Post(slug="dang", title="Đăng", category="Kiến thức", status="published", published_at=datetime(2026, 1, 1))])
    db.commit()
    assert titles(admin.get("/admin/posts").context["posts"]) == ["Đăng", "Nháp"]


def test_mail_defaults_to_deposit(admin, db):
    c = admin.get("/admin/subscribers?tab=mail").context
    assert c["mail_form"]["audience"] == ["deposit"]
    assert [o["id"] for o in c["audience_options"] if o["selected"]] == ["deposit"]


def test_bulk_links(admin, db):
    a, b = make_broker(db, "A", slug="a"), make_broker(db, "B", slug="b")
    r = admin.post("/admin/brokers/links", {f"url_{a.id}": "https://a.example/x", f"url_{b.id}": ""})
    assert r.status_code == 303 and r.headers["location"] == "/admin/brokers?tab=links"
    db.expire_all()
    assert db.get(Broker, a.id).affiliate_url == "https://a.example/x" and db.get(Broker, b.id).affiliate_url == ""


def test_bulk_links_all_or_nothing(admin, db, client):
    a, b = make_broker(db, "A", slug="a"), make_broker(db, "B", slug="b")
    admin.post("/admin/brokers/links", {f"url_{a.id}": "https://moi.example/", f"url_{b.id}": "javascript:alert(1)"})
    db.expire_all()
    assert db.get(Broker, a.id).affiliate_url == "https://example.com/aff"
    assert admin.get("/admin/brokers?tab=links").context["flash"]["code"] == "invalid_url"


def test_bulk_ads(admin, db):
    b = Banner(name="B", placement="after-bonus", target_url="https://example.com/1")
    db.add(b)
    db.commit()
    assert admin.get("/admin/ads").context["ads_action"] == "/admin/ads/bulk"
    r = admin.post("/admin/ads/bulk", {f"placement_{b.id}": "before-blog", f"target_url_{b.id}": "https://example.com/2",
                                       f"dates_{b.id}": "01/11/2026 – 30/11/2026"})
    assert r.status_code == 303
    db.expire_all()
    row = db.get(Banner, b.id)
    assert (row.placement, row.target_url) == ("before-blog", "https://example.com/2")
    assert (row.start_date, row.end_date) == (date(2026, 11, 1), date(2026, 11, 30))
    assert admin.get("/admin/ads").context["banners"][0]["dates"]


@pytest.mark.parametrize("field,value,code", [("target_url", "javascript:alert(1)", "invalid_url"), ("target_url", "", "invalid_url"),
                                              ("dates", "abc", "invalid_dates")])
def test_bulk_ads_all_or_nothing(admin, db, field, value, code):
    good = Banner(name="A", placement="after-bonus", target_url="https://example.com/a")
    bad = Banner(name="B", placement="after-bonus", target_url="https://example.com/b")
    db.add_all([good, bad])
    db.commit()
    data = {f"placement_{x.id}": "before-blog" for x in (good, bad)} | {f"target_url_{x.id}": x.target_url for x in (good, bad)}
    admin.post("/admin/ads/bulk", data | {f"{field}_{bad.id}": value})
    db.expire_all()
    assert db.get(Banner, good.id).placement == "after-bonus"
    assert admin.get("/admin/ads").context["flash"]["code"] == code


def test_settings_tabs_and_brand(admin, db):
    assert [t["id"] for t in admin.get("/admin/settings").context["subtabs"]] == [
        "general", "seo", "users", "brand", "social", "tracking"]
    admin.post("/admin/settings/brand", {"partner_email": "doi.tac@example.test", "logo_path": "/static/img/logo.png",
                                         "favicon_path": "/static/img/logo.png"})
    admin.post("/admin/settings/general", {"site_name": "Tên mới"})
    s = content.get_all(db)
    assert s["partner_email"] == "doi.tac@example.test" and s["branding"]["logo_path"] == "/static/img/logo.png"
    assert s["site_name"] == "Tên mới"


def test_bonus_row_keeps_required_license(admin, db):
    r = admin.post("/admin/brokers/new", {"name": "Sàn", "kind": "forex", "is_active": "1"})
    assert r.status_code == 400 and db.query(Broker).count() == 0
    assert db.query(Bonus).count() == 0


# ---------- gửi email ở production khi không có SMTP thật ----------

def _confirmed(db):
    db.add(Subscriber(email="nhan@example.test", status="confirmed", token="t-nhan"))
    db.commit()


MAIL = {"subject": "Bonus mới", "body": "Nội dung đang soạn", "audience": ["deposit"]}


def test_campaign_production_console_fails_and_stays_draft(admin, db, prod_console):
    _confirmed(db)
    r = admin.post("/admin/subscribers/mail", MAIL | {"action": "send"})
    c = db.query(Campaign).one()
    assert r.status_code == 303 and r.headers["location"] == f"/admin/subscribers?tab=mail&draft={c.id}"
    assert _set_flash(r) == "send_failed" and mailer.outbox == []
    assert (c.status, c.sent_count, c.sent_at, c.subject, c.body) == ("draft", 0, None, "Bonus mới", "Nội dung đang soạn")
    form = admin.get(r.headers["location"]).context["mail_form"]
    assert form["subject"] == "Bonus mới" and form["body"] == "Nội dung đang soạn" and form["draft_id"] == c.id


def test_campaign_production_console_keeps_partial_progress(admin, db, prod_console):
    _confirmed(db)
    c = Campaign(subject="S", body="B", audience=[], status="partial", sent_to=["cu@example.test"], sent_count=1)
    db.add(c)
    db.commit()
    r = admin.post("/admin/subscribers/mail", {"subject": "S", "body": "B", "draft_id": c.id, "action": "send"})
    assert _set_flash(r) == "send_failed" and mailer.outbox == []
    db.expire_all()
    assert (c.status, c.sent_count) == ("partial", 1)


def test_draft_still_saves_production_console(admin, db, prod_console):
    r = admin.post("/admin/subscribers/mail", MAIL | {"action": "draft"})
    assert r.status_code == 303 and db.query(Campaign).one().status == "draft"
    assert "send_failed" not in r.headers.get("set-cookie", "")


def test_test_mail_production_console_fails(admin, db, prod_console):
    r = admin.post("/admin/subscribers/mail/test", MAIL)
    assert r.status_code == 502 and r.context["flash"]["code"] == "test_failed" and mailer.outbox == []
    assert r.context["mail_form"]["body"] == "Nội dung đang soạn" and db.query(Campaign).count() == 0


def test_campaign_dev_console_still_sends(admin, db):
    _confirmed(db)
    r = admin.post("/admin/subscribers/mail", MAIL | {"action": "send"})
    assert r.headers["location"] == "/admin/subscribers?tab=mail" and len(mailer.outbox) == 1
    assert db.query(Campaign).one().status == "sent"
