"""Hồi quy cho các mục Public FE ghi trong docs/ISSUES.md và lỗi thư mục data/."""
import os
import subprocess
import sys
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text

from conftest import ROOT, make_bonus, make_broker, titles
from app import content
from app.db import SessionLocal, engine
from app.models import Banner, Post


# 1. /san/so-sanh

def test_compare_empty_ids_means_nothing_selected(client, db):
    a = make_broker(db, "Sàn A", in_compare=True)
    make_broker(db, "Sàn B", in_compare=True)
    assert len(client.get("/san/so-sanh").context["compare_brokers"]) == 2  # không tham số: mặc định
    c = client.get("/san/so-sanh?ids=").context
    assert c["compare_brokers"] == [] and all(not p["selected"] for p in c["compare_pick"])
    assert c["compare_rows"][0]["cells"] == []
    assert next(p for p in c["compare_pick"] if p["id"] == a.id)["url"] == f"/san/so-sanh?ids={a.id}"


def test_compare_removing_last_pick_links_to_empty_selection(client, db):
    a = make_broker(db, "Sàn A")
    c = client.get(f"/san/so-sanh?ids={a.id}").context
    assert c["compare_pick"][0]["url"] == "/san/so-sanh?ids="
    assert client.get("/san/so-sanh?ids=").status_code == 200


# 2. Canonical

@pytest.mark.parametrize("url,canonical", [
    ("/bonus", "/bonus"), ("/bonus?type=nodep", "/bonus?type=nodep"), ("/bonus?type=nodep&sort=value", "/bonus?type=nodep"),
    ("/bonus?type=sai", "/bonus"), ("/bonus?sort=value", "/bonus"),
    ("/san?kind=crypto", "/san?kind=crypto"), ("/san?kind=sai", "/san"),
    ("/san/so-sanh?ids=1,2", "/san/so-sanh"), ("/tin-tuc", "/tin-tuc"),
])
def test_canonical_keeps_meaningful_query(client, url, canonical):
    assert client.get(url).context["meta"]["canonical"] == "http://testserver" + canonical


def test_canonical_pagination_and_category(client, db):
    db.add_all([Post(slug=f"bai-{i}", title=f"Bài {i}", category="Kiến thức", status="published") for i in range(13)])
    db.commit()
    assert client.get("/tin-tuc?page=2").context["meta"]["canonical"] == "http://testserver/tin-tuc?page=2"
    assert client.get("/tin-tuc?page=1").context["meta"]["canonical"] == "http://testserver/tin-tuc"
    assert client.get("/tin-tuc?page=99").context["meta"]["canonical"] == "http://testserver/tin-tuc?page=2"  # đã kẹp
    url = client.get("/tin-tuc?cat=Kiến thức&page=2").context["meta"]["canonical"]
    assert url == "http://testserver/tin-tuc?cat=Ki%E1%BA%BFn+th%E1%BB%A9c&page=2"


def test_canonical_broker_tab(client, db):
    k = make_broker(db)
    assert client.get(f"/san/{k.slug}").context["meta"]["canonical"].endswith(f"/san/{k.slug}")
    assert client.get(f"/san/{k.slug}?tab=overview").context["meta"]["canonical"].endswith(f"/san/{k.slug}")
    assert client.get(f"/san/{k.slug}?tab=accounts").context["meta"]["canonical"].endswith(f"/san/{k.slug}?tab=accounts")


# 3. Banner rail: view đếm bằng beacon

def _rail(db, placement="rail-left", **kw) -> Banner:
    b = Banner(**({"name": "QC dọc", "placement": placement, "target_url": "https://example.com/r", "is_active": True} | kw))
    db.add(b)
    db.commit()
    return b


def test_rail_render_does_not_count_view(client, db):
    rail = _rail(db)
    other = _rail(db, "after-bonus", name="QC ngang")
    c = client.get("/").context
    assert c["rail_left"]["view_url"] == f"/api/ad-view/{rail.id}" and c["ad1"]["view_url"] is None
    db.expire_all()
    assert db.get(Banner, rail.id).views == 0 and db.get(Banner, other.id).views == 1


