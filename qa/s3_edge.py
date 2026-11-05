"""Vai C: biên và nghiệp vụ (HTTP thật vào server, dữ liệu nhập qua form admin)."""
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import httpx

from qalib import (BASE, WORK, Http, Report, Server, mk_banner, mk_bonus, mk_broker, mk_post, png_bytes)

R = Report("s3_edge")
c = R.check


def title_of(html):
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    return m.group(1) if m else ""


def meta_desc(html):
    m = re.search(r'<meta name="description" content="([^"]*)"', html)
    return m.group(1) if m else ""


# ---------- C1. Ranh giới ngày giờ VN ----------
now_file = WORK / "now.txt"
WORK.mkdir(parents=True, exist_ok=True)
now_file.write_text("2026-11-05T10:00:00+00:00")
s = Server("edge_tz", env={"QA_NOW_FILE": str(now_file)}, entry="qa/frozen_run.py").start()
try:
    s.cli_admin()
    h = Http().login()
    mk_broker(h, "Sàn TZ")
    kid = s.sql("select id from brokers")[0][0]
    mk_bonus(h, kid, "HetHan0511", expiry_date="2026-11-05")
    mk_bonus(h, kid, "HetHan0611", expiry_date="2026-11-06")
    mk_banner(h, "BN-het-0511", end_date="2026-11-05", placement="after-bonus")
    mk_banner(h, "BN-tu-0611", start_date="2026-11-06", placement="before-blog", target_url="https://ad.example.test/y")
    a1, a2 = [x[0] for x in s.sql("select id from banners order by id")]
    pub = httpx.Client(base_url=BASE, timeout=20)

    # 23:59 VN ngày 05/11 (16:59 UTC)
    now_file.write_text("2026-11-05T16:59:00+00:00")
    t = pub.get("/bonus").text
    c("C1.1", "23:59 VN 05/11: bonus hết hạn 05/11 vẫn hiện", "HetHan0511" in t)
    c("C1.2", "23:59 VN 05/11: banner end 05/11 còn chạy", pub.get(f"/go/ad/{a1}").status_code == 302)
    c("C1.3", "23:59 VN 05/11: banner start 06/11 chưa chạy", pub.get(f"/go/ad/{a2}").status_code == 404)
    # 00:30 VN ngày 06/11 (17:30 UTC, ngày UTC vẫn là 05/11)
    now_file.write_text("2026-11-05T17:30:00+00:00")
    t = pub.get("/bonus").text
    c("C1.4", "00:30 VN 06/11 (UTC còn 05/11): bonus hết hạn 05/11 đã biến mất", "HetHan0511" not in t)
    c("C1.5", "00:30 VN 06/11: bonus hết hạn 06/11 còn", "HetHan0611" in t)
    c("C1.6", "00:30 VN 06/11: /go/ad banner end 05/11 thành 404", pub.get(f"/go/ad/{a1}").status_code == 404)
    c("C1.7", "00:30 VN 06/11: banner start 06/11 đã chạy", pub.get(f"/go/ad/{a2}").status_code == 302)
    c("C1.8", "Trang sàn cũng bỏ bonus hết hạn", "HetHan0511" not in pub.get("/san/san-tz?tab=bonus").text)
    # chuyển năm: site.year
    now_file.write_text("2026-12-31T17:30:00+00:00")
    h.get("/admin")
finally:
    s.stop()

# ---------- Server chính ----------
s = Server("edge").start()
s.cli_admin()
h = Http().login()
pub = httpx.Client(base_url=BASE, timeout=20)
img = h.post("/admin/media/upload", {"alt": "logo"}, files={"files": ("l.png", png_bytes(), "image/png")})
assert img.status_code == 303
media_path = s.sql("select path from media_files")[0][0]


def bid(name):
    return s.sql("select id from brokers where name=?", (name,))[0][0]


