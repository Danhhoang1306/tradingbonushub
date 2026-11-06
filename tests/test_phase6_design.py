"""Phase 6: trả về đúng thiết kế (brief mục 13)."""
from datetime import date, datetime, timedelta

import pytest
from conftest import make_bonus, make_broker, titles

from app import content, mailer
from app.config import config
from app.models import Banner, Bonus, Broker, Campaign, MediaFile, Post, Subscriber
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


def test_bulk_links_saves_valid_rows_and_names_bad_one(admin, db):
    a, b = make_broker(db, "A", slug="a"), make_broker(db, "B", slug="b")
    r = admin.post("/admin/brokers/links", {f"url_{a.id}": "https://moi.example/", f"url_{b.id}": "javascript:alert(1)"})
    assert r.status_code == 400 and r.context["current_tab"] == "links"
    flash = r.context["flash"]
    assert flash["code"] == "bulk_errors" and "B" in flash["text"].split(".")[0] and "A" not in flash["text"].split(".")[0].replace("Chưa lưu", "")
    rows = {k["id"]: k for k in r.context["brokers"]}
    assert rows[b.id]["affiliate_url"] == "javascript:alert(1)" and "affiliate_url" in rows[b.id]["errors"]
    assert rows[a.id]["affiliate_url"] == "https://moi.example/" and rows[a.id]["errors"] == {}
    db.expire_all()
    assert db.get(Broker, a.id).affiliate_url == "https://moi.example/"
    assert db.get(Broker, b.id).affiliate_url == "https://example.com/aff"


def test_bulk_links_unchanged_bad_stored_value_does_not_block(admin, db):
    a = make_broker(db, "A", slug="a", affiliate_url="khong-phai-link")
    b = make_broker(db, "B", slug="b")
    r = admin.post("/admin/brokers/links", {f"url_{a.id}": "khong-phai-link", f"url_{b.id}": "https://moi.example/"})
    assert r.status_code == 303
    db.expire_all()
    assert db.get(Broker, b.id).affiliate_url == "https://moi.example/"


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


@pytest.mark.parametrize("field,value", [("target_url", "javascript:alert(1)"), ("target_url", ""), ("dates", "abc")])
def test_bulk_ads_saves_valid_rows_and_keeps_typed_text(admin, db, field, value):
    good = Banner(name="A", placement="after-bonus", target_url="https://example.com/a")
    bad = Banner(name="B", placement="after-bonus", target_url="https://example.com/b")
    db.add_all([good, bad])
    db.commit()
    data = {f"placement_{x.id}": "before-blog" for x in (good, bad)} | {f"target_url_{x.id}": x.target_url for x in (good, bad)}
    r = admin.post("/admin/ads/bulk", data | {f"{field}_{bad.id}": value})
    assert r.status_code == 400 and r.context["flash"]["code"] == "bulk_errors" and "B · " in r.context["flash"]["text"]
    rows = {b["id"]: b for b in r.context["banners"]}
    assert rows[bad.id][field] == value and field in rows[bad.id]["errors"] and rows[bad.id]["placement"] == "before-blog"
    assert rows[good.id]["errors"] == {}
    db.expire_all()
    assert db.get(Banner, good.id).placement == "before-blog"
    assert db.get(Banner, bad.id).placement == "after-bonus"  # thẻ lỗi không lưu phần nào


def test_bulk_ads_banner_without_link_does_not_block_others(admin, db):
    k = make_broker(db, affiliate_url="")
    dead = Banner(name="Chết", placement="after-bonus", broker_id=k.id, target_url="")
    live = Banner(name="Sống", placement="after-bonus", target_url="https://example.com/a")
    db.add_all([dead, live])
    db.commit()
    r = admin.post("/admin/ads/bulk", {f"placement_{dead.id}": "after-bonus", f"target_url_{dead.id}": "", f"dates_{dead.id}": "",
                                       f"placement_{live.id}": "before-blog", f"target_url_{live.id}": live.target_url,
                                       f"dates_{live.id}": ""})
    assert r.status_code == 303
    db.expire_all()
    assert db.get(Banner, live.id).placement == "before-blog"