def test_rail_beacon_counts_view(client, db):
    rail = _rail(db)
    assert client.post(f"/api/ad-view/{rail.id}").status_code == 204
    db.expire_all()
    assert db.get(Banner, rail.id).views == 1


def test_rail_beacon_rejects_other_banners(client, db):
    assert client.post("/api/ad-view/999").status_code == 404
    assert client.post(f"/api/ad-view/{_rail(db, 'after-bonus').id}").status_code == 404
    assert client.post(f"/api/ad-view/{_rail(db, is_active=False).id}").status_code == 404
    assert client.post(f"/api/ad-view/{_rail(db, end_date=date(2000, 1, 1)).id}").status_code == 404
    assert client.get(f"/api/ad-view/{_rail(db).id}").status_code in (404, 405)  # chỉ POST


def test_rail_beacon_is_rate_limited(client, db):
    rail = _rail(db)
    for _ in range(35):
        assert client.post(f"/api/ad-view/{rail.id}").status_code == 204
    db.expire_all()
    assert db.get(Banner, rail.id).views == 30


# 4. Trang 500 khi DB hỏng thật

@pytest.fixture
def plain_client():
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


def _assert_full_500(r):
    assert r.status_code == 500 and r.template.name == "public/500.html"
    assert r.context["site"]["site_name"] == "TradingBonusHub"
    assert r.context["page"]["title"] == "Đã có lỗi xảy ra"
    assert 'href="/static/css/site.css"' in r.text  # đủ khung site, không phải <h1> trần


def test_500_page_when_tables_are_missing(plain_client):
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE settings RENAME TO settings_hong"))
        conn.execute(text("ALTER TABLE bonuses RENAME TO bonuses_hong"))
    try:
        _assert_full_500(plain_client.get("/bonus"))
    finally:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE settings_hong RENAME TO settings"))
            conn.execute(text("ALTER TABLE bonuses_hong RENAME TO bonuses"))


def test_500_page_when_database_file_is_corrupt(plain_client, tmp_path):
    bad = tmp_path / "hong.db"
    bad.write_bytes(b"day khong phai file sqlite " * 400)
    bad_engine = create_engine(f"sqlite:///{bad.as_posix()}")
    event.listen(bad_engine, "connect", lambda conn, _: conn.execute("PRAGMA journal_mode=WAL"))
    SessionLocal.configure(bind=bad_engine)
    try:
        _assert_full_500(plain_client.get("/"))
    finally:
        SessionLocal.configure(bind=engine)
        bad_engine.dispose()


def test_404_page_survives_broken_settings(plain_client):
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE settings RENAME TO settings_hong"))
    try:
        r = plain_client.get("/khong-co-trang-nay")
        assert r.status_code == 404 and r.context["page"]["title"] == "Không tìm thấy trang"
    finally:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE settings_hong RENAME TO settings"))


# 5. Setting mặc định và admin sửa được

def test_footer_default_links_legal_pages(db):
    links = [x["url"] for col in content.get(db, "footer")["columns"] for x in col["links"]]
    assert "/dieu-khoan" in links and "/bao-mat" in links


def test_new_default_text(client):
    site = client.get("/").context["site"]
    assert site["footer"]["affiliate_note"] == "Một số liên kết là liên kết affiliate."
    assert site["cta_note"].startswith("Liên kết affiliate.") and site["ads_note"] == "CFD có rủi ro mất vốn cao."
    assert site["hero"]["card_label"] == "Nổi bật tuần này"
    assert site["contact_page"]["success_title"] == "Đã gửi"
    assert site["system_text"]["header_cta_page"] == "Nhận tư vấn"


def test_bonus_types_have_url_but_it_is_not_stored(client, admin, db):
    assert client.get("/").context["site"]["bonus_types"][0]["url"] == "/bonus?type=nodep"
    admin.post("/admin/home/types", {"title": "Loại", "nodep_label": "Không nạp"})
    assert all("url" not in t for t in content.get(db, "bonus_types"))
    assert client.get("/").context["site"]["bonus_types"][0]["url"] == "/bonus?type=nodep"


