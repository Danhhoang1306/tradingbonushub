"""Vai B: khách trên Chromium. Link ngoài (aff/ad) bị chặn tại trình duyệt, không ra mạng thật."""
import re

import httpx
from playwright.sync_api import sync_playwright

from qalib import BASE, Http, Report, Server, mk_banner, mk_bonus, mk_broker, mk_post

R = Report("s2_visitor")
c = R.check
s = Server("visitor").start()
s.cli_admin()
h = Http().login()
pub = httpx.Client(base_url=BASE, timeout=20)
errs = []

for n, kind, cmp_ in (("Forex Một", "forex", "1"), ("Forex Hai", "forex", "1"), ("Crypto Ba", "crypto", "1"), ("Crypto Bốn", "crypto", None), ("Forex Năm", "forex", None)):
    mk_broker(h, n, kind=kind, in_compare=cmp_, affiliate_url=f"https://aff.example.test/{n[-1]}")
ids = dict(s.sql("select name,id from brokers"))
K = list(ids.values())
mk_bonus(h, K[0], "B-gia-100", value_num="100", type="deposit", expiry_date="2031-01-01")
mk_bonus(h, K[1], "B-gia-900", value_num="900", type="deposit", expiry_date="2030-01-01")
mk_bonus(h, K[2], "B-gia-500", value_num="500", type="crypto", expiry_date="")
mk_bonus(h, K[3], "B-gia-trong", value_num="", type="nodep", expiry_date="2029-01-01")
mk_bonus(h, K[4], "B-cashback", value_num="10", type="cashback", expiry_date="")
for i in range(26):
    mk_post(h, f"Tin số {i:02d}", category=("Kiến thức" if i % 2 else "Tin sàn"), show_home="1" if i < 5 else None)
mk_banner(h, "QC1", placement="after-bonus", broker_id=K[0], target_url="https://aff.example.test/qc1")
mk_banner(h, "QC2", placement="before-blog", target_url="https://aff.example.test/qc2")
mk_banner(h, "Rail1", placement="rail-left", broker_id=K[1], target_url="https://aff.example.test/rail")


