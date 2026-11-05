"""Các phép thử bổ sung sau khi đọc code: mỗi mục là một giả thuyết cụ thể, chỉ giữ cái tái hiện được."""
import re
import subprocess

import httpx
from playwright.sync_api import sync_playwright

from qalib import ADMIN_EMAIL, ADMIN_PASS, BASE, PY, ROOT, Http, Report, Server, mk_banner, mk_bonus, mk_broker, mk_post, png_bytes

R = Report("s7_probes")
c = R.check
s = Server("probe").start()
s.cli_admin()
h = Http().login()
pub = httpx.Client(base_url=BASE, timeout=20)


def title(t):
    return (re.search(r"<title>(.*?)</title>", t, re.S) or [None, ""])[1]


def desc(t):
    return (re.search(r'<meta name="description" content="([^"]*)"', t) or [None, ""])[1]


SECTIONS = ("hero", "about", "bonus", "ad1", "why", "types", "compare", "signup", "ad2", "blog")
try:
    # ---------- P1. SEO ở giá trị mặc định, chưa sửa gì ----------
    mk_broker(h, "Sàn SEO", summary="")
    mk_broker(h, "Sàn SEO Hai", summary="")
    mk_post(h, "Bài SEO", excerpt="Tóm tắt riêng")
    t1, t2 = pub.get("/san/san-seo").text, pub.get("/san/san-seo-hai").text
    c("P1.1", "Mặc định: 2 sàn có <title> khác nhau", title(t1) != title(t2) and "Sàn SEO" in title(t1), (title(t1), title(t2)))
    c("P1.2", "Mặc định: bài viết có description riêng", "Tóm tắt riêng" in desc(pub.get("/tin-tuc/bai-seo").text), desc(pub.get("/tin-tuc/bai-seo").text))
    ts = {p: title(pub.get(p).text) for p in ("/gioi-thieu", "/gioi-thieu/cach-danh-gia", "/gioi-thieu/affiliate")}
    c("P1.3", "3 trang Giới thiệu có <title> khác nhau", len(set(ts.values())) == 3, ts)
    c("P1.4", "/san và /san/so-sanh có <title> khác nhau", title(pub.get("/san").text) != title(pub.get("/san/so-sanh").text), title(pub.get("/san/so-sanh").text))
    ds = {p: desc(pub.get(p).text) for p in ("/gioi-thieu", "/gioi-thieu/affiliate")}
    c("P1.5", "Trang Giới thiệu có description khác nhau", len(set(ds.values())) == 2, ds)

    # ---------- P2. CLI đặt lại mật khẩu nâng quyền editor ----------
    s.cli_admin("bientap@qa.test", "MatKhau-Mot-123", "editor")
    env = {**s.env, "ADMIN_PASSWORD": "MatKhau-Hai-456"}
    r = subprocess.run([PY, "-m", "app.cli", "create-admin", "--email", "bientap@qa.test"], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
    role = s.sql("select role from admin_users where email='bientap@qa.test'")[0][0]
    c("P2.1", "README: chạy lại lệnh = đặt lại mật khẩu. Không được âm thầm đổi vai trò editor thành admin", role == "editor", f"role={role}; CLI in: {r.stdout.strip()}")

    # ---------- P3. Nội dung dài bị cắt thầm ----------
    body = "Đoạn văn dài. " * 8000  # khoảng 112.000 ký tự
    r = h.post("/admin/posts/new", {"title": "Bài rất dài", "category": "Kiến thức", "status": "published", "body_md": body + "CHỐT-CUỐI-BÀI"})
    n = s.sql("select length(body_md) from posts where title='Bài rất dài'")
    c("P3.1", "Bài > 100.000 ký tự: báo lỗi hoặc lưu đủ, không cắt thầm", r.status_code == 400 or (n and "CHỐT-CUỐI-BÀI" in s.sql("select body_md from posts where title='Bài rất dài'")[0][0]), f"HTTP {r.status_code}, lưu {n}")
    r = h.post("/admin/bonus/new", {"broker_id": 1, "type": "deposit", "title": "T" * 400, "is_active": "1"})
    n = s.sql("select length(title) from bonuses order by id desc limit 1")[0][0]
    c("P3.2", "Tiêu đề bonus 400 ký tự: báo lỗi, không cắt thầm còn 255", r.status_code == 400, f"HTTP {r.status_code}, lưu {n} ký tự")
    r = h.post("/admin/pages/gioithieu", [("title", "Về"), ("about_block_title", "Khối"), ("about_block_text", "x" * 1500 + "CUỐI")])
    t = pub.get("/gioi-thieu").text
    c("P3.3", "Khối Giới thiệu 1.500 ký tự không bị cắt thầm ở 1.000", "xCUỐI" in t or r.status_code == 400, f"HTTP {r.status_code}, chữ cuối {'còn' if 'xCUỐI' in t else 'mất'}")

    # ---------- P4. Banner chết khi sàn bỏ link affiliate ----------
    mk_broker(h, "Sàn Link", slug="san-link")
    kl = s.sql("select id from brokers where slug='san-link'")[0][0]
    mk_banner(h, "QC theo link sàn", broker_id=kl, target_url="", placement="after-bonus")
    mk_bonus(h, kl, "BonusLink")
    bn = s.sql("select id from banners")[0][0]
    h.post(f"/admin/brokers/{kl}/link", {"affiliate_url": ""})
    t = pub.get("/").text
    st = pub.get(f"/go/ad/{bn}").status_code
    c("P4.1", "Xóa link affiliate của sàn: banner dùng link đó không còn hiện link chết", f"/go/ad/{bn}" not in t or st == 302, f"banner vẫn hiện, /go/ad={st}")
    s.sql("delete from banners")

    # ---------- P5. Cấu hình rỗng ----------
    for sec in SECTIONS:
        h.post(f"/admin/home/sections/{sec}/toggle")
    r = pub.get("/")
    c("P5.1", "Tắt mọi section: trang chủ 200, vẫn có footer", r.status_code == 200 and "<footer" in r.text, r.status_code)
    c("P5.2", "Vẫn đúng 1 <h1>", len(re.findall(r"<h1", r.text)) == 1, len(re.findall(r"<h1", r.text)))
    for sec in SECTIONS:
        h.post(f"/admin/home/sections/{sec}/toggle")
    h.post("/admin/pages/lienhe", {"title": "Liên hệ", "desc": "", "topics": "", "intro": "", "response_note": "", "success_text": ""})
    r = pub.get("/lien-he")
    c("P5.3", "Không có chủ đề liên hệ: form vẫn gửi được", r.status_code == 200 and pub.post("/api/contact", data={"email": "a@x.co", "body": "x"}, headers={"CF-Connecting-IP": "4.4.4.1"}).status_code == 303)
    h.post("/admin/home/menu", {"about_text": "", "risk_note": "", "copyright": "", "affiliate_note": "", "cta_note": "", "ads_note": ""})
    c("P5.4", "Menu + footer rỗng: public 200", pub.get("/bonus").status_code == 200)
    c("P5.5", "Sau khi xóa hết menu, tab menu vẫn mở được", h.get("/admin/home?tab=menu").status_code == 200)
    s.sql("delete from settings where key in ('menu','footer','cta_note','ads_note','contact_page')")

    # ---------- P6. Trường ảnh nhận đường dẫn /static/img/ tùy ý ----------
    r = h.post("/admin/home/hero", {"eyebrow": "e", "headline": "h", "sub": "s", "cta": "c", "image_path": "/static/img/../../admin/logout\"><svg/onload=alert(1)>"})
    t = pub.get("/").text
    c("P6.1", "Đường dẫn ảnh giả dạng /static/img/ không chèn được HTML", "<svg/onload" not in t, r.status_code)
    c("P6.2", "Đường dẫn ảnh có ../ bị từ chối", r.status_code == 400, f"HTTP {r.status_code}, đã lưu làm ảnh hero")
    s.sql("delete from settings where key='hero'")

    # ---------- P7. Avatar sàn tên không Latin ----------
    mk_broker(h, "日本証券", slug="nhat", mono="")
    m = s.sql("select mono from brokers where slug='nhat'")[0][0]
    c("P7.1", "Tên không Latin: mono không rỗng (khối avatar không trống)", m != "", repr(m))

    # ---------- P9. Đường dẫn Windows không hợp lệ ----------
    for p in ("/media/a%3Cb.png", "/media/a%22b", "/media/a%7Cb", "/media/a:b:c", "/media/a%2A", "/static/a%3Fb", "/media/" + "a" * 260, "/media/" + "a" * 300 + ".png", "/static/" + "b" * 400, "/media/" + "c/" * 200):
        st = pub.get(p).status_code
        c(f"P9.{p[:24]}", f"{p[:40]}: 404, không 500", st == 404, st)

    # ---------- P10. Trình duyệt ----------
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        ctx.route("**/*", lambda r: r.fulfill(status=200, body="", content_type="text/css") if "fonts.g" in r.request.url else r.continue_())
        pg = ctx.new_page()
        pg.goto(BASE + "/admin/login")
        pg.fill("input[name=email]", ADMIN_EMAIL)
        pg.fill("input[name=password]", ADMIN_PASS)
        with pg.expect_navigation():
            pg.click("button[type=submit]")
        h.post("/admin/media/upload", {"alt": "ảnh thư viện"}, files={"files": ("a.png", png_bytes(), "image/png")})
        mp = s.sql("select path from media_files order by id desc limit 1")[0][0]
        pg.goto(BASE + "/admin/brokers/new")
        pg.fill(".drawer input[name=name]", "Sàn Picker")
        pg.locator("button:has-text('thư viện')").first.click()
        pg.wait_for_selector("#media-picker[open]")
        pg.locator(f".picker-item[data-path='{mp}']").click()
        with pg.expect_navigation():
            pg.click(".drawer-foot .btn-save")
        got = s.sql("select logo_path from brokers where name='Sàn Picker'")
        c("P10.1", "Chọn ảnh từ thư viện vào form sàn", got == [(mp,)], got)
        pg.goto(BASE + "/admin/brokers/new")
        pg.fill(".drawer input[name=name]", "Đang gõ dở")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)
        c("P10.2", "Esc khi drawer có thay đổi: hỏi trước khi bỏ", "/new" in pg.url or pg.locator("dialog[open]").count() >= 1, pg.url)
        pg.goto(BASE + "/admin/bonus")
        with pg.expect_navigation():
            pg.locator("form[action='/admin/logout'] button").first.click()
        pg.go_back()
        pg.wait_for_load_state()
        c("P10.3", "Đăng xuất rồi bấm Back: không thấy dữ liệu admin", "/admin/login" in pg.url, pg.url)
        pg.set_viewport_size({"width": 360, "height": 740})
        h2 = Http().login()
        k = s.sql("select id from brokers where slug='san-link'")[0][0]
        for n in (16, 24, 32, 40):
            s.sql("delete from bonuses")
            mk_bonus(h2, k, "Thẻ thử", withdrawable="x" * n, min_deposit="$10")
            pg.goto(BASE + "/bonus")
            o1 = pg.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            pg.goto(BASE + "/")
            o2 = pg.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            print(f"     từ liền {n} ký tự ở ô Rút được, 360px: /bonus lệch {o1}px, / lệch {o2}px", flush=True)
            if n == 24:
                c("P10.4", "Giá trị liền 24 ký tự trong thẻ bonus không làm tràn ở 360px", o1 <= 0 and o2 <= 0, (o1, o2))
        b.close()

    # ---------- P11. Giới hạn độ dài có hiện trong form không ----------
    forms = {"/admin/pages?tab=gioithieu": "about_block_text", "/admin/home?tab=why": "reason_text", "/admin/home?tab=about": "point_text", "/admin/posts/new": "body_md", "/admin/bonus/new": "title"}
    for url, nm in forms.items():
        html = h.get(url).text
        m = re.search(r'<(?:textarea|input)[^>]*name="' + nm + r'"[^>]*>', html)
        print(f"     {url} {nm}: maxlength={'có' if m and 'maxlength' in m.group(0) else 'không'}", flush=True)

    # ---------- P12. Chèn nội dung vào email xác nhận qua ô tên ----------
    spam = "TRÚNG THƯỞNG 500 USD, nhận tại http://evil.example/x"
    for i in range(5):
        pub.post("/api/subscribe", data={"name": spam, "email": "nannhan@qa.test", "next": "/"}, headers={"CF-Connecting-IP": "4.4.5.1"})
    log = s.log_text()
    n = len(s.tokens("nannhan@qa.test"))
    c("P12.1", "Tên người đăng ký không được in nguyên vào email gửi tới địa chỉ chưa xác nhận (kẻ khác dùng site gửi nội dung tùy ý)", spam not in log, f"email có câu: Chào {spam},")
    c("P12.2", "Một địa chỉ chưa xác nhận nhận tối đa 3 email/24 giờ", n <= 3, f"{n} email trong vài giây cho cùng địa chỉ")

    # ---------- P13. /docs ----------
    c("P13.1", "/docs đã bỏ ở dev (404, không còn trang trắng)", pub.get("/docs").status_code == 404, pub.get("/docs").status_code)
