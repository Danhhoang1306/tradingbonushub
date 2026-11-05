"""Vai A: admin dùng lần đầu từ DB rỗng, thao tác hoàn toàn bằng Chromium qua UI thật."""
import re

import httpx
from PIL import Image
from playwright.sync_api import sync_playwright

from qalib import ADMIN_EMAIL, ADMIN_PASS, BASE, WORK, Http, Report, Server, mk_banner, mk_bonus, mk_broker, mk_post

R = Report("s1_admin_first_use")
c = R.check
s = Server("admin").start()
s.cli_admin()
pub = httpx.Client(base_url=BASE, timeout=20)
A = WORK / "admin_assets"
A.mkdir(exist_ok=True)
errs = []


def img(name, size, color):
    p = A / name
    Image.new("RGB", size, color).save(p)
    return str(p)


logo = img("logo.png", (200, 200), (25, 68, 223))
cover = img("cover.jpg", (1200, 630), (2, 22, 35))
ban = img("ban.png", (970, 250), (200, 30, 30))
rail = img("rail.webp", (160, 600), (30, 160, 60))
PUB_PAGES = ["/", "/bonus", "/san", "/san/so-sanh", "/tin-tuc", "/gioi-thieu", "/gioi-thieu/cach-danh-gia", "/gioi-thieu/affiliate", "/lien-he", "/dieu-khoan", "/bao-mat"]


def flash(pg):
    el = pg.locator("[data-flash]")
    return el.first.inner_text() if el.count() else ""


def confirm(pg):
    with pg.expect_navigation():
        pg.locator("#confirm-dialog button[value=ok]").click()


def save_drawer(pg):
    with pg.expect_navigation():
        pg.click(".drawer-foot .btn-save")


def save_page(pg):
    with pg.expect_navigation():
        pg.click("#page-form button[type=submit]:visible, .form-actions button[type=submit]:visible")