def order(html):
    return re.findall(r"B-(?:gia-\w+|cashback)", html)


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    ctx.route("**/*", lambda r: r.fulfill(status=200, body="ok") if "example.test" in r.request.url else (r.fulfill(status=200, body="", content_type="text/css") if "fonts.g" in r.request.url else r.continue_()))
    seen = []
    ctx.on("request", lambda r: seen.append(r.url))
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(("pageerror", pg.url, str(e))))
    pg.on("console", lambda m: errs.append(("console", pg.url, m.text)) if m.type == "error" else None)

    # ---------- B1. Lọc + sort /bonus ----------
    pg.goto(BASE + "/bonus")
    c("B1.1", "5 bonus, mới nhất trước", order(pg.content())[:1] == ["B-cashback"], order(pg.content()))
    pg.get_by_role("link", name=re.compile("Giá trị cao")).first.click()
    pg.wait_for_load_state()
    c("B1.2", "Sort Giá trị cao: 900, 500, 100, 10, rồi bonus không có giá trị", order(pg.content()) == ["B-gia-900", "B-gia-500", "B-gia-100", "B-cashback", "B-gia-trong"], order(pg.content()))
    pg.get_by_role("link", name=re.compile("Deposit")).first.click()
    pg.wait_for_load_state()
    c("B1.3", "Đổi tab giữ sort, chỉ deposit", "sort=value" in pg.url and "type=deposit" in pg.url and order(pg.content()) == ["B-gia-900", "B-gia-100"], (pg.url, order(pg.content())))
    pg.get_by_role("link", name=re.compile("Sắp hết hạn")).first.click()
    pg.wait_for_load_state()
    c("B1.4", "Đổi sort giữ tab, hạn sớm trước", "type=deposit" in pg.url and order(pg.content()) == ["B-gia-900", "B-gia-100"], (pg.url, order(pg.content())))
    pg.goto(BASE + "/bonus?sort=expiry")
    c("B1.5", "Sắp hết hạn: bonus Liên tục xuống cuối", order(pg.content())[:3] == ["B-gia-trong", "B-gia-900", "B-gia-100"], order(pg.content()))
    pg.goto(BASE + "/bonus?type=contest")
    c("B1.6", "Không có bonus loại đó: câu trống", "Chưa có ưu đãi" in pg.inner_text("main"))

    # ---------- B2. Lọc ở trang chủ ----------
    pg.goto(BASE + "/")
    btn = pg.locator("[data-filter=crypto]")
    c("B2.1", "Có nút lọc crypto", btn.count() == 1)
    btn.click()
    vis = pg.locator("#bonus [data-type]:visible").count()
    c("B2.2", "Lọc tại chỗ còn 1 thẻ", vis == 1, vis)
    pg.locator("[data-filter=all]").click()
    c("B2.3", "Tất cả: 5 thẻ", pg.locator("#bonus [data-type]:visible").count() == 5)
    pg.locator("[data-type-tab]").nth(2).click()
    c("B2.4", "Tab Loại bonus đổi panel", pg.locator("[data-type-panel]:visible").count() == 1)

    # ---------- B3. Sàn ----------
    pg.goto(BASE + "/san")
    t = pg.inner_text("main")
    c("B3.1", "5 sàn", all(n in t for n in ids))
    pg.get_by_role("link", name=re.compile("Crypto")).first.click()
    pg.wait_for_load_state()
    t = pg.inner_text("main")
    c("B3.2", "Lọc crypto", "kind=crypto" in pg.url and "Crypto Ba" in t and "Forex Một" not in t, pg.url)

    # ---------- B4. So sánh 1 đến 3 ----------
    pg.goto(BASE + "/san/so-sanh?ids=")
    c("B4.0", "ids rỗng: câu trống", "Chưa chọn sàn" in pg.inner_text("main"))
    for n, cols in (("Forex Một", 1), ("Crypto Ba", 2), ("Forex Năm", 3)):
        pg.locator(".compare-pick a", has_text=n).click()
        pg.wait_for_load_state()
        c(f"B4.{cols}", f"Chọn {cols} sàn", pg.locator(".compare-grid__name").count() == cols, pg.locator(".compare-grid__name").count())
    c("B4.4", "Đủ 3: pill khác bị khóa", pg.locator(".compare-pick .is-disabled").count() == 2)
    r = pg.locator(".compare-pick a[aria-pressed=true]", has_text="Crypto Ba")
    r.click()
    pg.wait_for_load_state()
    c("B4.5", "Bỏ chọn còn 2 và không còn khóa", pg.locator(".compare-grid__name").count() == 2 and pg.locator(".compare-pick .is-disabled").count() == 0)
    t = pg.inner_text(".compare-grid")
    c("B4.6", "8 dòng thông tin + nút mở tài khoản", all(x in t for x in ("Giấy phép", "Nạp tối thiểu", "Đòn bẩy tối đa", "Spread / phí", "Nền tảng", "Rút tiền", "Thành lập", "Bonus đang có")))
    pg.goto(BASE + "/san/so-sanh")
    c("B4.7", "Mặc định: sàn admin bật so sánh", pg.locator(".compare-grid__name").count() == 3)

    # ---------- B5. Chi tiết sàn 4 tab ----------
    pg.goto(BASE + "/san/forex-mot")
    for name, q in (("Bonus", "?tab=bonus"), ("Tài khoản & phí", "?tab=accounts"), ("Nạp & rút", "?tab=pay"), ("Tổng quan", "")):
        pg.locator(f'a[href="/san/forex-mot{q}"]').first.click()
        pg.wait_for_load_state()
        c(f"B5.{name}", f"Tab {name}", pg.url.endswith("/san/forex-mot" + q), pg.url)
    a = pg.locator("a", has_text="Mở tài khoản").first
    c("B5.1", "Nút Mở tài khoản: tab mới, rel sponsored nofollow noopener", a.get_attribute("target") == "_blank" and all(x in (a.get_attribute("rel") or "") for x in ("sponsored", "nofollow", "noopener")), a.get_attribute("rel"))
    c("B5.2", "Có dòng công bố affiliate dưới nút", "Liên kết affiliate" in pg.inner_text("main"))
    pg.goto(BASE + "/san/forex-mot?tab=accounts")
    c("B5.3", "Chưa có tài khoản: câu trống, không lỗi", "Chưa có" in pg.inner_text("main"), pg.inner_text("main")[:200])

    # ---------- B6. Tin tức ----------
    pg.goto(BASE + "/tin-tuc")
    c("B6.1", "12 bài trang 1", pg.locator(".post-card").count() == 12, pg.locator(".post-card").count())
    pg.get_by_role("link", name=re.compile("sau|Sau|›|→|Tiếp")).last.click()
    pg.wait_for_load_state()
    c("B6.2", "Sang trang 2", "page=2" in pg.url, pg.url)
    first_p2 = pg.locator(".post-card").first.inner_text()
    pg.goto(BASE + "/tin-tuc?page=3")
    c("B6.3", "Trang 3 còn 2 bài", pg.locator(".post-card").count() == 2)
    pg.goto(BASE + "/tin-tuc?cat=Tin sàn")
    c("B6.4", "Lọc chuyên mục: 12 bài, có trang 2 giữ cat", pg.locator(".post-card").count() == 12 and pg.locator("a[href*='page=2']").count() >= 1 and "cat=" in (pg.locator("a[href*='page=2']").first.get_attribute("href") or ""))
    pg.goto(BASE + "/tin-tuc?cat=So sánh")
    c("B6.5", "Chuyên mục rỗng: câu trống", pg.locator(".post-card").count() == 0 and len(pg.inner_text("main").strip()) > 0)
    pg.goto(BASE + "/tin-tuc/tin-so-03")
    c("B6.6", "Bài chi tiết có bài liên quan cùng chuyên mục", pg.locator(".post-card").count() >= 1)
    c("B6.7", "Lượt xem tăng", s.sql("select views from posts where slug='tin-so-03'")[0][0] == 1)

    # ---------- B7. Đăng ký email ----------
    pg.goto(BASE + "/#dang-ky")
    pg.fill("#dang-ky input[name=name]", "Khách Một 😀")
    pg.fill("#dang-ky input[name=email]", "Khach.Mot@Qa.Test")
    pg.locator("#dang-ky label.chip", has_text=re.compile("Cashback")).click()
    with pg.expect_navigation():
        pg.locator("#dang-ky button[type=submit]").click()
    c("B7.1", "Đăng ký: khối thành công, về #dang-ky", "#dang-ky" in pg.url and pg.locator("#dang-ky .notice, #dang-ky [role=status]").count() >= 1, pg.url)
    row = s.sql("select email,status,interests,name from subscribers")
    c("B7.2", "Email chuẩn hóa thường, trạng thái pending, sở thích đúng", row and row[0][0] == "khach.mot@qa.test" and row[0][1] == "pending" and "cashback" in row[0][2], row)
    pg.reload()
    c("B7.3", "Tải lại trang: thông báo một lần rồi mất", pg.locator("#dang-ky form").count() == 1)
    tk = s.tokens("khach.mot@qa.test")
    c("B7.4", "Email xác nhận gửi đúng 1 lần", len(tk) == 1, len(tk))
    t = s.log_text()
    c("B7.5", "Email có link hủy", "/huy-dang-ky/" in t)
    pg.goto(f"{BASE}/xac-nhan/{tk[0]}")
    c("B7.6a", "GET link xác nhận chỉ hiện nút, chưa đổi trạng thái", s.sql("select status from subscribers")[0][0] == "pending" and pg.locator(".status-box form button").count() == 1)
    with pg.expect_navigation():
        pg.locator(".status-box form button").click()
    c("B7.6", "Bấm nút: xác nhận thành công", "Đã xác nhận" in pg.inner_text("body") and s.sql("select status from subscribers")[0][0] == "confirmed")
    pg.goto(f"{BASE}/xac-nhan/{tk[0]}")
    c("B7.7", "Bấm lại link xác nhận: vẫn trang xác nhận", "Đã xác nhận" in pg.inner_text("body"))
    r = pub.post("/api/subscribe", data={"email": "khach.mot@qa.test", "next": "/"}, headers={"CF-Connecting-IP": "6.6.6.1"})
    c("B7.8", "Đăng ký lại khi đã xác nhận: không gửi mail", len(s.tokens("khach.mot@qa.test")) == 1)
    r = pub.get(f"/xac-nhan/saitoken")
    c("B7.9", "Token sai: 404 trang rõ ràng", r.status_code == 404 and "Liên kết không hợp lệ" in r.text)
    r = pub.post(f"/huy-dang-ky/saitoken")
    c("B7.10", "Token hủy sai: 404", r.status_code == 404)
    pg.goto(f"{BASE}/huy-dang-ky/{tk[0]}")
    c("B7.11a", "GET link hủy chỉ hiện nút", s.sql("select status from subscribers")[0][0] == "confirmed")
    with pg.expect_navigation():
        pg.locator(".status-box form button").click()
    c("B7.11", "Bấm nút: hủy thành công", "Đã hủy" in pg.inner_text("body") and s.sql("select status from subscribers")[0][0] == "unsubscribed")
    r = pub.post(f"/xac-nhan/{tk[0]}")
    c("B7.12", "Link xác nhận cũ sau khi hủy: không kích hoạt lại", r.status_code == 404 and s.sql("select status from subscribers")[0][0] == "unsubscribed")
    pub.post("/api/subscribe", data={"email": "khach.mot@qa.test", "interests": ["crypto"], "next": "/"}, headers={"CF-Connecting-IP": "6.6.6.2"})
    tk2 = s.tokens("khach.mot@qa.test")
    c("B7.13", "Đăng ký lại sau khi hủy: pending, mail mới, token mới", len(tk2) == 2 and tk2[1] != tk[0] and s.sql("select status from subscribers")[0][0] == "pending")
    r = pub.post(f"/xac-nhan/{tk2[1]}")
    c("B7.14", "Xác nhận lại được; sở thích là cái vừa chọn", s.sql("select status,interests from subscribers")[0] == ("confirmed", '["crypto"]'), s.sql("select status,interests from subscribers"))
    for _ in range(2):
        pub.post("/api/subscribe", data={"email": "hailan@x.co", "next": "/"}, headers={"CF-Connecting-IP": "6.6.6.3"})
    tks = s.tokens("hailan@x.co")
    r = pub.post(f"/xac-nhan/{tks[0]}")
    c("B7.15", "Gửi form 2 lần: link trong email thứ nhất vẫn dùng được (người dùng mở email nào cũng xác nhận được)", r.status_code == 200, f"email 1 -> {r.status_code}, có {len(tks)} email")
    # kẻ khác spam địa chỉ nạn nhân sau khi nạn nhân đã hủy
    tv = s.tokens("hailan@x.co")[-1]
    pub.post(f"/xac-nhan/{tv}")
    pub.post(f"/huy-dang-ky/{tv}")
    pub.post("/api/subscribe", data={"email": "hailan@x.co", "next": "/"}, headers={"CF-Connecting-IP": "6.6.6.4"})
    print("     đã hủy vẫn nhận mail xác nhận khi ai đó đăng ký lại:", len(s.tokens("hailan@x.co")), flush=True)
    # sai định dạng, không JS validate
    r = pub.post("/api/subscribe", data={"email": "khong-hop-le", "next": "/"}, headers={"CF-Connecting-IP": "6.6.6.5"}, follow_redirects=False)
    c("B7.16", "Email sai: flash sub_invalid", "tbh_flash=sub_invalid" in r.headers.get("set-cookie", ""))
    pg.goto(BASE + "/")
    pg.fill("#dang-ky input[name=email]", "sai@")
    pg.locator("#dang-ky button[type=submit]").click()
    pg.wait_for_timeout(300)
    # giới hạn tần suất
    rl = [pub.post("/api/subscribe", data={"email": f"r{i}@x.co", "next": "/"}, headers={"CF-Connecting-IP": "6.6.6.6"}).headers.get("set-cookie", "") for i in range(6)]
    c("B7.17", "Lần thứ 6 trong 10 phút: sub_rate", "sub_rate" in rl[-1] and "sub_ok" in rl[-2], rl[-1][:60])
    r = pub.post("/api/subscribe", data={"email": "bot@x.co", "website": "http://spam", "next": "/"}, headers={"CF-Connecting-IP": "6.6.6.7"})
    c("B7.18", "Honeypot: không lưu", s.sql("select count(*) from subscribers where email='bot@x.co'")[0][0] == 0)

    # ---------- B8. Liên hệ ----------
    pg.goto(BASE + "/lien-he")
    pg.fill("input[name=name]", "Khách 2")
    pg.fill("input[name=email]", "sai")
    pg.fill("textarea[name=body]", "Câu hỏi của tôi")
    with pg.expect_navigation():
        pg.click(".btn-submit")
    c("B8.1", "Email sai: báo lỗi tại ô, giữ chữ đã nhập", "Vui lòng nhập email hợp lệ" in pg.inner_text("main") and pg.input_value("textarea[name=body]") == "Câu hỏi của tôi")
    pg.fill("input[name=email]", "khach2@qa.test")
    pg.fill("textarea[name=body]", "")
    with pg.expect_navigation():
        pg.click(".btn-submit")
    c("B8.2", "Nội dung trống: báo lỗi", "Vui lòng nhập nội dung" in pg.inner_text("main"))
    pg.fill("textarea[name=body]", "Câu hỏi của tôi\nDòng hai 😀")
    pg.locator("label.chip", has_text="Hợp tác").click()
    with pg.expect_navigation():
        pg.click(".btn-submit")
    c("B8.3", "Gửi xong: khối Đã gửi", pg.url.endswith("/lien-he") and "Đã gửi" in pg.inner_text("main"), pg.url)
    m = s.sql("select topic,name,email,body,is_read from contact_messages")
    c("B8.4", "Tin lưu đúng", m and m[0][0] == "Hợp tác" and "Dòng hai 😀" in m[0][3] and m[0][4] == 0, m)
    t = h.get("/admin").text
    c("B8.5", "Admin thấy tin chưa đọc", "chưa đọc" in t)
    c("B8.6", "Mở tin: nội dung nhiều dòng, đánh dấu đã đọc", "Dòng hai" in h.get("/admin/messages/1").text and s.sql("select is_read from contact_messages")[0][0] == 1)
    rs = [pub.post("/api/contact", data={"email": "a@x.co", "body": f"m{i}"}, headers={"CF-Connecting-IP": "6.6.7.1"}).status_code for i in range(6)]
    c("B8.7", "Liên hệ quá 5 lần: 429 có thông báo", rs[-1] == 429 and rs[-2] == 303, rs)
    pg.goto(BASE + "/lien-he")
    pg.fill("input[name=email]", "dup@qa.test")
    pg.fill("textarea[name=body]", "Bấm đúp")
    pg.dblclick(".btn-submit")
    pg.wait_for_load_state("networkidle")
    n = s.sql("select count(*) from contact_messages where email='dup@qa.test'")[0][0]
    c("B8.8", "Bấm đúp Gửi tin nhắn: 1 tin", n == 1, f"{n} tin")

    # ---------- B9. Đếm click ----------
    s.sql("update banners set views=0, clicks=0")
    c0 = s.sql("select clicks from brokers where id=?", (K[1],))[0][0]
    pg.goto(BASE + "/bonus")
    card = pg.locator("article.bcard", has_text="B-gia-900")
    with ctx.expect_page() as pop:
        card.locator("a", has_text="Nhận bonus").click()
    np = pop.value
    np.wait_for_timeout(500)  # route không chặn request sau redirect nên tab dừng ở lỗi DNS, chỉ cần biết đích
    c("B9.1", "Nhận bonus mở tab mới tới link affiliate", any("aff.example.test" in u for u in seen), seen[-3:])
    np.close()
    c("B9.2", "Click affiliate +1 đúng", s.sql("select clicks from brokers where id=?", (K[1],))[0][0] == c0 + 1)
    pg.goto(BASE + "/")
    pg.wait_for_timeout(300)
    bn = dict(s.sql("select name,views from banners"))
    c("B9.3", "Một lượt tải trang chủ: banner ngang +1; rail không tính ở màn 1440", bn["QC1"] == 1 and bn["QC2"] == 1 and bn["Rail1"] == 0, bn)
    with ctx.expect_page() as pop:
        pg.locator(".ad a").first.click()
    np = pop.value
    np.wait_for_timeout(300)
    np.close()
    bc = s.sql("select name,clicks from banners where clicks>0")
    c("B9.4", "Click quảng cáo +1 đúng banner", len(bc) == 1 and bc[0][1] == 1, bc)
    big = ctx.new_page()
    big.set_viewport_size({"width": 1700, "height": 950})
    big.goto(BASE + "/")
    big.wait_for_timeout(500)
    big.close()
    c("B9.5", "Màn 1700: rail +1 qua beacon", dict(s.sql("select name,views from banners"))["Rail1"] == 1, s.sql("select name,views from banners"))
    t = h.get("/admin/ads?tab=stats").text
    c("B9.6", "Thống kê quảng cáo hiện CTR", "%" in t)
    t = h.get("/admin").text
    stats = re.sub(r"<[^>]+>", " ", t)
    c("B9.7", "Tổng quan có click affiliate/quảng cáo 30 ngày", "Click quảng cáo" in stats and "Click affiliate" in stats)
    day = s.sql("select kind,sum(count) from click_logs group by kind")
    c("B9.8", "ClickLog theo ngày khớp", dict(day).get("ad", 0) >= 1 and dict(day).get("broker", 0) >= 1, day)
    # robot/preview: mỗi GET /go đều tính, kể cả bot, kiểm tra hành vi X-Robots-Tag
    r = pub.get(f"/go/broker/{K[0]}")
    c("B9.9", "/go có X-Robots-Tag noindex", "noindex" in r.headers.get("x-robots-tag", ""))
    c("B9.10", "Không có lỗi console/JS phía khách (bỏ qua 400/404/429 cố ý)", not [e for e in errs if "status of 4" not in e[2]], errs[:6])
    b.close()
s.stop()
R.save()
