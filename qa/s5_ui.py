"""Vai E: giao diện. 5 khổ màn, cuộn ngang, CSP/console, bàn phím + focus, tương phản, chuỗi dài. Ảnh chụp ở QA_WORK/shots."""
import re

import httpx
from PIL import Image
from playwright.sync_api import sync_playwright

from qalib import ADMIN_EMAIL, ADMIN_PASS, BASE, WORK, Http, Report, Server, mk_banner, mk_bonus, mk_broker, mk_post, png_bytes

R = Report("s5_ui")
c = R.check
SHOTS = WORK / "shots"
SHOTS.mkdir(parents=True, exist_ok=True)
SIZES = [(360, 740), (390, 844), (768, 1024), (1440, 900), (1920, 1080)]
NORMAL = "Chương trình khuyến mãi dành cho khách hàng mới của sàn giao dịch quốc tế hàng đầu Việt Nam năm 2026 "  # có dấu cách
STRESS = "Khôngcókhoảngtrắngrấtrấtrấtdàiđểkiểmtratràn" * 4  # một từ liền 170+ ký tự


def seed(mode):
    global s, h, mp, k1, k2, k3, W
    W = (NORMAL * 3)[:250].strip() if mode == "normal" else STRESS
    s = Server(f"ui_{mode}").start()
    s.cli_admin()
    h = Http().login()
    h.post("/admin/media/upload", {"alt": "ảnh"}, files={"files": ("a.png", png_bytes(300, 300), "image/png")})
    mp = s.sql("select path from media_files")[0][0]
    n120 = W[:118].strip()
    mk_broker(h, "Sàn Bình Thường", in_compare="1", featured="1", logo_path=mp)
    mk_broker(h, n120, slug="san-dai", tagline=W, summary=W, license=W, platforms=W, min_deposit=W[:60], leverage=W[:60], spread=W[:60], withdrawal=W[:118], founded="2010", in_compare="1", pros=W, cons=W)
    mk_broker(h, "Sàn Crypto", kind="crypto", in_compare="1")
    k1, k2, k3 = [x[0] for x in s.sql("select id from brokers order by id")]
    h.post(f"/admin/brokers/{k2}/edit", [("name", n120), ("slug", "san-dai"), ("kind", "forex"), ("is_active", "1"), ("in_compare", "1"), ("tagline", W), ("summary", W), ("license", W), ("founded", "2010"),
                                        ("affiliate_url", "https://aff.example.test/x"), ("account_name", W[:200]), ("account_min_deposit", W[:200]), ("account_spread", W[:200]), ("account_commission", W[:200]),
                                        ("payment_method", W[:200]), ("payment_deposit", W[:200]), ("payment_withdraw", W[:200]), ("payment_time", W[:200]), ("pros", W), ("cons", W)])
    mk_bonus(h, k1, "Bonus thường có tiêu đề bình thường", value_num="100")
    mk_bonus(h, k2, W, amount=W[:60], min_deposit=W[:60], withdrawable=W[:60], value_num="200", expiry_date="2030-01-01")
    mk_bonus(h, k3, "Bonus crypto", type="crypto", value_num="50")
    for i in range(14):
        mk_post(h, f"Bài viết số {i}" if i else W[:255], slug=f"bai-{i}", excerpt=W[:500] if i == 0 else "Tóm tắt", body_md=f"## {W}\n\n{W}\n\n| {W} | B |\n|---|---|\n| {W} | 2 |\n\n`{W}`\n\n[{W}](https://example.com/{W.replace(' ', '-')})\n\n![a]({mp})\n" if i == 0 else "Nội dung", cover_path=mp if i % 2 else "", category="Tin sàn")
    mk_banner(h, "QC ngang", placement="after-bonus", broker_id=k1, target_url="https://aff.example.test/1", image_path=mp)
    mk_banner(h, n120, placement="before-blog", broker_id=k2, target_url="https://aff.example.test/2")
    mk_banner(h, "Rail", placement="rail-left", broker_id=k1, target_url="https://aff.example.test/3")
    h.post("/admin/settings/general", {"site_name": "TradingBonusHub", "contact_email": "lien.he.cham.soc.khach.hang@qa.test", "partner_email": "b@qa.test", "telegram": "https://t.me/tradingbonushub_vietnam"})
    httpx.post(BASE + "/api/contact", data={"topic": "Hợp tác", "name": W[:118], "email": "x@x.co", "body": W}, headers={"CF-Connecting-IP": "5.5.5.1"})
    httpx.post(BASE + "/api/subscribe", data={"name": W[:118], "email": "mot.dia.chi.email.kha.dai.cua.khach.hang@gmail.test", "next": "/"}, headers={"CF-Connecting-IP": "5.5.5.2"})
    h.post("/admin/subscribers/mail", {"subject": W[:200], "body": W, "action": "draft"})


