"""Trường chữ tự do theo thiết kế (K16, K18, K24, K25) và link pháp lý ở chân trang."""
from datetime import timedelta

from conftest import make_broker
from app import content
from app.models import Banner, Bonus
from app.utils import today_vn


def add_bonus(db, broker, title="Bonus", amount="$50", value=50, **kw):
    b = Bonus(broker_id=broker.id, type="deposit", title=title, amount=amount, value_num=value, **kw)
    db.add(b)
    db.commit()
    return b


def add_rail(db, broker, placement="rail-left", **kw):
    b = Banner(name="Rail", placement=placement, broker_id=broker.id, target_url="https://example.test/x", **kw)
    db.add(b)
    db.commit()
    return b


def home(client):
    return client.get("/").text


def test_hero_card_uses_chosen_bonus(client, admin, db):
    featured = make_broker(db, "Sàn nổi bật", featured=True)
    add_bonus(db, featured, "Bonus tự động", value=100)
    other = make_broker(db, "Sàn khác")
    pick = add_bonus(db, other, "Bonus được chọn", value=1)
    assert "Bonus tự động" in client.get("/").context["hero_bonus"]["title"]
    assert admin.post("/admin/home/hero_extra", data={"card_bonus_id": str(pick.id)}).status_code == 303
    assert client.get("/").context["hero_bonus"]["title"] == "Bonus được chọn"
    assert 'selected' in admin.get("/admin/home?tab=hero_extra").text


def test_hero_card_without_featured_broker(client, admin, db):
    pick = add_bonus(db, make_broker(db, "Sàn thường"), "Bonus chọn tay")
    assert client.get("/").context["hero_bonus"] is None
    admin.post("/admin/home/hero_extra", data={"card_bonus_id": str(pick.id)})
    assert client.get("/").context["hero_bonus"]["title"] == "Bonus chọn tay"


def test_hero_card_falls_back_when_pick_not_visible(client, admin, db):
    featured = make_broker(db, "Sàn nổi bật", featured=True)
    add_bonus(db, featured, "Bonus tự động")
    other = make_broker(db, "Sàn khác")
    pick = add_bonus(db, other, "Bonus được chọn")
    admin.post("/admin/home/hero_extra", data={"card_bonus_id": str(pick.id)})

    pick.expiry_date = today_vn() - timedelta(days=1)
    db.commit()
    assert client.get("/").context["hero_bonus"]["title"] == "Bonus tự động"

    pick.expiry_date = None
    other.is_active = False
    db.commit()
    assert client.get("/").context["hero_bonus"]["title"] == "Bonus tự động"

    db.delete(pick)
    db.commit()
    assert client.get("/").context["hero_bonus"]["title"] == "Bonus tự động"


def test_hero_extra_rejects_unknown_bonus_and_clear_returns_to_auto(admin, db):
    assert admin.post("/admin/home/hero_extra", data={"card_bonus_id": "999"}).status_code == 400
    assert admin.post("/admin/home/hero_extra", data={"card_bonus_id": "abc"}).status_code == 400
    pick = add_bonus(db, make_broker(db), "B")
    admin.post("/admin/home/hero_extra", data={"card_bonus_id": str(pick.id)})
    assert content.get(db, "hero")["card_bonus_id"] == pick.id
    admin.post("/admin/home/hero_extra", data={"card_label": "Nhãn"})  # form không có ô: giữ nguyên
    assert content.get(db, "hero")["card_bonus_id"] == pick.id
    admin.post("/admin/home/hero_extra", data={"card_bonus_id": ""})
    db.expire_all()
    assert content.get(db, "hero")["card_bonus_id"] is None


def test_featured_bonus_line_free_text_and_fallback(client, db):
    k = make_broker(db, "Sàn So Sánh", in_compare=True)
    add_bonus(db, k, amount="$50")
    assert "$50</dd>" in home(client)
    k.featured_bonus_text = "Deposit 50%"
    db.commit()
    html = home(client)
    assert "<dd>Deposit 50%</dd>" in html and "$50</dd>" not in html


def test_featured_bonus_line_shows_without_bonus(client, db):
    make_broker(db, "Sàn So Sánh", in_compare=True, featured_bonus_text="Cashback")
    assert "<dd>Cashback</dd>" in home(client)


def test_rail_free_text_left(client, db):
    k = make_broker(db, "Sàn Rail", license="FSA")
    add_bonus(db, k, "Tiêu đề bonus", amount="$4/lot", min_deposit="$10")
    add_rail(db, k, rail_amount="$4", rail_note="mỗi lot", rail_desc="Hoàn phí giao dịch", rail_line="Rút trong ngày")
    html = home(client)
    assert 'class="rail__amount">$4</div>' in html  # số ngắn giữ cỡ lớn, không dùng --long
    assert '<div class="rail__sub">mỗi lot</div>' in html
    assert "Hoàn phí giao dịch" in html and "Tiêu đề bonus" not in html.split("rail--left")[1].split("</aside>")[0]
    assert "<li>Rút trong ngày</li>" in html and "<li>Nạp từ $10</li>" in html and "<li>FSA</li>" in html


