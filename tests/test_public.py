from datetime import date

import pytest

from conftest import make_bonus, make_broker, titles

PUBLIC_PAGES = ["/", "/bonus", "/bonus?type=nodep", "/bonus?sort=value", "/bonus?sort=expiry", "/bonus?type=xxx",
                "/san", "/san?kind=forex", "/san?kind=crypto", "/san/so-sanh", "/san/so-sanh?ids=1,2,3",
                "/tin-tuc", "/tin-tuc?cat=Kiến thức", "/tin-tuc?page=99", "/gioi-thieu", "/gioi-thieu/cach-danh-gia",
                "/gioi-thieu/affiliate", "/lien-he", "/dieu-khoan", "/bao-mat", "/robots.txt", "/sitemap.xml", "/health"]


@pytest.mark.parametrize("url", PUBLIC_PAGES)
def test_empty_db_public_pages_ok(client, url):
    r = client.get(url)
    assert r.status_code == 200, url


@pytest.mark.parametrize("url", ["/san/khong-co", "/tin-tuc/khong-co", "/khong-ton-tai", "/go/broker/1", "/go/ad/1"])
def test_missing_pages_404(client, url):
    assert client.get(url, follow_redirects=False).status_code == 404


def test_empty_home_hides_data_sections(client):
    assert client.get("/").context["home_sections"] == ["hero", "about", "why", "types", "signup"]


def test_security_headers(client):
    r = client.get("/")
    csp = r.headers["content-security-policy"]
    assert "fonts.googleapis.com" in csp and "frame-ancestors 'none'" in csp
    assert r.headers["x-content-type-options"] == "nosniff"
    assert client.get("/admin/login").headers["x-robots-tag"].startswith("noindex")


def test_robots_and_sitemap(client, db):
    make_broker(db, "Sàn A")
    assert "Disallow: /admin" in client.get("/robots.txt").text
    xml = client.get("/sitemap.xml").text
    assert "<loc>http://testserver/san/san-a</loc>" in xml


def test_no_api_docs(client):
    for url in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(url).status_code == 404


def test_expired_bonus_leaves_public(client, db):
    k = make_broker(db)
    make_bonus(db, k, "Bonus còn hạn", expiry_date=date(2999, 1, 1))
    make_bonus(db, k, "Bonus liên tục", expiry_date=None)
    make_bonus(db, k, "Bonus hết hạn", expiry_date=date(2000, 1, 1))
    make_bonus(db, k, "Bonus đã ẩn", is_active=False)
    for url, key in (("/", "latest_bonuses"), ("/bonus", "bonuses"), (f"/san/{k.slug}", "bonuses")):
        assert sorted(titles(client.get(url).context[key])) == ["Bonus còn hạn", "Bonus liên tục"]
    from app.templating import expiry_label
    assert expiry_label(None) == "Liên tục"


def test_inactive_broker_hides_bonuses_and_page(client, db):
    k = make_broker(db, is_active=False)
    make_bonus(db, k, "Bonus của sàn ẩn")
    assert client.get("/bonus").context["bonuses"] == []
    assert client.get(f"/san/{k.slug}").status_code == 404
    assert client.get(f"/go/broker/{k.id}", follow_redirects=False).status_code == 404


def test_bonus_filter_and_sort(client, db):
    k = make_broker(db)
    make_bonus(db, k, "Nhỏ", value_num=10, type="cashback")
    make_bonus(db, k, "Lớn", value_num=1000, type="deposit")
    make_bonus(db, k, "Không giá trị", value_num=None, type="deposit")
    assert titles(client.get("/bonus?sort=value").context["bonuses"]) == ["Lớn", "Nhỏ", "Không giá trị"]
    assert titles(client.get("/bonus?type=cashback").context["bonuses"]) == ["Nhỏ"]
    tabs = {t["id"]: t["count"] for t in client.get("/bonus").context["tabs"]}
    assert tabs["all"] == 3 and tabs["deposit"] == 2 and tabs["nodep"] == 0


def test_compare_page_max_three(client, db):
    ids = [make_broker(db, f"Sàn {c}").id for c in "ABCD"]
    c = client.get("/san/so-sanh?ids=" + ",".join(map(str, ids))).context
    assert titles(c["compare_brokers"], "name") == ["Sàn A", "Sàn B", "Sàn C"]
    pick = {p["name"]: p for p in c["compare_pick"]}
    assert pick["Sàn D"]["url"] is None and not pick["Sàn D"]["selected"]  # đủ 3: không chọn thêm được
    assert pick["Sàn A"]["url"] == "/san/so-sanh?ids=" + ",".join(map(str, ids[1:3]))
    assert len(c["compare_rows"]) == 8 and all(len(row["cells"]) == 3 for row in c["compare_rows"])