seed("normal")

PUBLIC = ["/", "/bonus", "/san", "/san/so-sanh", "/san/so-sanh?ids=1,2,3", "/san/san-dai", "/san/san-dai?tab=bonus", "/san/san-dai?tab=accounts", "/san/san-dai?tab=pay", "/san/san-binh-thuong",
          "/tin-tuc", "/tin-tuc/bai-0", "/tin-tuc/bai-1", "/gioi-thieu", "/gioi-thieu/cach-danh-gia", "/gioi-thieu/affiliate", "/lien-he", "/dieu-khoan", "/bao-mat", "/khong-co", "/xac-nhan/x"]
ADMIN = ["/admin", "/admin/bonus", "/admin/bonus/new", "/admin/brokers", "/admin/brokers?tab=links", "/admin/brokers/2/edit", "/admin/ads", "/admin/ads?tab=stats", "/admin/posts", "/admin/posts/new",
         "/admin/home?tab=sections", "/admin/home?tab=hero", "/admin/home?tab=menu", "/admin/pages?tab=gioithieu", "/admin/pages?tab=system", "/admin/media", "/admin/subscribers", "/admin/subscribers?tab=mail",
         "/admin/messages", "/admin/messages/1", "/admin/settings?tab=general", "/admin/settings?tab=users"]
OVER = """() => { const d = document.documentElement; const over = d.scrollWidth - d.clientWidth;
  if (over <= 0) return {over: 0, who: []};
  const who = [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > d.clientWidth + 1 && getComputedStyle(e).position !== 'fixed' && !e.closest('[hidden]')).slice(0, 5)
     .map(e => e.tagName + '.' + (e.className.baseVal ?? e.className)); return {over, who}; }"""
CONTRAST = r"""() => {
  const parse = s => { const m = s.match(/[\d.]+/g).map(Number); return {r:m[0], g:m[1], b:m[2], a: m.length>3 ? m[3] : 1}; };
  const lum = c => { const f = [c.r,c.g,c.b].map(v => { v/=255; return v<=0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055,2.4); }); return 0.2126*f[0]+0.7152*f[1]+0.0722*f[2]; };
  const out = [];
  for (const e of document.querySelectorAll('body *')) {
    if (!e.childNodes.length || ![...e.childNodes].some(n => n.nodeType===3 && n.textContent.trim())) continue;
    const st = getComputedStyle(e); const rect = e.getBoundingClientRect();
    if (rect.width<2 || rect.height<2 || st.visibility==='hidden' || st.opacity==='0') continue;
    let p = e, bg = null, img = false;
    while (p) { const s = getComputedStyle(p); if (s.backgroundImage !== 'none') { img = true; break; }
      const c = parse(s.backgroundColor); if (c.a >= 0.99) { bg = c; break; } if (c.a > 0) { img = true; break; } p = p.parentElement; }
    if (!bg && !img) bg = {r:255,g:255,b:255,a:1};
    if (img || !bg) continue;
    const fg = parse(st.color); if (fg.a < 1) { fg.r = fg.r*fg.a+bg.r*(1-fg.a); fg.g = fg.g*fg.a+bg.g*(1-fg.a); fg.b = fg.b*fg.a+bg.b*(1-fg.a); }
    const L1 = lum(fg), L2 = lum(bg); const ratio = (Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);
    const size = parseFloat(st.fontSize), bold = parseInt(st.fontWeight)>=700; const need = (size>=24 || (size>=18.66 && bold)) ? 3 : 4.5;
    if (ratio < need) out.push({txt: e.textContent.trim().slice(0,30), cls: String(e.className).slice(0,40), ratio: +ratio.toFixed(2), size, col: st.color});
  } return out.slice(0,40); }"""