def test_bulk_ads_missing_field_keeps_value(admin, db):
    b = Banner(name="B", placement="after-bonus", target_url="https://example.com/a", start_date=date(2026, 1, 1))
    db.add(b)
    db.commit()
    assert admin.post("/admin/ads/bulk", {f"placement_{b.id}": "before-blog"}).status_code == 303
    db.expire_all()
    row = db.get(Banner, b.id)
    assert (row.placement, row.target_url, row.start_date) == ("before-blog", "https://example.com/a", date(2026, 1, 1))


def _dates_of_years():
    """Mọi tổ hợp năm quanh năm nay, gồm cả ngày đến có ngày/tháng nhỏ hơn, bằng, lớn hơn ngày từ, và 29/02."""
    days = [(1, 1), (5, 11), (30, 11), (31, 12)]
    out = []
    for y1 in (2024, 2025, 2026, 2027, 2028):
        for y2 in (2024, 2025, 2026, 2027, 2028):
            for d1 in days:
                for d2 in days:
                    s, e = date(y1, d1[1], d1[0]), date(y2, d2[1], d2[0])
                    if s <= e:
                        out.append((s, e))
    out += [(date(y, 11, 1), None) for y in (2025, 2026, 2027)] + [(None, date(y, 11, 30)) for y in (2025, 2026, 2027)]
    out += [(date(2027, 12, 1), date(2028, 2, 29)), (date(2028, 2, 29), date(2028, 3, 1)), (date(2024, 2, 29), date(2028, 2, 29))]
    return out


@pytest.mark.parametrize("today", [date(2026, 11, 5), date(2026, 1, 1), date(2026, 12, 31), date(2027, 3, 1), date(2028, 2, 29)])
def test_date_range_round_trip_every_year_shape(today):
    for start, end in _dates_of_years():
        label = date_range_label(start, end, today)
        assert parse_date_range(label, today) == (start, end), label


def test_date_range_label_keeps_design_short_form():
    today = date(2026, 11, 5)
    assert date_range_label(date(2026, 11, 1), date(2026, 11, 30), today) == "01/11 – 30/11"
    assert date_range_label(date(2026, 12, 1), date(2027, 1, 31), today) == "01/12 – 31/01"
    assert date_range_label(date(2025, 1, 1), date(2026, 11, 30), today) == "01/01/2025 – 30/11/2026"


def test_v3_1_publish_without_change_keeps_multi_year_banner(admin, db):
    y = today_vn().year
    b = Banner(name="B", placement="after-bonus", target_url="https://example.com/a",
               start_date=date(y - 1, 1, 1), end_date=date(y, 11, 30))
    db.add(b)
    db.commit()
    row = admin.get("/admin/ads").context["banners"][0]
    r = admin.post("/admin/ads/bulk", {f"placement_{b.id}": row["placement"], f"target_url_{b.id}": row["target_url"],
                                       f"dates_{b.id}": row["dates"]})
    assert r.status_code == 303
    db.expire_all()
    assert (db.get(Banner, b.id).start_date, db.get(Banner, b.id).end_date) == (date(y - 1, 1, 1), date(y, 11, 30))


def test_bulk_ads_impossible_stored_range_unchanged_is_kept(admin, db):
    b = Banner(name="B", placement="after-bonus", target_url="https://example.com/a",
               start_date=date(2026, 12, 1), end_date=date(2026, 1, 1))
    db.add(b)
    db.commit()
    dates = admin.get("/admin/ads").context["banners"][0]["dates"]
    assert admin.post("/admin/ads/bulk", {f"placement_{b.id}": "after-bonus", f"dates_{b.id}": dates}).status_code == 303
    db.expire_all()
    assert db.get(Banner, b.id).end_date == date(2026, 1, 1)


# ---------- brief 13.1: ảnh, nháp, xuống dòng, tab bổ sung, số 0 ----------