def test_admin_can_edit_notes_and_labels(admin, db):
    admin.post("/admin/home/menu", {"menu_label": ["Bonus"], "menu_url": ["/bonus"], "affiliate_note": "Có affiliate.",
                                    "cta_note": "Ghi chú nút.", "ads_note": ""})
    admin.post("/admin/home/hero", {"headline": "H", "card_label": "Hot", "image_path": "/static/img/hero-bg.webp"})
    admin.post("/admin/pages/lienhe", {"title": "Liên hệ", "success_title": "Đã nhận"})
    s = content.get_all(db)
    assert s["footer"]["affiliate_note"] == "Có affiliate." and s["cta_note"] == "Ghi chú nút."
    assert s["ads_note"] == "" and s["hero"]["card_label"] == "Hot" and s["contact_page"]["success_title"] == "Đã nhận"


def test_old_form_without_new_fields_keeps_values(admin, db):
    admin.post("/admin/home/menu", {"menu_label": ["Bonus"], "menu_url": ["/bonus"]})
    admin.post("/admin/home/hero", {"headline": "H", "image_path": "/static/img/hero-bg.webp"})
    admin.post("/admin/pages/lienhe", {"title": "Liên hệ"})
    s = content.get_all(db)
    assert s["cta_note"] and s["ads_note"] and s["footer"]["affiliate_note"]
    assert s["hero"]["card_label"] == "Nổi bật tuần này" and s["contact_page"]["success_title"] == "Đã gửi"


def test_admin_can_edit_system_text(admin, client, db):
    assert admin.get("/admin/pages?tab=system").status_code == 200
    r = admin.post("/admin/pages/system", {"not_found_title": "Lạc đường", "header_cta_page": "Hỏi ngay",
                                           "sub_invalid_title": "Link hỏng"})
    assert r.status_code == 303
    s = content.get(db, "system_text")
    assert s["header_cta_page"] == "Hỏi ngay" and s["error_title"] == "Đã có lỗi xảy ra"  # khóa khác giữ nguyên
    assert client.get("/khong-co").context["page"]["title"] == "Lạc đường"
    assert client.get("/xac-nhan/sai").context["page"]["title"] == "Link hỏng"


def test_home_hero_bonus_still_renders_with_new_keys(client, db):
    k = make_broker(db, featured=True, in_compare=True)
    make_bonus(db, k, "Thưởng nổi bật", value_num=5)
    assert client.get("/").context["hero_bonus"]["title"] == "Thưởng nổi bật"
    assert titles(client.get("/").context["compare_brokers"], "name") == ["Sàn A"]


# data/: import app không được tạo thư mục

def test_import_does_not_create_data_dirs(tmp_path):
    db_dir, up_dir = tmp_path / "chua-co" / "db", tmp_path / "chua-co-up"
    env = os.environ | {"DATABASE_URL": f"sqlite:///{(db_dir / 'app.db').as_posix()}", "UPLOAD_DIR": str(up_dir)}
    code = ("import app.main, app.cli, app.db\n"
            "from sqlalchemy import text\n"
            "import pathlib, sys\n"
            "assert not pathlib.Path(sys.argv[1]).exists()\n"
            "c = app.db.engine.connect(); c.execute(text('select 1')); c.close(); app.db.engine.dispose()\n")
    r = subprocess.run([sys.executable, "-c", code, str(db_dir)], cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert db_dir.exists() and not up_dir.exists()  # thư mục DB chỉ có khi kết nối thật


def test_media_returns_404_when_upload_dir_is_missing(admin, monkeypatch, tmp_path):
    from app.main import app
    media = next(r.app for r in app.routes if getattr(r, "name", "") == "media")
    monkeypatch.setattr(media, "directory", str(tmp_path / "chua-co"))
    monkeypatch.setattr(media, "all_directories", [str(tmp_path / "chua-co")])
    monkeypatch.setattr(media, "config_checked", False)  # ép chạy lại check_config như request đầu tiên
    assert admin.get("/media/khong-co.png").status_code == 404