try:
    # ---------- C2. Sàn inactive ----------
    mk_broker(h, "Sàn Tắt", in_compare="1", featured="1")
    k = bid("Sàn Tắt")
    mk_bonus(h, k, "BonusCuaSanTat", value_num="500")
    mk_banner(h, "QCsanTat", broker_id=k, target_url="", placement="after-bonus")
    ban = s.sql("select id from banners")[0][0]
    c("C2.0", "Trước khi tắt: sàn và bonus hiện", "BonusCuaSanTat" in pub.get("/").text)
    h.post(f"/admin/brokers/{k}/toggle", {"field": "is_active"})
    home = pub.get("/").text
    c("C2.1", "Tắt sàn: trang chủ không còn bonus", "BonusCuaSanTat" not in home)
    c("C2.2", "Tắt sàn: /san/slug 404", pub.get("/san/san-tat").status_code == 404)
    c("C2.3", "Tắt sàn: /bonus không còn", "BonusCuaSanTat" not in pub.get("/bonus").text)
    c("C2.4", "Tắt sàn: /go/broker 404", pub.get(f"/go/broker/{k}").status_code == 404)
    c("C2.5", "Tắt sàn: banner của sàn không hiện, /go/ad 404", pub.get(f"/go/ad/{ban}").status_code == 404 and "QCsanTat" not in home)
    c("C2.6", "Tắt sàn: khỏi sitemap", "san-tat" not in pub.get("/sitemap.xml").text)
    c("C2.7", "Tắt sàn: khỏi so sánh", "Sàn Tắt" not in pub.get(f"/san/so-sanh?ids={k}").text)
    c("C2.8", "Tắt sàn: hero không còn thẻ nổi bật", 'BonusCuaSanTat' not in home)

    # ---------- C3. Xóa sàn đang có bonus/banner ----------
    h.post(f"/admin/brokers/{k}/toggle", {"field": "is_active"})
    mk_banner(h, "QCcoTarget", broker_id=k, target_url="https://ad.example.test/keep", placement="before-blog")
    r = h.post(f"/admin/brokers/{k}/delete")
    c("C3.1", "Xóa sàn có bonus + banner: không lỗi", r.status_code == 303, r.status_code)
    c("C3.2", "Bonus bị xóa theo", s.sql("select count(*) from bonuses")[0][0] == 0)
    rows = s.sql("select id,name,broker_id,target_url,image_path,is_active from banners")
    ghost = [x for x in rows if x[1] == "QCsanTat"]
    home = pub.get("/").text
    if ghost:
        gid = ghost[0][0]
        shown = f"/go/ad/{gid}" in home
        st = pub.get(f"/go/ad/{gid}").status_code
        c("C3.3", "Banner không còn đích (sàn đã xóa, không target_url) không được hiện link chết trên trang chủ", not shown, f"banner #{gid} hiện={shown}, /go/ad={st}")
        adm = h.get("/admin/ads").text
        c("C3.4", "Admin thấy banner mồ côi không phải 'Đang chạy'", not re.search(r"QCsanTat.*?Đang chạy", adm, re.S), "vẫn báo Đang chạy")
    for b in s.sql("select id from banners"):
        h.post(f"/admin/ads/{b[0]}/delete")

    # ---------- C4. Giới hạn 3 compare / 1 featured ----------
    for n in ("K1", "K2", "K3"):
        mk_broker(h, n, in_compare="1")
    mk_broker(h, "K4")
    k4 = bid("K4")
    r = h.post(f"/admin/brokers/{k4}/toggle", {"field": "in_compare"})
    c("C4.1", "Bật so sánh sàn thứ 4 bị chặn (toggle)", s.sql("select count(*) from brokers where in_compare=1")[0][0] == 3)
    r = h.post("/admin/brokers/new", {"name": "K5", "kind": "forex", "license": "FCA", "in_compare": "1", "is_active": "1"})
    c("C4.2", "Thêm sàn thứ 4 có so sánh bị chặn (form)", r.status_code == 400, r.status_code)
    # sàn đã tắt có chiếm suất so sánh không?
    h.post(f"/admin/brokers/{bid('K1')}/toggle", {"field": "is_active"})
    r = h.post(f"/admin/brokers/{k4}/toggle", {"field": "in_compare"})
    n_vis = s.sql("select count(*) from brokers where in_compare=1 and is_active=1")[0][0]
    c("C4.3", "Sàn đã ẩn không chiếm suất: bật được sàn thứ 3 đang hiển thị", n_vis == 3, f"đang hiển thị={n_vis}, flash={h.cookies.get('tbh_flash')}")
    h.post(f"/admin/brokers/{bid('K1')}/toggle", {"field": "is_active"})
    h.post(f"/admin/brokers/{bid('K2')}/toggle", {"field": "featured"})
    h.post(f"/admin/brokers/{bid('K3')}/toggle", {"field": "featured"})
    c("C4.4", "Tối đa 1 featured (toggle)", s.sql("select count(*) from brokers where featured=1")[0][0] == 1)
    mk_broker(h, "K6", featured="1")
    c("C4.5", "Tối đa 1 featured (form)", s.sql("select name from brokers where featured=1") == [("K6",)])
    # compare công khai: ?ids=
    ids = ",".join(str(x[0]) for x in s.sql("select id from brokers order by id"))
    c("C4.6", "/san/so-sanh?ids=5 sàn chỉ lấy 3 cột", pub.get(f"/san/so-sanh?ids={ids}").text.count("Mở tài khoản") <= 3)

    # ---------- C5. Slug ----------
    r = h.post("/admin/brokers/new", {"name": "K1", "kind": "forex", "license": "FCA", "is_active": "1"})
    c("C5.1", "Trùng slug sàn: 400", r.status_code == 400 and "Slug đã được dùng" in r.text, r.status_code)
    mk_post(h, "Bài trùng")
    r = h.post("/admin/posts/new", {"title": "Bài trùng", "category": "Hướng dẫn", "status": "draft"})
    c("C5.2", "Trùng slug bài: 400", r.status_code == 400 and "Slug đã được dùng" in r.text, r.status_code)
    r = h.post("/admin/brokers/new", {"name": "So sánh", "kind": "forex", "license": "FCA", "is_active": "1", "summary": "Tóm tắt-so-sanh-XYZ"})
    t = pub.get("/san/so-sanh")
    c("C5.3", "Slug trùng route tĩnh (so-sanh) phải bị từ chối, nếu không trang sàn không bao giờ truy cập được",
      r.status_code == 400 or "Tóm tắt-so-sanh-XYZ" in t.text, f"POST={r.status_code}; /san/so-sanh vẫn là trang so sánh")
    r = h.post("/admin/brokers/new", {"name": "😀😀", "kind": "forex", "license": "FCA", "is_active": "1"})
    c("C5.4", "Tên toàn emoji: slug rỗng báo lỗi rõ, không 500", r.status_code == 400, r.status_code)
    long_name = ("ab " * 60)[:119] + " c"  # sau slugify ký tự cắt rơi vào dấu gạch
    r = h.post("/admin/posts/new", {"title": "x" * 119 + " yyy", "category": "Hướng dẫn", "status": "draft"})
    c("C5.5", "Tiêu đề dài > 120 ký tự, cắt slug rơi đúng dấu gạch vẫn lưu được (slug tự sinh)", r.status_code == 303, f"{r.status_code}: {re.findall(r'field-error[^>]*>([^<]+)', r.text)[:2]}")
    r = h.post("/admin/brokers/new", {"name": "Đồng Tiền Việt", "kind": "forex", "license": "FCA", "is_active": "1"})
    c("C5.6", "Slug tiếng Việt: dong-tien-viet", s.sql("select count(*) from brokers where slug='dong-tien-viet'")[0][0] == 1)

    # ---------- C6. Chuỗi dài, emoji ----------
    long = "Rấtdài" * 50
    r = h.post("/admin/brokers/new", {"name": "Dài" + "x" * 300, "kind": "forex", "license": "FCA", "is_active": "1"})
    c("C6.2", "Tên sàn vượt 120 ký tự: báo lỗi, không cắt", r.status_code == 400 and s.sql("select count(*) from brokers where name like 'Dàixx%'")[0][0] == 0, r.status_code)
    r = h.post("/admin/brokers/new", {"name": "Sàn F", "founded": "20" * 50, "kind": "forex", "license": "FCA", "is_active": "1"})
    c("C6.3", "founded vượt 20 ký tự: báo lỗi", r.status_code == 400, r.status_code)
    mk_broker(h, "Sàn Dài", slug="sandai", tagline=long[:250], summary=long * 40, license=long[:250], platforms=long[:250], founded="2020", min_deposit="9" * 60)
    k = s.sql("select id,length(name),length(founded) from brokers where slug='sandai'")[0]
    c("C6.4", "Trang sàn dài 200", pub.get("/san/sandai").status_code == 200)
    mk_bonus(h, k[0], "Tiêu đề 😀 ệẫữ ️", amount="💰 100$ 🚀")
    t = pub.get("/bonus").text
    c("C6.5", "Emoji/tiếng Việt hiện nguyên vẹn", "Tiêu đề 😀 ệẫữ" in t and "💰 100$ 🚀" in t)

    # ---------- C7. value_num ----------
    for v, label in (("inf", "inf"), ("-inf", "-inf"), ("nan", "nan"), ("1e999", "1e999"), ("1,5", "1,5"), ("-5", "âm")):
        r = h.post("/admin/bonus/new", {"broker_id": k[0], "type": "deposit", "title": f"Val {label}", "value_num": v, "is_active": "1"})
        ok = r.status_code in (303, 400)
        c(f"C7.{label}", f"value_num={v}: không 500", ok, r.status_code)
    inf_rows = s.sql("select count(*) from bonuses where value_num > 1e300 or value_num < -1e300")[0][0]
    c("C7.x", "value_num vô cực phải bị từ chối (số để sort)", inf_rows == 0, f"{inf_rows} dòng value_num=inf đã lưu")
    for path in ("/", "/bonus?sort=value", "/admin/bonus"):
        st = h.get(path).status_code
        c(f"C7.r{path}", f"Sau khi lưu giá trị lạ, {path} vẫn 200", st == 200, st)
    r = h.get("/admin/bonus")
    eid = s.sql("select id from bonuses where title='Val inf'")
    if eid:
        c("C7.e", "Mở form sửa bonus inf", h.get(f"/admin/bonus/{eid[0][0]}/edit").status_code == 200)
    s.sql("delete from bonuses where title like 'Val %'")

    # ---------- C8. Ngày ----------
    for v in ("0001-01-01", "9999-12-31", "31/12/2030", "2026-02-30", "abc"):
        r = h.post("/admin/bonus/new", {"broker_id": k[0], "type": "deposit", "title": f"Date {v}", "expiry_date": v, "is_active": "1"})
        c(f"C8.{v}", f"Ngày hết hạn {v}: không 500", r.status_code in (303, 400), r.status_code)
    c("C8.r", "/admin/bonus và /bonus 200 sau ngày biên", h.get("/admin/bonus").status_code == 200 and pub.get("/bonus?sort=expiry").status_code == 200)
    s.sql("delete from bonuses where title like 'Date %'")
    r = mk_post(h, "Bài năm 9999", published_at="9999-12-31")
    c("C8.p1", "Bài ngày 9999 là hẹn giờ: danh sách 200, trang bài 404", pub.get("/tin-tuc").status_code == 200 and pub.get("/tin-tuc/bai-nam-9999").status_code == 404)
    fut = (date.today() + timedelta(days=30)).isoformat()
    mk_post(h, "Bài hẹn giờ tương lai", published_at=fut)
    c("C8.p2", "Bài đăng ngày tương lai không hiện trước ngày đó", "Bài hẹn giờ tương lai" not in pub.get("/tin-tuc").text, "bài tương lai hiện ngay")
    s.sql("delete from posts where title in ('Bài năm 9999','Bài hẹn giờ tương lai')")

    # ---------- C9. Markdown ----------
    md = "# Tiêu đề một\n\n## Tiêu đề hai\n\nDòng một\nDòng hai\n\n- a\n- b\n\n1. x\n2. y\n\n```\ncode block\n<b>x</b>\n```\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n> trích\n\n![ảnh](" + media_path + ")\n\n[link](https://example.com)\n\n##### H5 nhỏ\n"
    mk_post(h, "Bài markdown", body_md=md.replace("\n", "\r\n"))
    t = pub.get("/tin-tuc/bai-markdown").text
    body = t[t.find('class="prose"'):]
    body = body[:body.find("</div>")]
    c("C9.1", "h2, ul, ol, table, blockquote, img, link render", all(x in body for x in ("<h2>", "<ul>", "<ol>", "<table>", "<blockquote>", f'src="{media_path}"', 'href="https://example.com"')), body[:300])
    c("C9.2", "'# Tiêu đề' (h1) không bị mất định dạng thành chữ thường", "<p>Tiêu đề một" not in body and re.search(r"<h[1-4]>Tiêu đề một", body), re.findall(r".{0,20}Tiêu đề một.{0,10}", body))
    c("C9.3", "Xuống dòng đơn trong đoạn được giữ (người nhập gõ 2 dòng)", "Dòng một<br" in body, re.findall(r"Dòng một.{0,20}", body, re.S))
    c("C9.4", "Khối ``` hiển thị thành khối code và escape <b>", "<pre>" in body and "&lt;b&gt;" in body, re.findall(r".{0,30}code block.{0,40}", body, re.S))
    c("C9.5", "##### H5 không mất định dạng", "<h5>" in body or "<h4>H5" in body, re.findall(r".{0,20}H5 nhỏ.{0,10}", body))

    # ---------- C10. Gửi hai lần / đua ----------
    def post_new(i):
        hh = Http()
        hh.cookies = dict(h.cookies)
        hh.csrf = h.csrf
        return hh.post("/admin/brokers/new", {"name": "Đua Slug", "kind": "forex", "license": "FCA", "is_active": "1"}).status_code
    with ThreadPoolExecutor(6) as ex:
        codes = list(ex.map(post_new, range(6)))
    c("C10.1", "Gửi đồng thời cùng slug: không 500 (chỉ 303 + 400)", 500 not in codes, codes)
    c("C10.2", "Chỉ tạo một sàn", s.sql("select count(*) from brokers where slug='dua-slug'")[0][0] == 1)

    # ---------- C11. 0 kết quả, phân trang ----------
    s.sql("delete from posts")
    s.sql("delete from bonuses")
    t = pub.get("/bonus?type=contest").text
    c("C11.1", "0 bonus: có empty state, không 'in 0'", "Chưa có ưu đãi" in t and "0 ưu đãi" not in t)
    t = pub.get("/tin-tuc?cat=So sánh").text
    c("C11.2", "0 bài: có câu trống", "Chưa có" in t, re.sub(r"<[^>]+>", " ", t)[-400:])
    t = pub.get(f"/san/so-sanh?ids={bid('K2')},{bid('K3')}").text
    cells = re.findall(r"Bonus đang có.*?</div>\s*(.{0,200})", t, re.S)
    c("C11.3", "Sàn 0 bonus: bảng so sánh không in số 0 (brief: con số đếm bằng 0 thì ẩn)", not re.search(r">\s*0\s*<", t[t.find("Bonus đang có"):t.find("Bonus đang có") + 400]), t[t.find("Bonus đang có"):t.find("Bonus đang có") + 200])
    for i in range(25):
        h.post("/admin/posts/new", {"title": f"Trang {i:02d}", "category": "Kiến thức" if i % 2 else "Tin sàn", "status": "published", "body_md": "x"})
    t = pub.get("/tin-tuc").text
    c("C11.4", "Tin tức bỏ phân trang: hiện đủ 25 bài", len(set(re.findall(r'href="/tin-tuc/(trang-\d+)', t))) == 25, len(set(re.findall(r'href="/tin-tuc/(trang-\d+)', t))))
    c("C11.6", "?page=999 (link cũ đã index) vẫn 200, không 500", pub.get("/tin-tuc?page=999").status_code == 200)
    for q in ("0", "-5", "99999999999999999999999999", "1.5", "abc", "", "%00"):
        r = pub.get(f"/tin-tuc?page={q}")
        c(f"C11.p{q}", f"/tin-tuc?page={q}: trang HTML 200 hoặc 404 (khách không thấy JSON lỗi)", r.status_code in (200, 404) and "text/html" in r.headers["content-type"], f"{r.status_code} {r.headers['content-type']} {r.text[:120]}")
    for path in ("/go/broker/abc", "/go/broker/99999999999999999999999", "/go/ad/99999999999999999999999", "/go/broker/-1"):
        r = pub.get(path)
        c(f"C11.g{path}", f"{path}: 404 trang lỗi", r.status_code == 404 and "text/html" in r.headers["content-type"], f"{r.status_code} {r.headers['content-type']} {r.text[:80]!r}")
    r = pub.post("/api/ad-view/99999999999999999999999")
    c("C11.b", "ad-view id khổng lồ: không 500", r.status_code in (404, 204), r.status_code)
    for path in ("/admin/bonus/99999999999999999999999/edit", "/admin/brokers/abc/edit", "/admin/subscribers?draft=abc", "/admin/subscribers?draft=99999999999999999999999", "/admin/messages/99999999999999999999999"):
        r = h.get(path)
        c(f"C11.a{path}", f"{path}: không 500", r.status_code < 500, r.status_code)
    for path in ("/", "/bonus", "/san", "/health", "/robots.txt", "/sitemap.xml"):
        r = pub.head(path)
        c(f"C11.h{path}", f"HEAD {path} không 405 (uptime check, bot)", r.status_code == 200, r.status_code)

    # ---------- C12. SEO: trang chi tiết không bị title chung của mục ----------
    k = bid("K2")
    h.post(f"/admin/brokers/{k}/edit", {"name": "K2", "slug": "k2", "kind": "forex", "license": "FCA", "is_active": "1", "summary": ""})
    mk_post(h, "Bài SEO", excerpt="Mô tả riêng của bài")
    h.post("/admin/pages/san", {"title": "Sàn", "desc": "D", "meta_title": "SEO chung mục Sàn", "meta_desc": "SEO mô tả chung Sàn"})
    h.post("/admin/pages/tin", {"title": "Tin", "desc": "D", "meta_title": "SEO chung mục Tin", "meta_desc": "SEO mô tả chung Tin"})
    t = pub.get("/san/k2").text
    c("C12.1", "<title> trang sàn riêng từng sàn, không phải meta_title của mục Sàn", "K2" in title_of(t), title_of(t))
    c("C12.2", "So sánh có <title> riêng khác /san", title_of(pub.get("/san/so-sanh").text) != title_of(pub.get("/san").text), title_of(pub.get("/san/so-sanh").text))
    t = pub.get("/tin-tuc/bai-seo").text
    c("C12.3", "<title> bài viết riêng", "Bài SEO" in title_of(t), title_of(t))
    c("C12.4", "meta description bài viết là excerpt riêng, không phải meta_desc của mục Tin", "Mô tả riêng" in meta_desc(t), meta_desc(t))

    # ---------- C13. Đếm view khi section tắt ----------
    mk_banner(h, "QC section tắt", placement="after-bonus", target_url="https://ad.example.test/s")
    mk_bonus(h, bid("K3"), "Có bonus")
    bn = s.sql("select id from banners where name='QC section tắt'")[0][0]
    pub.get("/")
    v1 = s.sql("select views from banners where id=?", (bn,))[0][0]
    h.post("/admin/home/sections/ad1/toggle")
    for _ in range(3):
        t = pub.get("/").text
    v2 = s.sql("select views from banners where id=?", (bn,))[0][0]
    c("C13.1", "Tắt section Quảng cáo #1: banner không hiện", f"/go/ad/{bn}" not in t)
    c("C13.2", "Tắt section: không cộng lượt hiển thị (không hiển thị thì không tính)", v2 == v1, f"views {v1} -> {v2} dù section tắt")
    h.post("/admin/home/sections/ad1/toggle")

    # ---------- C14. lastmod sitemap không đổi vì lượt xem/click ----------
    s.sql("update posts set updated_at='2020-01-01 00:00:00' where slug='bai-seo'")
    s.sql("update brokers set updated_at='2020-01-01 00:00:00' where slug='k2'")
    pub.get("/tin-tuc/bai-seo")
    h.post(f"/admin/brokers/{k}/link", {"affiliate_url": "https://aff.example.test/z"})
    s.sql("update brokers set updated_at='2020-01-01 00:00:00' where slug='k2'")
    pub.get(f"/go/broker/{k}")
    sm = pub.get("/sitemap.xml").text
    c("C14.1", "Mở bài viết không làm đổi lastmod", re.search(r"bai-seo</loc><lastmod>2020", sm), re.findall(r"bai-seo</loc><lastmod>[^<]+", sm))
    c("C14.2", "Click affiliate không làm đổi lastmod của sàn", re.search(r"/san/k2</loc><lastmod>2020", sm), re.findall(r"/san/k2</loc><lastmod>[^<]+", sm))

    # ---------- C15. ClickLog khi xóa rồi tạo lại (id tái sử dụng) ----------
    mk_broker(h, "Sàn Cuối")
    last = bid("Sàn Cuối")
    for _ in range(3):
        pub.get(f"/go/broker/{last}")
    h.post(f"/admin/brokers/{last}/delete")
    mk_broker(h, "Sàn Mới Tinh")
    nid = bid("Sàn Mới Tinh")
    t = h.get("/admin/brokers?tab=links").text
    row = t[t.find("Sàn Mới Tinh"):t.find("Sàn Mới Tinh") + 900]
    c("C15.1", "Sàn mới không thừa hưởng click 30 ngày của sàn đã xóa", nid != last or ">3<" not in row, f"id cũ={last}, id mới={nid}, dòng: {re.sub(r'<[^>]+>', ' ', row)[:160]}")

    # ---------- C16. Email lạ ở form đăng ký ----------
    weird = ['a,b@x.co', 'a"b@x.co', 'a(b@x.co', 'a<b@x.co', 'tèst@ví-dụ.vn', 'a;b@x.co', "o'neil@x.co",
             '=?utf-8?q?x?=@x.co', 'a@b.c.', 'a..b@x.co', ('x' * 240) + '@x.co', 'a:b@x.co', '[a]@x.co', 'a%b@x.co']
    for i, w in enumerate(weird):
        r = pub.post("/api/subscribe", data={"email": w, "next": "/"}, headers={"CF-Connecting-IP": f"10.9.0.{i}"})
        c(f"C16.{i}", f"Đăng ký email lạ {w[:24]!r}: không 500", r.status_code == 303, r.status_code)
    # xác nhận hết rồi gửi chiến dịch: một địa chỉ lạ không được làm hỏng cả lô
    s.sql("update subscribers set status='confirmed'")
    n = s.sql("select count(*) from subscribers")[0][0]
    r = h.post("/admin/subscribers/mail", {"subject": "Chiến dịch", "body": "Nội dung", "action": "send"})
    st = s.sql("select status, sent_count from campaigns order by id desc limit 1")
    c("C16.c", f"Chiến dịch tới {n} địa chỉ (có địa chỉ lạ): không 500, trạng thái sent", r.status_code == 303 and st and st[0][0] == "sent", f"{r.status_code} {st}")
    c("C16.t", "Admin mở lại Người đăng ký không lỗi", h.get("/admin/subscribers").status_code == 200)
    s.sql("delete from subscribers")
    s.sql("delete from campaigns")

    # ---------- C17. Đăng ký hai lần: link đầu còn dùng được? ----------
    for _ in range(2):
        pub.post("/api/subscribe", data={"email": "hailan@x.co", "next": "/"}, headers={"CF-Connecting-IP": "10.8.0.1"})
    tk = s.tokens("hailan@x.co")
    c("C17.1", "Bấm gửi hai lần: gửi 2 email xác nhận (hoặc 1)", len(tk) in (1, 2), len(tk))
    if len(tk) >= 2:
        r = pub.post(f"/xac-nhan/{tk[0]}")
        c("C17.2", "Link trong email thứ nhất vẫn xác nhận được (người dùng hay mở email đầu)", r.status_code == 200, r.status_code)

    # ---------- C18. Liên hệ gửi hai lần ----------
    d = {"topic": "Hợp tác", "name": "Khách", "email": "k@x.co", "body": "Xin chào"}
    for _ in range(2):
        pub.post("/api/contact", data=d, headers={"CF-Connecting-IP": "10.8.0.2"})
    print("     hai POST liên hệ giống nhau:", s.sql("select count(*) from contact_messages")[0][0], "tin (không phải lỗi, bấm đúp thật kiểm ở B8.8)", flush=True)
    r = pub.post("/api/contact", data={**d, "topic": "<b>chủ đề giả</b>" * 3}, headers={"CF-Connecting-IP": "10.8.0.3"})
    c("C18.2", "Chủ đề ngoài danh sách bị từ chối hoặc chuẩn hóa", s.sql("select count(*) from contact_messages where topic like '%chủ đề giả%'")[0][0] == 0, "lưu nguyên chủ đề tùy ý")
    r = pub.post("/api/contact", data={**d, "email": "sai", "body": ""}, headers={"CF-Connecting-IP": "10.8.0.4"})
    c("C18.3", "Lỗi validate liên hệ: 400, không index (canonical không trỏ /api/contact)", r.status_code == 400 and "/api/contact\"" not in re.sub(r'action="/api/contact"', "", r.text), re.findall(r'rel="canonical" href="[^"]+"', r.text))
    r = pub.post("/api/contact", data={**d, "body": "x" * 5001}, headers={"CF-Connecting-IP": "10.8.0.5"})
    c("C18.4", "Nội dung > 5000: 400", r.status_code == 400)
    r = pub.post("/api/contact", content=bytes([255,254,61,255]), headers={"Content-Type": "application/x-www-form-urlencoded"})
    c("C18.5", "Form rác byte: không 500", r.status_code < 500, r.status_code)
    r = pub.post("/api/subscribe", content=b"email=" + b"a" * 3_000_000, headers={"Content-Type": "application/x-www-form-urlencoded", "CF-Connecting-IP": "10.8.0.6"})
    c("C18.6", "Thân form 3MB: không 500", r.status_code < 500, r.status_code)

    # ---------- C19. Banner không ảnh, không sàn ----------
    s.sql("delete from banners")
    mk_banner(h, "QC chỉ link", placement="after-bonus")
    t = pub.get("/").text
    i = t.find("/go/ad/")
    frag = t[max(0, i - 300):i + 500]
    link = re.search(r'<a href="/go/ad/\d+"[^>]*>(.*?)</a>', frag, re.S)
    c("C19.1", "Banner không ảnh (khối nền theo brief 13): link vẫn có tên cho trình đọc màn hình", link and (link.group(1).strip() or "aria-label" in link.group(0)), link and link.group(0)[:160])
    c("C19.2", "Banner luôn có nhãn Tài trợ", "Tài trợ" in frag)
    # đặt link đúng 1000 ký tự
    url = "https://x.test/" + "a" * 985
    r = h.post(f"/admin/brokers/{bid('K3')}/link", {"affiliate_url": url})
    c("C19.3", "Link affiliate 1000 ký tự redirect đúng", pub.get(f"/go/broker/{bid('K3')}").headers.get("location") == url)
    url = "https://x.test/?q=tiếng việt"
    r = h.post(f"/admin/brokers/{bid('K3')}/link", {"affiliate_url": url})
    c("C19.4", "Link có khoảng trắng bị từ chối", s.sql("select affiliate_url from brokers where name='K3'")[0][0] != url)
    url = "https://x.test/?q=tiếng&ref=1|2"
    h.post(f"/admin/brokers/{bid('K3')}/link", {"affiliate_url": url})
    loc = pub.get(f"/go/broker/{bid('K3')}").headers.get("location")
    c("C19.5", "Link có dấu tiếng Việt: redirect không vỡ", loc and loc.startswith("https://x.test/?q=ti"), loc)

    # ---------- C20. Lưu lại form không đổi gì không được làm mất dữ liệu ----------
    # (kiểm bằng trình duyệt ở s1). Ở đây: POST thiếu trường hiện có
    k3 = bid("K3")
    before = s.sql("select clicks, pros, summary from brokers where id=?", (k3,))[0]
    h.post(f"/admin/brokers/{k3}/toggle", {"field": "featured"})
    after = s.sql("select clicks, pros, summary from brokers where id=?", (k3,))[0]
    c("C20.1", "Toggle không đổi trường khác", before == after)
finally:
    s.stop()
bad = R.save()