def snapshot():
    out = {}
    for p in PUB_PAGES:
        t = pub.get(p).text
        out[p] = t
    return out


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(("pageerror", pg.url, str(e))))
    pg.on("console", lambda m: errs.append(("console", pg.url, m.text)) if m.type == "error" else None)
    pg.goto(BASE + "/admin")
    c("A0.1", "Vào /admin chuyển về đăng nhập", "/admin/login" in pg.url)
    pg.fill("input[name=email]", ADMIN_EMAIL)
    pg.fill("input[name=password]", ADMIN_PASS)
    with pg.expect_navigation():
        pg.click("button[type=submit]")
    c("A0.2", "Đăng nhập vào Tổng quan DB rỗng", pg.url.rstrip("/").endswith("/admin"))
    c("A0.3", "DB rỗng: public không có dữ liệu mock", all(x not in pub.get("/").text for x in ("Exness", "Vantage", "Bybit", "OKX", "VT Markets")))

    # ---------- A1. Nhập trọn một sàn ----------
    pg.goto(BASE + "/admin/brokers/new")
    pg.fill("input[name=name]", "Hải Âu Markets")
    pg.fill("input[name=tagline]", "Sàn thử nghiệm QA")
    pg.fill("textarea[name=summary]", "Đoạn giới thiệu một.\n\nĐoạn giới thiệu hai.")
    for k, v in {"license": "FCA 123", "min_deposit": "$11", "leverage": "1:777", "platforms": "MT5, cTrader", "spread": "0.2 pip", "withdrawal": "Trong 2 giờ", "founded": "2011"}.items():
        pg.fill(f"input[name={k}]", v)
    pg.fill("input[name=affiliate_url]", "https://aff.example.test/haiau?ref=1")
    pg.set_input_files("input[name=logo_path_file]", logo)
    pros = pg.locator("textarea[name=pros] ~ .lines-list")
    pros.locator("input").first.fill("Ưu điểm một")
    pg.locator("textarea[name=pros] ~ .btn-add").click()
    pros.locator("input").nth(1).fill("Ưu điểm hai")
    pg.locator("textarea[name=cons] ~ .lines-list").locator("input").first.fill("Nhược điểm một")
    acc = pg.locator("[data-rows]").filter(has=pg.locator("input[name=account_name]")).first
    acc.locator("[data-row-add]").click()
    rows = acc.locator("[data-rows-list] > [data-row]")
    rows.nth(0).locator("input[name=account_name]").fill("Standard")
    rows.nth(0).locator("input[name=account_min_deposit]").fill("$50")
    rows.nth(0).locator("input[name=account_spread]").fill("1.0")
    rows.nth(0).locator("input[name=account_commission]").fill("0")
    pay = pg.locator("[data-rows]").filter(has=pg.locator("input[name=payment_method]")).first
    if pay.locator("input[name=payment_method]").count() == 0:
        pay.locator("[data-row-add]").click()
    pay.locator("input[name=payment_method]").first.fill("Momo")
    pay.locator("input[name=payment_deposit]").first.fill("Miễn phí")
    pay.locator("input[name=payment_withdraw]").first.fill("1%")
    pay.locator("input[name=payment_time]").first.fill("5 phút")
    for sw in ("in_compare", "featured"):
        pg.locator(f"label:has(input[name={sw}])").click()
    save_drawer(pg)
    c("A1.1", "Thêm sàn: flash Đã thêm", "Đã thêm" in flash(pg), flash(pg))
    t = pub.get("/san/hai-au-markets").text
    c("A1.2", "Tổng quan sàn: đủ fact", all(x in t for x in ("FCA 123", "$11", "1:777", "MT5, cTrader", "0.2 pip", "Trong 2 giờ", "2011", "Sàn thử nghiệm QA", "Ưu điểm hai", "Nhược điểm một")))
    c("A1.3", "Logo upload hiện", re.search(r'<img src="/media/[0-9a-f]+\.png"', t))
    pg.goto(BASE + "/san/hai-au-markets")
    summ = pg.get_by_text("Đoạn giới thiệu một.").first
    css = summ.evaluate("e => getComputedStyle(e).whiteSpace")
    c("A1.5", "summary nhiều đoạn: có xuống dòng (white-space pre-line hoặc nhiều <p>)", "pre" in css or "Đoạn giới thiệu hai" not in summ.inner_text(), css)
    t = pub.get("/san/hai-au-markets?tab=accounts").text
    c("A1.6", "Tab Tài khoản & phí", "Standard" in t and "$50" in t)
    t = pub.get("/san/hai-au-markets?tab=pay").text
    c("A1.7", "Tab Nạp & rút", "Momo" in t and "5 phút" in t)
    c("A1.8", "Sàn trong /san và so sánh mặc định", "Hải Âu Markets" in pub.get("/san").text and "Hải Âu Markets" in pub.get("/san/so-sanh").text)
    c("A1.9", "/go/broker chuyển đúng link + đếm", pub.get("/go/broker/1").headers.get("location") == "https://aff.example.test/haiau?ref=1" and s.sql("select clicks from brokers")[0][0] == 1)

    # ---------- A2. Bonus ----------
    pg.goto(BASE + "/admin/bonus/new")
    pg.locator("select[name=broker_id]").select_option("1") if pg.locator("select[name=broker_id]").count() else None
    pg.locator("label:has(input[name=type][value=nodep])").click()
    pg.fill("input[name=title]", "Thưởng không cần nạp")
    pg.fill("input[name=amount]", "$30")
    pg.fill("input[name=value_num]", "30")
    pg.fill("input[name=min_deposit]", "$0")
    pg.fill("input[name=withdrawable]", "Lợi nhuận")
    pg.fill("input[name=expiry_date]", "2030-12-31")
    save_drawer(pg)
    c("A2.1", "Thêm bonus", "Đã thêm" in flash(pg), flash(pg))
    pg.goto(BASE + "/admin/bonus/new")
    pg.locator("select[name=broker_id]").select_option("1")
    pg.locator("label:has(input[name=type][value=deposit])").click()
    pg.fill("input[name=title]", "Thưởng nạp 100%")
    pg.fill("input[name=amount]", "100%")
    pg.fill("input[name=value_num]", "500")
    save_drawer(pg)
    t = pub.get("/bonus").text
    c("A2.2", "Bonus hiện ở /bonus đủ trường", all(x in t for x in ("Thưởng không cần nạp", "$30", "Lợi nhuận", "31/12/2030", "Thưởng nạp 100%", "Liên tục")))
    t = pub.get("/").text
    c("A2.3", "Trang chủ: thẻ hero nổi bật là bonus giá trị cao nhất của sàn featured", "hero-card" in t and "Thưởng nạp 100%" in t[t.find("hero-card"):t.find("hero-card") + 900])
    c("A2.4", "Trang chủ: số ưu đãi đang hoạt động 2+", "2+" in t)
    t = pub.get("/san/hai-au-markets?tab=bonus").text
    c("A2.5", "Tab Bonus sàn", "Thưởng nạp 100%" in t and "Thưởng không cần nạp" in t)

    # ---------- A3. Bài viết ----------
    pg.goto(BASE + "/admin/posts/new")
    pg.fill("input[name=title]", "Hướng dẫn nhận bonus")
    pg.fill("textarea[name=excerpt]", "Tóm tắt bài viết QA")
    pg.fill("textarea[name=body_md]", "## Bước một\n\nNội dung **đậm** và [liên kết](https://example.com).\n\n- Mục 1\n- Mục 2\n")
    pg.set_input_files("input[name=cover_path_file]", cover)
    if pg.locator("input[name=status][value=published]").count():
        pg.locator("label:has(input[name=status][value=published])").click()
    else:
        pg.locator("select[name=status]").select_option("published")
    pg.locator("label:has(input[name=show_home])").click()
    save_drawer(pg)
    c("A3.1", "Thêm bài", "Đã thêm" in flash(pg), flash(pg))
    t = pub.get("/tin-tuc/huong-dan-nhan-bonus").text
    c("A3.2", "Bài public: markdown, ảnh bìa", "<h2>Bước một</h2>" in t and "<strong>đậm</strong>" in t and re.search(r'src="/media/[0-9a-f]+\.jpg"', t))
    c("A3.3", "Bài ở /tin-tuc và trang chủ", "Hướng dẫn nhận bonus" in pub.get("/tin-tuc").text and "Hướng dẫn nhận bonus" in pub.get("/").text)

    # ---------- A4. Banner ----------
    for name, place, f in (("Banner sau bonus", "after-bonus", ban), ("Banner trước tin", "before-blog", ban), ("Rail trái", "rail-left", rail), ("Rail phải", "rail-right", rail)):
        pg.goto(BASE + "/admin/ads/new")
        pg.fill(".drawer input[name=name]", name)
        pg.locator("select[name=broker_id]").select_option("1")
        if pg.locator(f"input[name=placement][value={place}]").count():
            pg.locator(f"label:has(input[name=placement][value={place}])").click()
        else:
            pg.locator("select[name=placement]").select_option(place)
        pg.set_input_files("input[name=image_path_file]", f)
        save_drawer(pg)
        c(f"A4.{place}", f"Thêm banner {place}", "Đã thêm" in flash(pg), flash(pg))
    t = pub.get("/").text
    c("A4.1", "4 banner lên trang chủ", all(f"/go/ad/{i}" in t for i in (1, 2, 3, 4)))
    pg2 = ctx.new_page()
    pg2.set_viewport_size({"width": 1700, "height": 950})
    pg2.goto(BASE + "/")
    pg2.wait_for_timeout(500)
    c("A4.2", "Màn ≥1572px: rail hiển thị thật và beacon đếm view", pg2.locator(".rail, [data-view-url]").first.is_visible() and s.sql("select views from banners where placement='rail-left'")[0][0] >= 1)
    pg2.close()

    # ---------- A5. Lưu không đổi gì ở mọi tab: public y nguyên ----------
    HOME_TABS = ("sections", "hero", "about", "why", "types", "contact", "menu")
    PAGE_TABS = ("bonus", "san", "compare", "tin", "gioithieu", "method", "affiliate", "lienhe", "terms", "privacy", "system")
    SET_TABS = ("general", "seo", "social", "tracking")
    tabs = [("home", t) for t in HOME_TABS] + [("pages", t) for t in PAGE_TABS] + [("settings", t) for t in SET_TABS]
    before = snapshot()
    for area, t in tabs:
        pg.goto(f"{BASE}/admin/{area}?tab={t}")
        try:
            save_page(pg)
            f = flash(pg)
        except Exception as e:
            f = f"LỖI {e}"
        c(f"A5.{area}.{t}", f"Lưu nguyên trạng {area}/{t}: Đã lưu", "Đã lưu" in f, f"{f!r} url={pg.url}")
    after = snapshot()
    diffs = [p for p in PUB_PAGES if before[p] != after[p]]
    detail = ""
    if diffs:
        import difflib
        d = list(difflib.unified_diff(before[diffs[0]].splitlines(), after[diffs[0]].splitlines(), lineterm="", n=0))[:12]
        detail = f"{diffs}: " + " | ".join(x[:140] for x in d)
    c("A5.0", "Sau khi lưu nguyên trạng mọi tab, HTML public không đổi", not diffs, detail)

    # ---------- A6. Marker vào từng ô của từng tab, rồi tìm trên public ----------
    markers = []
    idx = [0]

    def marker(prefix="ZQ"):
        idx[0] += 1
        return f"{prefix}{idx[0]}Z"

    FILL = """() => [...document.querySelectorAll('#page-form input, #page-form textarea')].map((e, i) => {
        e.dataset.qa = i; const v = e.offsetParent !== null || e.getClientRects().length > 0;
        return {i, name: e.name, type: e.type, tag: e.tagName, visible: v, val: e.value};
    })"""
    # thêm dòng lặp để có ô trống cho social
    bad_save = []
    unnamed = [0]
    for area, t in tabs:
        if t == "tracking" or t == "sections" and False:
            continue
        pg.goto(f"{BASE}/admin/{area}?tab={t}")
        if t == "social":
            pg.locator("[data-row-add]").first.click()
        fields = pg.evaluate(FILL)
        for f in fields:
            if not f["visible"] or f["type"] in ("hidden", "file", "checkbox", "radio", "search", "submit", "date") or not f["name"] and f["tag"] == "INPUT" and False:
                continue
            n = f["name"] or "(dòng)"
            if n == "csrf_token":
                continue
            m = marker()
            if "email" in n:
                val = m.lower() + "@qa.test"
            elif n in ("menu_url",):
                val = "/" + m.lower()
            elif n == "social_url":
                val = f"https://{m.lower()}.test/"
            elif n == "footer_col_links":
                val = f"Nhãn{m} | /{m.lower()}"
            elif n.endswith("_path") or re.fullmatch(r"(image(_\d)?|\w+_image|og_image)", n):
                continue
            else:
                val = m
            if t == "menu" and not f["name"]:  # dòng link footer: cặp (nhãn, url) không có name, JS gộp vào footer_col_links
                unnamed[0] += 1
                if unnamed[0] % 2 == 0:
                    val = "/" + m.lower()
            sel = f'[data-qa="{f["i"]}"]'
            try:
                pg.fill(sel, val)
                markers.append((f"{area}/{t}", n, m if "email" not in n else m.lower()))
            except Exception as e:
                bad_save.append((area, t, n, str(e)[:80]))
        files = pg.locator("#page-form input[type=file]")
        for i in range(files.count()):
            colour = (idx[0] * 7 % 255, 90, 120)
            idx[0] += 1
            files.nth(i).set_input_files(img(f"f{idx[0]}.png", (120, 120), colour))
        try:
            save_page(pg)
            if "Đã lưu" not in flash(pg):
                bad_save.append((area, t, "flash", flash(pg), pg.locator(".field-error, .alert-error").all_inner_texts()[:3]))
        except Exception as e:
            bad_save.append((area, t, "save", str(e)[:120]))
    c("A6.0", f"Lưu {len(markers)} ô qua UI không lỗi", not bad_save, bad_save[:6])

    # thu thập mọi trang public (cả trang trạng thái)
    h = Http()
    corpus = {}
    for p_ in PUB_PAGES + ["/san/hai-au-markets", "/san/hai-au-markets?tab=bonus", "/tin-tuc/huong-dan-nhan-bonus", "/khong-co-trang", "/xac-nhan/sai"]:
        corpus[p_] = pub.get(p_).text
    r = pub.post("/api/subscribe", data={"email": "s@qa.test", "next": "/"}, headers={"CF-Connecting-IP": "7.7.7.1"})
    ck = {"tbh_flash": "sub_ok"}
    corpus["home+sub_ok"] = httpx.get(BASE + "/", cookies=ck).text
    tk = s.tokens("s@qa.test")[-1]
    corpus["ask_confirm"] = pub.get(f"/xac-nhan/{tk}").text
    corpus["ask_unsub"] = pub.get(f"/huy-dang-ky/{tk}").text
    corpus["confirm"] = pub.post(f"/xac-nhan/{tk}").text
    corpus["unsub"] = pub.post(f"/huy-dang-ky/{tk}").text
    corpus["contact_ok"] = httpx.get(BASE + "/lien-he", cookies={"tbh_flash": "contact_ok"}).text
    corpus["500"] = pub.get("/go/broker/99999999999999999999999").text
    all_html = "\n".join(corpus.values())
    missing = [(a, n, m) for a, n, m in markers if m not in all_html and m.lower() not in all_html]
    missing = [x for x in missing if x[1] != "ads_note"]  # ads_note chỉ in ở rail không có ảnh; rail ở đây có ảnh
    for mi in missing:
        print("     KHÔNG THẤY:", mi, flush=True)
    c("A6.1", f"Mọi ô đã sửa xuất hiện ở public ({len(markers)} ô)", not missing, missing[:30])
    media_refs = set(re.findall(r"/media/[0-9a-f]{32}\.\w+", all_html))
    db_media = {x[0] for x in s.sql("select path from media_files")}
    settings_media = [m for m in db_media if m in "\n".join(str(x[0]) for x in s.sql("select value from settings"))]
    not_seen = [m for m in settings_media if m not in media_refs]
    c("A6.2", f"Mọi ảnh đặt trong Trang chủ/Trang/Cài đặt hiện ở public ({len(settings_media)} ảnh)", not not_seen, not_seen[:6])
    if "home+sub_ok" in corpus:
        pass

    # ---------- A7. Sửa, ẩn, xóa ----------
    pg.goto(BASE + "/admin/bonus/1/edit")
    pg.fill("input[name=title]", "Thưởng đã sửa tên")
    save_drawer(pg)
    t = pub.get("/bonus").text
    c("A7.1", "Sửa bonus: public đổi", "Thưởng đã sửa tên" in t and "Thưởng không cần nạp" not in t)
    pg.goto(BASE + "/admin/bonus")
    row = pg.locator(".t-row", has_text="Thưởng đã sửa tên")
    with pg.expect_navigation():
        row.locator("button.switch").first.click()
    c("A7.2", "Ẩn bonus: biến khỏi public", "Thưởng đã sửa tên" not in pub.get("/bonus").text and "Thưởng đã sửa tên" not in pub.get("/").text)
    row = pg.locator(".t-row", has_text="Thưởng đã sửa tên")
    row.locator("button:has-text('Xóa'), a:has-text('Xóa')").first.click() if row.locator("button:has-text('Xóa')").count() else None
    if pg.locator("#confirm-dialog[open]").count():
        confirm(pg)
    else:
        pg.goto(BASE + "/admin/bonus/1/edit")
        pg.locator(".drawer button:has-text('Xóa')").first.click()
        confirm(pg)
    c("A7.3", "Xóa bonus qua hộp xác nhận", s.sql("select count(*) from bonuses where id=1")[0][0] == 0)
    pg.goto(BASE + "/admin/posts/1/edit")
    if pg.locator("input[name=status][value=draft]").count():
        pg.locator("label:has(input[name=status][value=draft])").click()
    else:
        pg.locator("select[name=status]").select_option("draft")
    save_drawer(pg)
    c("A7.4", "Chuyển bài về nháp: 404, khỏi danh sách, sitemap, trang chủ", pub.get("/tin-tuc/huong-dan-nhan-bonus").status_code == 404 and "huong-dan-nhan-bonus" not in pub.get("/sitemap.xml").text and "huong-dan-nhan-bonus" not in pub.get("/tin-tuc").text and "huong-dan-nhan-bonus" not in pub.get("/").text)
    pg.goto(BASE + "/admin/ads")
    with pg.expect_navigation():
        pg.locator("button.switch").first.click()
    live = s.sql("select id from banners where is_active=0")
    c("A7.5", "Tắt banner: /go/ad 404, không còn ở trang chủ", len(live) == 1 and pub.get(f"/go/ad/{live[0][0]}").status_code == 404 and f"/go/ad/{live[0][0]}\"" not in pub.get("/").text)
    # chặn xóa ảnh đang dùng
    pg.goto(BASE + "/admin/media")
    dis = pg.locator("button:has-text('Xóa'):disabled").count()
    c("A7.6", "Thư viện ảnh: ảnh đang dùng khóa nút Xóa", dis >= 1, dis)
    mid = s.sql("select id, path from media_files limit 1")[0]
    # sửa tên sàn
    pg.goto(BASE + "/admin/brokers/1/edit")
    pg.fill("input[name=name]", "Hải Âu Mới")
    save_drawer(pg)
    c("A7.7", "Sửa tên sàn: public đổi, slug giữ hay đổi đều không 404 tại link đang hiển thị", "Hải Âu Mới" in pub.get("/san").text)
    slug = s.sql("select slug from brokers where id=1")[0][0]
    c("A7.8", "Sửa tên sàn nhưng ô Slug giữ nguyên: slug không đổi (link cũ còn sống)", slug == "hai-au-markets", slug)
    pg.goto(BASE + "/admin/brokers/1/edit")
    pg.locator(".drawer button:has-text('Xóa')").first.click()
    confirm(pg)
    t = pub.get("/san").text
    c("A7.9", "Xóa sàn: biến khỏi /san, 404 trang sàn, /go 404", "Hải Âu Mới" not in t and pub.get(f"/san/{slug}").status_code == 404 and pub.get("/go/broker/1").status_code == 404)

    # ---------- A8. Bấm hai lần ----------
    h = Http().login()
    mk_broker(h, "Sàn Đúp")
    kid = s.sql("select id from brokers where name='Sàn Đúp'")[0][0]
    pg.goto(BASE + "/admin/bonus/new")
    pg.locator("select[name=broker_id]").select_option(str(kid))
    pg.fill("input[name=title]", "Bonus bấm đúp")
    pg.dblclick(".drawer-foot .btn-save")
    pg.wait_for_load_state("networkidle")
    n = s.sql("select count(*) from bonuses where title='Bonus bấm đúp'")[0][0]
    c("A8.1", "Bấm đúp nút Lưu bonus: chỉ tạo 1 bản ghi", n == 1, f"{n} bản ghi")
    for i in range(2):
        pub.post("/api/subscribe", data={"email": f"cf{i}@qa.test", "next": "/"}, headers={"CF-Connecting-IP": f"7.7.8.{i}"})
        pub.post("/xac-nhan/" + s.tokens(f"cf{i}@qa.test")[-1])
    pg.goto(BASE + "/admin/subscribers?tab=mail")
    pg.fill("input[name=subject]", "Tin QA bấm đúp")
    pg.fill("textarea[name=body]", "Nội dung")
    pg.wait_for_timeout(300)
    send = pg.locator("button[name=action][value=send]")
    send.click()
    pg.wait_for_selector("#confirm-dialog[open]")
    pg.locator("#confirm-dialog button[value=ok]").dblclick()
    pg.wait_for_timeout(1200)
    n = s.sql("select count(*) from campaigns where subject='Tin QA bấm đúp'")[0][0]
    c("A8.2", "Bấm đúp xác nhận gửi email: chỉ gửi 1 chiến dịch", n == 1, f"{n} chiến dịch")
    c("A8.3", "Không có lỗi console/JS khi admin thao tác", not [e for e in errs if "favicon" not in e[2]], errs[:6])
    b.close()
s.stop()
R.save()