finally:
    s.stop()
# ---------- P14. SMTP hỏng ----------
s = Server("probe_mail", entry="qa/mailfail_run.py").start()
s.cli_admin()
h = Http().login()
try:
    pub.post("/api/subscribe", data={"email": "x@qa.test", "next": "/"})
    s.sql("update subscribers set status='confirmed'")
    r = h.post("/admin/subscribers/mail", {"subject": "Tin", "body": "Nội dung", "action": "send"})
    flash = r.headers.get("set-cookie", "")
    st = s.sql("select status, sent_count from campaigns")
    c("P14.1", "SMTP hỏng, 0 email đi: admin không được báo Đã gửi", "tbh_flash=sent" not in flash, f"flash={flash[:24]}, campaign={st}")
    c("P14.2", "SMTP hỏng: chiến dịch không ở trạng thái sent (để gửi lại được)", st and st[0][0] != "sent", st)
    r = pub.post("/api/subscribe", data={"email": "y@qa.test", "next": "/"}, headers={"CF-Connecting-IP": "4.4.6.1"})
    c("P14.3", "SMTP hỏng: form đăng ký không báo 'kiểm tra hộp thư'", "sub_ok" not in r.headers.get("set-cookie", ""), r.headers.get("set-cookie", "")[:30])
finally:
    s.stop()
R.save()