def test_media_bulk_saves_alt(admin, db):
    m = MediaFile(path="/media/a.png")
    db.add(m)
    db.commit()
    assert admin.get("/admin/media?q=").context["media_action"] == "/admin/media/bulk"
    r = admin.post("/admin/media/bulk?q=abc", {f"alt_{m.id}": "Mô tả mới"})
    assert r.status_code == 303 and r.headers["location"] == "/admin/media?q=abc"
    db.expire_all()
    assert db.get(MediaFile, m.id).alt == "Mô tả mới"


def test_media_bulk_keeps_typed_text_on_error(admin, db):
    good, bad = MediaFile(path="/media/tot.png"), MediaFile(path="/media/hong.png")
    db.add_all([good, bad])
    db.commit()
    r = admin.post("/admin/media/bulk", {f"alt_{good.id}": "Được", f"alt_{bad.id}": "x" * 256})
    assert r.status_code == 400 and "hong.png" in r.context["flash"]["text"]
    rows = {m["id"]: m for m in r.context["media"]}
    assert rows[bad.id]["alt"] == "x" * 256 and "alt" in rows[bad.id]["errors"]
    db.expire_all()
    assert db.get(MediaFile, good.id).alt == "Được" and db.get(MediaFile, bad.id).alt == ""


def test_media_bulk_requires_csrf(client, admin, db):
    assert client.post("/admin/media/bulk", data={"csrf_token": "sai"}).status_code == 403


def test_empty_mail_publish_reports_error_and_keeps_audience(admin, db):
    r = admin.post("/admin/subscribers/mail", {"subject": "", "body": "", "audience": ["crypto"], "action": "draft"})
    assert r.status_code == 400 and db.query(Campaign).count() == 0
    assert r.context["mail_form"]["audience"] == ["crypto"] and "subject" in r.context["mail_form"]["errors"]


@pytest.mark.parametrize("tab,key", [("terms", "terms_md"), ("privacy", "privacy_md")])
def test_legal_publish_without_change_keeps_bytes(admin, db, tab, key):
    before = content.get(db, "legal")[key]
    shown = before.replace("\n", "\r\n")  # trình duyệt gửi CRLF
    assert admin.post(f"/admin/pages/{tab}", {"title": "T", "body_md": shown}).status_code == 303
    db.expire_all()
    assert content.get(db, "legal")[key] == before


def test_legal_edit_stored_with_lf(admin, db):
    admin.post("/admin/pages/terms", {"title": "T", "body_md": "## A\r\n\r\nB\r\n"})
    db.expire_all()
    assert content.get(db, "legal")["terms_md"] == "## A\n\nB"


def test_legal_old_crlf_stored_is_kept_when_unchanged(admin, db):
    legal = content.get(db, "legal")
    content.put(db, "legal", legal | {"terms_md": "## A\r\n\r\nB\r\n"})
    db.commit()
    admin.post("/admin/pages/terms", {"title": "T", "body_md": "## A\r\n\r\nB\r\n"})
    db.expire_all()
    assert content.get(db, "legal")["terms_md"] == "## A\r\n\r\nB\r\n"


def test_home_tabs_design_first(admin):
    ids = [t["id"] for t in admin.get("/admin/home").context["subtabs"]]
    assert ids[:3] == ["sections", "hero", "menu"] and {"hero_extra", "headings", "footer"} <= set(ids)


@pytest.mark.parametrize("tab", ["hero_extra", "headings", "footer"])
def test_new_home_tabs_render(admin, tab):
    assert admin.get(f"/admin/home?tab={tab}").status_code == 200


def test_hero_form_without_card_label_keeps_it(admin, db):
    admin.post("/admin/home/hero_extra", {"card_label": "Nhãn riêng"})
    before = content.get(db, "hero")
    admin.post("/admin/home/hero", {"eyebrow": "E", "headline": "H", "sub": "S", "cta": "C", "image_path": before["image_path"]})
    db.expire_all()
    hero = content.get(db, "hero")
    assert hero["card_label"] == "Nhãn riêng" and hero["headline"] == "H"