def test_rail_right_cta_uses_override_amount(client, db):
    k = make_broker(db, "Sàn Rail")
    add_bonus(db, k, amount="$50")
    add_rail(db, k, "rail-right", rail_amount="$99")
    assert "Nhận $99" in home(client) and "Nhận $50" not in home(client)


def test_rail_empty_fields_keep_existing_output(client, db):
    k = make_broker(db, "Sàn Rail")
    add_bonus(db, k, "Tiêu đề bonus", amount="$50")
    add_rail(db, k, "rail-right")
    html = home(client)
    rail = html.split("rail--right")[1].split("</aside>")[0]
    assert "Tiêu đề bonus" in rail and "Nhận $50" in rail and "rail__sub" not in rail


def test_rail_without_bonus_or_text_has_no_empty_facts(client, db):
    add_rail(db, make_broker(db, "Sàn Rail"))
    rail = home(client).split("rail--left")[1].split("</aside>")[0]
    assert "rail__facts" not in rail and "Mở tài khoản" in rail


def test_rail_without_bonus_can_use_line(client, db):
    add_rail(db, make_broker(db, "Sàn Rail"), rail_line="Rút trong ngày")
    assert "<li>Rút trong ngày</li>" in home(client)


def test_admin_saves_rail_and_featured_fields(admin, db):
    k = make_broker(db, "Sàn Rail", affiliate_url="https://example.test/a")
    data = {"name": "Rail", "broker_id": str(k.id), "placement": "rail-left", "is_active": "on",
            "rail_amount": "$4", "rail_note": "mỗi lot", "rail_desc": "Mô tả", "rail_line": "Rút trong ngày"}
    assert admin.post("/admin/ads/new", data=data).status_code == 303
    b = db.query(Banner).one()
    assert (b.rail_amount, b.rail_note, b.rail_desc, b.rail_line) == ("$4", "mỗi lot", "Mô tả", "Rút trong ngày")
    assert 'value="mỗi lot"' in admin.get(f"/admin/ads/{b.id}/edit").text
    assert admin.post("/admin/ads/new", data=data | {"rail_amount": "x" * 21}).status_code == 400


def test_admin_saves_broker_featured_text(admin, db):
    data = {"name": "Sàn Mới", "kind": "forex", "license": "FSA", "is_active": "on", "featured_bonus_text": "Deposit 50%"}
    assert admin.post("/admin/brokers/new", data=data).status_code == 303
    assert admin.post("/admin/brokers/new", data=data | {"name": "Sàn Khác", "featured_bonus_text": "x" * 61}).status_code == 400


def test_legal_links_on_full_and_compact_footer(client):
    for url in ("/", "/bonus"):
        html = client.get(url).text
        assert 'href="/dieu-khoan">Điều khoản</a>' in html and 'href="/bao-mat">Bảo mật</a>' in html


def test_legal_links_default_applies_to_saved_footer(client, db):
    """Site thật đã lưu khóa footer trước khi có legal_links: link vẫn phải hiện."""
    saved = content.get(db, "footer")
    saved.pop("legal_links")
    content.put(db, "footer", saved)
    db.commit()
    assert 'href="/bao-mat"' in client.get("/").text


def test_admin_edits_legal_links(client, admin, db):
    r = admin.post("/admin/home/footer", data={"legal_links": "Chính sách | /bao-mat\n\nLuật | https://example.test/l"})
    assert r.status_code == 303
    db.expire_all()
    assert content.get(db, "footer")["legal_links"] == [{"label": "Chính sách", "url": "/bao-mat"},
                                                       {"label": "Luật", "url": "https://example.test/l"}]
    assert "Chính sách | /bao-mat" in admin.get("/admin/home?tab=footer").text
    assert 'href="/dieu-khoan">Điều khoản</a>' not in client.get("/").text


def test_admin_rejects_bad_legal_link_and_empty_hides(client, admin, db):
    r = admin.post("/admin/home/footer", data={"legal_links": "Xấu | javascript:alert(1)"})
    assert r.status_code == 400 and "javascript:alert(1)" in r.text
    admin.post("/admin/home/footer", data={"legal_links": ""})
    assert "site-footer__legal-links" not in client.get("/").text


def test_menu_tab_keeps_legal_links(admin, db):
    admin.post("/admin/home/footer", data={"legal_links": "A | /bao-mat"})
    admin.post("/admin/home/menu", data={"menu_label": "Bonus", "menu_url": "/bonus"})
    db.expire_all()
    assert content.get(db, "footer")["legal_links"] == [{"label": "A", "url": "/bao-mat"}]