def test_compare_defaults_to_in_compare_brokers(client, db):
    make_broker(db, "Sàn A", in_compare=True)
    make_broker(db, "Sàn B")
    assert titles(client.get("/san/so-sanh").context["compare_brokers"], "name") == ["Sàn A"]


def test_go_broker_redirect_counts_click(client, db):
    from app.models import Broker, ClickLog
    k = make_broker(db, affiliate_url="https://example.com/ref?x=1")
    r = client.get(f"/go/broker/{k.id}", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "https://example.com/ref?x=1"
    client.get(f"/go/broker/{k.id}", follow_redirects=False)
    db.expire_all()
    assert db.get(Broker, k.id).clicks == 2
    assert db.query(ClickLog).one().count == 2


def test_go_broker_without_link_404(client, db):
    k = make_broker(db, affiliate_url="")
    assert client.get(f"/go/broker/{k.id}", follow_redirects=False).status_code == 404


def test_go_ad_uses_db_target_only(client, db):
    from app.models import Banner
    k = make_broker(db, affiliate_url="https://example.com/broker")
    b1 = Banner(name="QC1", placement="after-bonus", target_url="https://example.com/ad", is_active=True)
    b2 = Banner(name="QC2", placement="before-blog", broker_id=k.id, target_url="", is_active=True)
    b3 = Banner(name="QC3", placement="before-blog", target_url="javascript:alert(1)", is_active=True)
    db.add_all([b1, b2, b3])
    db.commit()
    assert client.get(f"/go/ad/{b1.id}?url=https://evil.example", follow_redirects=False).headers["location"] == \
        "https://example.com/ad"
    assert client.get(f"/go/ad/{b2.id}", follow_redirects=False).headers["location"] == "https://example.com/broker"
    assert client.get(f"/go/ad/{b3.id}", follow_redirects=False).status_code == 404
    db.expire_all()
    assert db.get(Banner, b1.id).clicks == 1


def test_banner_shown_only_in_date_window(client, db):
    from app.models import Banner
    db.add_all([
        Banner(name="QC đang chạy", placement="after-bonus", target_url="https://example.com/1", is_active=True,
               start_date=date(2000, 1, 1), end_date=date(2999, 1, 1)),
        Banner(name="QC tương lai", placement="before-blog", target_url="https://example.com/2", is_active=True,
               start_date=date(2999, 1, 1)),
        Banner(name="QC đã hết", placement="rail-left", target_url="https://example.com/3", is_active=True,
               end_date=date(2000, 1, 1)),
    ])
    db.commit()
    c = client.get("/").context
    assert c["ad1"]["name"] == "QC đang chạy"
    assert c["ad2"] is None and c["rail_left"] is None
    assert c["home_sections"].count("ad1") == 1 and "ad2" not in c["home_sections"]
    assert client.get("/go/ad/2", follow_redirects=False).status_code == 404
    db.expire_all()
    assert db.query(Banner).filter_by(name="QC đang chạy").one().views == 1


def test_post_draft_hidden_and_markdown_sanitized(client, db):
    from app.models import Post
    db.add_all([Post(slug="nhap", title="Bài nháp", category="Kiến thức", status="draft"),
                Post(slug="da-dang", title="Bài đã đăng", category="Kiến thức", status="published",
                     body_md="**đậm** <script>alert(1)</script> [x](javascript:alert(1))")])
    db.commit()
    assert titles(client.get("/tin-tuc").context["posts"]) == ["Bài đã đăng"]
    assert client.get("/tin-tuc/nhap").status_code == 404
    html = client.get("/tin-tuc/da-dang").context["post"]["body_html"]
    assert "<strong>đậm</strong>" in html and "<script>alert" not in html and "javascript:" not in html


def test_setting_change_shows_on_public(client, db):
    from app import content
    content.put(db, "hero", {"headline": "Tiêu đề do admin nhập"})
    content.put(db, "pages", {"bonus": {"title": "Trang bonus mới"}})
    db.commit()
    assert client.get("/bonus").context["page"]["title"] == "Trang bonus mới"
    assert content.get(db, "hero")["headline"] == "Tiêu đề do admin nhập"
    # mặc định của các khóa khác vẫn còn sau khi trộn
    assert content.get(db, "pages")["san"]["title"] == "Sàn giao dịch uy tín"
    assert content.get(db, "hero")["cta"] == "Xem tất cả bonus"