def block(route):
    u = route.request.url
    if "fonts.g" in u:
        return route.fulfill(status=200, body="", content_type="text/css")
    if "example.test" in u:
        return route.fulfill(status=200, body="ok")
    return route.continue_()


errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    def sweep(tag):
        for (w, hh) in SIZES:
            ctx = b.new_context(viewport={"width": w, "height": hh})
            ctx.route("**/*", block)
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errs.append((w, pg.url, str(e))))
            pg.on("console", lambda m: errs.append((w, pg.url, m.text)) if m.type in ("error", "warning") and "preload" not in m.text else None)
            over = []
            for u in PUBLIC:
                pg.goto(BASE + u)
                r = pg.evaluate(OVER)
                if r["over"] > 0:
                    over.append((u, r["over"], r["who"][:3]))
                if w in (360, 1440) and u in ("/", "/bonus", "/san/san-dai", "/san/so-sanh?ids=1,2,3", "/tin-tuc/bai-0", "/lien-he"):
                    pg.screenshot(path=str(SHOTS / f"{tag}_pub_{w}_{re.sub(r'[^a-z0-9]+', '_', u)}.png"), full_page=True)
            c(f"E1.{tag}.{w}", f"[{tag}] Public {w}px: không cuộn ngang ({len(PUBLIC)} trang, có chuỗi dài)", not over, over[:6])
            pg.goto(BASE + "/admin/login")
            pg.fill("input[name=email]", ADMIN_EMAIL)
            pg.fill("input[name=password]", ADMIN_PASS)
            with pg.expect_navigation():
                pg.click("button[type=submit]")
            over = []
            for u in ADMIN:
                pg.goto(BASE + u)
                r = pg.evaluate(OVER)
                if r["over"] > 0:
                    over.append((u, r["over"], r["who"][:3]))
                if w in (360, 1440) and u in ("/admin", "/admin/brokers", "/admin/home?tab=hero", "/admin/bonus/new"):
                    pg.screenshot(path=str(SHOTS / f"{tag}_adm_{w}_{re.sub(r'[^a-z0-9]+', '_', u)}.png"), full_page=True)
            c(f"E2.{tag}.{w}", f"[{tag}] Admin {w}px: không cuộn ngang ({len(ADMIN)} trang)", not over, over[:6])
            ctx.close()

    sweep("normal")
    real = [e for e in errs if "status of 404" not in e[2]]
    c("E3.1", "CSP thật: không lỗi console/CSP ở mọi trang, mọi khổ", not real, list({(e[1].replace(BASE, ""), e[2][:120]) for e in real})[:8])

    # ---------- Bàn phím + focus ----------
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    ctx.route("**/*", block)
    pg = ctx.new_page()
    FOCUS = """() => { const e = document.activeElement; const s = getComputedStyle(e);
       return {tag: e.tagName, cls: String(e.className).slice(0,40), txt: (e.textContent||e.name||'').trim().slice(0,24), outline: s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0, shadow: s.boxShadow !== 'none'}; }"""
    for u in ("/", "/bonus", "/lien-he", "/san/so-sanh"):
        pg.goto(BASE + u)
        none, seen = [], 0
        for i in range(30):
            pg.keyboard.press("Tab")
            r = pg.evaluate(FOCUS)
            if r["tag"] == "BODY":
                continue
            seen += 1
            if not r["outline"] and not r["shadow"]:
                none.append(r)
        c(f"E4.{u}", f"{u}: mọi phần tử Tab tới có vòng focus nhìn thấy", seen > 3 and not none, none[:4])
    pg.goto(BASE + "/")
    pg.keyboard.press("Tab")
    r = pg.evaluate(FOCUS)
    c("E4.s", "Tab đầu tiên là link bỏ qua tới nội dung", "bỏ qua" in r["txt"].lower() or "nội dung" in r["txt"].lower(), r)
    pg.goto(BASE + "/")
    pg.locator("[data-type-tab]").first.focus()
    pg.keyboard.press("ArrowDown")
    c("E4.t", "Tab Loại bonus chuyển bằng phím mũi tên", pg.locator("[data-type-tab]").nth(1).get_attribute("aria-selected") == "true")
    m = b.new_context(viewport={"width": 390, "height": 844})
    m.route("**/*", block)
    mp_ = m.new_page()
    mp_.goto(BASE + "/bonus")
    tog = mp_.locator("[data-nav-toggle]").first
    tog.focus()
    mp_.keyboard.press("Enter")
    mp_.wait_for_timeout(150)
    c("E4.m1", "Menu mobile mở bằng Enter, aria-expanded true", tog.get_attribute("aria-expanded") == "true")
    box = mp_.locator("nav a:visible").count()
    c("E4.m2", "Menu mobile hiện link", box >= 4, box)
    mp_.keyboard.press("Escape")
    mp_.wait_for_timeout(100)
    c("E4.m3", "Esc đóng menu mobile", tog.get_attribute("aria-expanded") == "false", tog.get_attribute("aria-expanded"))
    m.close()
    # admin
    pg.goto(BASE + "/admin/login")
    pg.fill("input[name=email]", ADMIN_EMAIL)
    pg.fill("input[name=password]", ADMIN_PASS)
    with pg.expect_navigation():
        pg.keyboard.press("Enter")
    c("E5.1", "Enter ở ô mật khẩu đăng nhập được", pg.url.rstrip("/").endswith("/admin"), pg.url)
    pg.goto(BASE + "/admin/bonus/new")
    active = pg.evaluate("() => document.activeElement.tagName + ':' + (document.activeElement.name||'')")
    c("E5.2", "Mở drawer: focus vào trong drawer", pg.evaluate("() => !!document.activeElement.closest('.drawer')"), active)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(300)
    c("E5.3", "Esc đóng drawer", "/admin/bonus/new" not in pg.url, pg.url)
    pg.goto(BASE + "/admin/brokers/1/edit")
    pg.locator(".drawer button:has-text('Xóa')").first.focus()
    pg.keyboard.press("Enter")
    pg.wait_for_selector("#confirm-dialog[open]")
    infoc = pg.evaluate("() => !!document.activeElement.closest('#confirm-dialog')")
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(150)
    c("E5.4", "Hộp xác nhận: focus vào hộp, Esc hủy, không xóa", infoc and pg.locator("#confirm-dialog[open]").count() == 0 and s.sql("select count(*) from brokers")[0][0] == 3)
    # ảnh không có alt
    miss = {}
    for u in PUBLIC[:12]:
        pg.goto(BASE + u)
        n = pg.evaluate("""() => [...document.querySelectorAll('img')].filter(i => !i.hasAttribute('alt')).length""")
        one = pg.evaluate("() => document.querySelectorAll('h1').length")
        lang = pg.evaluate("() => document.documentElement.lang")
        if n or one != 1 or lang != "vi":
            miss[u] = (n, one, lang)
    c("E6.1", "Mọi ảnh có alt, đúng 1 <h1>, lang=vi", not miss, miss)
    # tương phản
    low = {}
    for u in PUBLIC[:4] + ["/san/san-binh-thuong", "/tin-tuc/bai-1", "/gioi-thieu", "/lien-he", "/khong-co"]:
        pg.goto(BASE + u)
        for x in pg.evaluate(CONTRAST):
            low.setdefault((x["cls"], x["col"], x["ratio"]), (u, x["txt"], x["size"]))
    for u in ("/admin", "/admin/bonus", "/admin/brokers", "/admin/home?tab=hero", "/admin/settings?tab=users"):
        pg.goto(BASE + u)
        for x in pg.evaluate(CONTRAST):
            low.setdefault((x["cls"], x["col"], x["ratio"]), (u, x["txt"], x["size"]))
    for k, v in sorted(low.items(), key=lambda kv: kv[0][2])[:30]:
        print("     tương phản thấp:", k, v, flush=True)
    c("E7.1", "Tương phản WCAG AA", not low, f"{len(low)} kiểu chữ dưới ngưỡng")
    s.stop()
    errs.clear()
    seed("stress")
    sweep("stress")
    b.close()
s.stop()
R.save()