def test_hero_extra_does_not_touch_other_fields(admin, db):
    before = content.get(db, "hero")
    admin.post("/admin/home/hero_extra", {"card_label": "Nhãn riêng"})
    db.expire_all()
    assert content.get(db, "hero") == before | {"card_label": "Nhãn riêng"}


def test_menu_form_keeps_footer_fields(admin, db):
    before = content.get(db, "footer")
    r = admin.post("/admin/home/menu", {"menu_label": ["Bonus"], "menu_url": ["/bonus"], "risk_note": "Rủi ro mới"})
    assert r.status_code == 303
    db.expire_all()
    assert content.get(db, "footer") == before | {"risk_note": "Rủi ro mới"}
    assert content.get(db, "menu") == [{"label": "Bonus", "url": "/bonus"}]


def test_footer_form_keeps_menu_and_risk_note(admin, db):
    menu, note = content.get(db, "menu"), content.get(db, "footer")["risk_note"]
    r = admin.post("/admin/home/footer", {"about_text": "Mới", "copyright": "C", "footer_col_title": ["Cột"],
                                          "footer_col_links": ["Bonus | /bonus"]})
    assert r.status_code == 303
    db.expire_all()
    f = content.get(db, "footer")
    assert content.get(db, "menu") == menu and f["risk_note"] == note and f["about_text"] == "Mới"
    assert f["columns"] == [{"title": "Cột", "links": [{"label": "Bonus", "url": "/bonus"}]}]


def test_footer_tab_can_remove_all_columns(admin, db):
    assert admin.post("/admin/home/footer", {"about_text": "A"}).status_code == 303
    db.expire_all()
    assert content.get(db, "footer")["columns"] == []


def test_footer_tab_bad_link_is_400_and_keeps_rows(admin, db):
    r = admin.post("/admin/home/footer", {"footer_col_title": ["Cột"], "footer_col_links": ["X | javascript:alert(1)"]})
    assert r.status_code == 400 and r.context["form"]["data"]["columns"][0]["title"] == "Cột"


def test_sections_post_empty_keeps_headings(admin, db):
    admin.post("/admin/home/headings", {"bonus_eyebrow": "E", "bonus_title": "T", "compare_featured_label": "Nhãn"})
    assert content.get(db, "home_bonus")["title"] == "T"
    admin.post("/admin/home/sections", {})
    db.expire_all()
    assert content.get(db, "home_bonus")["title"] == "T" and content.get(db, "home_compare")["featured_label"] == "Nhãn"


def test_zero_counts_are_numbers_not_none(client, db):
    make_broker(db, "A", slug="a")
    bonus = {t["id"]: t["count"] for t in client.get("/bonus").context["tabs"]}
    assert all(v == 0 for v in bonus.values()) and client.get("/bonus").context["bonus_count"] == 0
    san = client.get("/san").context
    assert san["brokers"][0]["bonus_count"] == 0
    assert {t["id"]: t["count"] for t in san["tabs"]} == {"all": 1, "forex": 1, "crypto": 0, "compare": None}
    assert {t["id"]: t["count"] for t in client.get("/tin-tuc").context["tabs"]}["all"] == 0
    rows = client.get("/san/so-sanh?ids=" + str(san["brokers"][0]["id"])).context["compare_rows"]
    assert rows[-1]["label"] == "Bonus đang có" and rows[-1]["cells"] == [0]
    assert {t["id"]: t["count"] for t in client.get("/san/a").context["tabs"]}["bonus"] == 0


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


def test_templates_do_not_reload_from_disk_in_production():
    import subprocess
    import sys
    code = ("from app.templating import templates; import sys; "
            "sys.exit(0 if templates.env.auto_reload is False else 1)")
    env = {**__import__("os").environ, "APP_ENV": "production", "SECRET_KEY": "x" * 40}
    assert subprocess.run([sys.executable, "-c", code], env=env).returncode == 0
