"""Vòng 3: (A) đối chiếu chức năng với 2e4229e bằng cách crawl form + link của cả hai bản, (B) bulk save /admin/ads/bulk,
/admin/brokers/links, (C) bảo mật route/form mới, (D) production + console, (E) chức năng dời vào drawer dùng được,
(F) nâng cấp DB tạo bằng 2e4229e. Cổng 8014. Không đụng cổng 8000, data/app.db, .env."""
import email
import email.policy
import io
import json
import re
import shutil
import sqlite3
import subprocess
import tarfile
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit

import httpx
from playwright.sync_api import sync_playwright

from qalib import (OPEN_DETAILS, ADMIN_EMAIL, ADMIN_PASS, BASE, EDITOR_EMAIL, EDITOR_PASS, PORT, PY, RESULTS, ROOT, WORK, Http, Report, Server, admin_routes,
                   mk_banner, mk_bonus, mk_broker, mk_post, png_bytes, prod_env)

R = Report("s11_round3")
c = R.check
pub = httpx.Client(base_url=BASE, timeout=30)
OLD_REV = "2e4229e"
XSS = "\"'><img src=x onerror=__xss=1><svg/onload=__xss=1>"
FONTS = lambda r: r.fulfill(status=200, body="", content_type="text/css") if "fonts.g" in r.request.url else (r.fulfill(status=200, body="ok") if "example.test" in r.request.url else r.continue_())


def extract(rev, dest):
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    tar = subprocess.run(["git", "archive", rev], cwd=ROOT, capture_output=True, check=True).stdout
    tarfile.open(fileobj=io.BytesIO(tar)).extractall(dest, filter="data")


def flash(r):
    m = re.search(r"tbh_flash=(\w+)", r.headers.get("set-cookie", ""))
    return m.group(1) if m else ""


class Crawl(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms, self.links, self.cur, self.orphans = {}, set(), None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self.cur = norm(a.get("action") or "(self)") if (a.get("method") or "").lower() == "post" else None
            if self.cur:
                self.forms.setdefault(self.cur, set())
                if a.get("id"):
                    self.ids = getattr(self, "ids", {}) | {a["id"]: self.cur}
        elif tag in ("input", "textarea", "select", "button") and a.get("name"):
            if a.get("form"):
                self.orphans.append((a["form"], a["name"]))
            elif self.cur:
                self.forms[self.cur].add(norm_field(a["name"]))
        elif tag == "a" and a.get("href"):
            self.links.add(norm(a["href"]))

    def handle_endtag(self, tag):
        if tag == "form":
            self.cur = None

    def finish(self):
        for fid, name in self.orphans:
            if fid in getattr(self, "ids", {}):
                self.forms[self.ids[fid]].add(norm_field(name))
        return self


def norm(u):
    u = re.sub(r"/\d+(?=/|$|\?)", "/{id}", u)
    u = re.sub(r"draft=\d+", "draft={id}", u)
    return re.sub(r"/media/[0-9a-f]{32}\.\w+", "/media/{file}", u)


def norm_field(n):
    return re.sub(r"_\d+$", "_{id}", n)


def seed(s):
    s.cli_admin()
    s.cli_admin(EDITOR_EMAIL, EDITOR_PASS, "editor")
    h = Http().login()
    h.post("/admin/media/upload", {"alt": "ảnh"}, files={"files": ("a.png", png_bytes(), "image/png")})
    mp = s.sql("select path from media_files")[0][0]
    mk_broker(h, "Sàn Một", in_compare="1", featured="1")
    mk_broker(h, "Sàn Hai", kind="crypto")
    mk_bonus(h, 1, "Bonus Một", expiry_date="2030-01-01")
    mk_bonus(h, 2, "Bonus Hai", type="crypto")
    mk_post(h, "Bài Một", cover_path=mp)
    mk_post(h, "Bài Nháp", status="draft")
    mk_banner(h, "QC Một", broker_id=1, image_path=mp)
    pub.post("/api/contact", data={"topic": "Hợp tác", "name": "K", "email": "k@qa.test", "body": "Xin chào"}, headers={"CF-Connecting-IP": "9.2.0.1"})
    for i in range(2):
        s.sql("insert into subscribers(name,email,interests,status,token,confirm_count,created_at,updated_at) values('K',?,'[]','confirmed',?,0,'2026-01-01 00:00:00','2026-01-01 00:00:00')", (f"u{i}@qa.test", f"tok{i}"))
    h.post("/admin/subscribers/mail", {"subject": "Nháp", "body": "x", "action": "draft"})
    return h


PAGES = ["/admin", "/admin/bonus", "/admin/bonus?tab=exp", "/admin/bonus/new", "/admin/bonus/1/edit", "/admin/brokers", "/admin/brokers?tab=links", "/admin/brokers/new", "/admin/brokers/1/edit",
         "/admin/ads", "/admin/ads?tab=stats", "/admin/ads/new", "/admin/ads/1/edit", "/admin/posts", "/admin/posts?tab=draft", "/admin/posts/new", "/admin/posts/1/edit",
         "/admin/media", "/admin/subscribers", "/admin/subscribers?tab=mail", "/admin/subscribers?tab=mail&draft=1", "/admin/messages", "/admin/messages/1", "/admin/home?tab=sections", "/admin/home?tab=hero",
         "/admin/home?tab=about", "/admin/home?tab=why", "/admin/home?tab=types", "/admin/home?tab=contact", "/admin/home?tab=menu", "/admin/pages?tab=bonus", "/admin/pages?tab=gioithieu", "/admin/pages?tab=lienhe",
         "/admin/pages?tab=terms", "/admin/pages?tab=system", "/admin/settings?tab=general", "/admin/settings?tab=brand", "/admin/settings?tab=seo", "/admin/settings?tab=social", "/admin/settings?tab=tracking", "/admin/settings?tab=users"]
PUBLIC = ["/", "/bonus", "/san", "/san/so-sanh", "/san/san-mot", "/san/san-mot?tab=bonus", "/tin-tuc", "/tin-tuc/bai-mot", "/gioi-thieu", "/lien-he"]


def inventory(s, h):
    forms, links = {}, set()
    for p in PAGES + PUBLIC:
        r = h.get(p)
        if r.status_code != 200:
            continue
        cr = Crawl()
        cr.feed(r.text)
        cr.finish()
        for k, v in cr.forms.items():
            forms.setdefault(k, set()).update(v)
        links |= {x for x in cr.links if x.startswith("/") or x.startswith("#") or x.startswith("mailto")}
    return forms, links, {(p, m) for p, ms in admin_routes(s.env) for m in ms if m in ("get", "post")}


# =========== A. Đối chiếu chức năng với bản trước ===========
OLD = WORK / "code_prev"
extract(OLD_REV, OLD)
so = Server("par_old")
so.cwd = OLD
so.start()
ho = seed(so)
fo, lo, _ = inventory(so, ho)
so.stop()
sn = Server("par_new").start()
hn = seed(sn)
fn, ln, routes = inventory(sn, hn)
lost_forms = sorted(set(fo) - set(fn))
lost_fields = {k: sorted(fo[k] - fn[k]) for k in fo if k in fn and fo[k] - fn[k]}
lost_links = sorted(x for x in lo - ln)
new_forms = sorted(set(fn) - set(fo))
RESULTS.mkdir(parents=True, exist_ok=True)
(RESULTS / "s11_parity.json").write_text(json.dumps({"lost_forms": lost_forms, "lost_fields": lost_fields, "lost_links": lost_links, "new_forms": new_forms, "new_links": sorted(ln - lo)}, ensure_ascii=False, indent=1), encoding="utf-8")
print("     form mất:", lost_forms, flush=True)
print("     trường mất:", lost_fields, flush=True)
print("     link mất:", lost_links, flush=True)
print("     form mới:", new_forms, flush=True)
print("     link mới:", sorted(ln - lo), flush=True)
c("A1", "Mọi form POST còn trên UI (lưu từng dòng link được thay bằng /admin/brokers/links)", not (set(lost_forms) - {"/admin/brokers/{id}/link"}), lost_forms)
sn.stop()

# =========== B. Bulk save ===========
s = Server("bulk").start()
s.cli_admin()
s.cli_admin(EDITOR_EMAIL, EDITOR_PASS, "editor")
h = Http().login()
mk_broker(h, "Sàn B1", affiliate_url="https://aff.example.test/b1")
mk_broker(h, "Sàn B2", affiliate_url="https://aff.example.test/b2")
mk_broker(h, "Sàn B3", affiliate_url="")
CASES = [("cungnam", "2026-11-01", "2026-11-30"), ("quanam", "2025-01-01", "2026-11-30"), ("quanam2", "2025-11-01", "2026-01-31"), ("chiden", "", "2026-12-31"), ("chitu", "2026-11-01", ""),
         ("trong", "", ""), ("sangnam", "2026-11-01", "2027-02-01"), ("dacu", "2025-03-01", "2025-04-01"), ("namsau", "2027-01-01", "2027-02-01"), ("nhuan", "2028-02-29", "2028-03-01")]
for n, a, b in CASES:
    mk_banner(h, n, start_date=a, end_date=b, target_url=f"https://ad.example.test/{n}")
mk_banner(h, "theosan", broker_id=1, target_url="", placement="rail-left")
COLS = "id,name,placement,target_url,start_date,end_date,is_active,views,clicks,broker_id,image_path"
snap = lambda: {r[0]: r for r in s.sql(f"select {COLS} from banners")}
ids = {r[1]: r[0] for r in snap().values()}
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    ctx.route("**/*", FONTS)
    pg = ctx.new_page()
    pg.goto(BASE + "/admin/login")
    pg.fill("input[name=email]", ADMIN_EMAIL)
    pg.fill("input[name=password]", ADMIN_PASS)
    with pg.expect_navigation():
        pg.click("button[type=submit]")
    PUBLISH = "button[form=page-form]"

    # B1 lưu nguyên trạng
    before = snap()
    pg.goto(BASE + "/admin/ads")
    labels = {n: pg.input_value(f"input[name=dates_{ids[n]}]") for n, _, _ in CASES}
    print("     nhãn ngày:", labels, flush=True)
    with pg.expect_navigation():
        pg.click(PUBLISH)
    after = snap()
    changed = {before[i][1]: (before[i][4:6], after[i][4:6]) for i in before if before[i] != after[i]}
    c("B1.1", "Xuất bản không đổi gì ở /admin/ads: mọi dòng giữ nguyên", not changed, changed)
    c("B1.2", "Báo Đã lưu", "Đã lưu" in pg.locator("[data-flash]").first.inner_text() if pg.locator("[data-flash]").count() else False)
    for i, row in before.items():  # trả về đúng để các bước sau độc lập
        s.sql("update banners set start_date=?, end_date=? where id=?", (row[4], row[5], i))

    # B2 sửa đúng một dòng qua UI
    i = ids["cungnam"]
    before = snap()
    pg.goto(BASE + "/admin/ads")
    pg.select_option(f"select[name=placement_{i}]", "before-blog")
    pg.fill(f"input[name=target_url_{i}]", "https://ad.example.test/moi")
    pg.fill(f"input[name=dates_{i}]", "02/11 – 29/11")
    with pg.expect_navigation():
        pg.click(PUBLISH)
    after = snap()
    r = after[i]
    c("B2.1", "Dòng sửa đúng cả 3 trường", r[2:6] == ("before-blog", "https://ad.example.test/moi", "2026-11-02", "2026-11-29"), r[2:6])
    others = {before[k][1] for k in before if k != i and before[k][2:] != after[k][2:]}
    c("B2.2", "Dòng khác không đổi (trừ lỗi ngày B1.1)", others <= {"quanam"}, others)
    c("B2.3", "Không mất views, clicks, ảnh, sàn, is_active", r[6:] == before[i][6:])
    for k, row in before.items():
        s.sql("update banners set start_date=?, end_date=?, placement=?, target_url=? where id=?", (row[4], row[5], row[2], row[3], k))

    # B3 Enter trong ô cũng lưu đúng form
    pg.goto(BASE + "/admin/ads")
    pg.fill(f"input[name=target_url_{i}]", "https://ad.example.test/enter")
    with pg.expect_navigation():
        pg.press(f"input[name=target_url_{i}]", "Enter")
    c("B3.1", "Enter trong ô của thẻ banner lưu đúng", s.sql("select target_url from banners where id=?", (i,))[0][0] == "https://ad.example.test/enter" and "/admin/ads" in pg.url, pg.url)
    s.sql("update banners set target_url=? where id=?", (before[i][3], i))

    # B4 công tắc giữa form bulk: không nộp nhầm form lớn
    j = ids["trong"]
    pg.goto(BASE + "/admin/ads")
    pg.fill(f"input[name=target_url_{i}]", "https://ad.example.test/chua-luu")
    with pg.expect_response(lambda r: r.url.endswith(f"/admin/ads/{j}/toggle")):  # công tắc đổi tại chỗ từ phase 6.1
        pg.locator(f"form[action='/admin/ads/{j}/toggle'] button").click()
    c("B4.1", "Bấm công tắc chỉ đổi is_active", s.sql("select is_active from banners where id=?", (j,))[0][0] == 0 and s.sql("select target_url from banners where id=?", (i,))[0][0] == before[i][3])
    s.sql("update banners set is_active=1 where id=?", (j,))

    # Link affiliate
    kb = {r[1]: r[0] for r in s.sql("select id,name from brokers")}
    before_k = s.sql("select id,affiliate_url,clicks,license from brokers order by id")
    pg.goto(BASE + "/admin/brokers?tab=links")
    with pg.expect_navigation():
        pg.click(PUBLISH)
    c("B5.1", "Xuất bản Link affiliate không đổi gì", s.sql("select id,affiliate_url,clicks,license from brokers order by id") == before_k)
    pg.fill(f"input[name=url_{kb['Sàn B2']}]", "https://aff.example.test/moi")
    with pg.expect_navigation():
        pg.click(PUBLISH)
    now = dict(s.sql("select name,affiliate_url from brokers"))
    c("B5.2", "Chỉ dòng sửa đổi, đúng sàn", now == {"Sàn B1": "https://aff.example.test/b1", "Sàn B2": "https://aff.example.test/moi", "Sàn B3": ""}, now)
    c("B5.3", "Sau lưu vẫn ở tab links", "tab=links" in pg.url, pg.url)
    b.close()

# B6 HTTP: tất cả hoặc không
k1, k2 = kb["Sàn B1"], kb["Sàn B2"]
for label, bad in (("javascript", "javascript:alert(1)"), ("ftp", "ftp://x"), ("rác", "khong-phai-url"), ("dấu cách", "https://x.test/a b")):
    pre = s.sql("select id,affiliate_url from brokers order by id")
    r = h.post("/admin/brokers/links", {f"url_{k1}": "https://aff.example.test/doi", f"url_{k2}": bad})
    c(f"B6.{label}", f"Links có dòng sai ({label}): flash lỗi, không lưu dòng nào", flash(r) == "invalid_url" and s.sql("select id,affiliate_url from brokers order by id") == pre, (flash(r), s.sql("select id,affiliate_url from brokers order by id")))
pre = s.sql("select id,affiliate_url from brokers order by id")
r = h.post("/admin/brokers/links", {f"url_{k1}": "https://x.test/" + "a" * 1000})
c("B6.long", "Link > 1000 ký tự: too_long, không cắt", flash(r) == "too_long" and s.sql("select id,affiliate_url from brokers order by id") == pre, flash(r))
r = h.post("/admin/brokers/links", {"url_99999": "https://x.test/", "url_abc": "x", f"url_{k1}": pre[0][1]})
c("B6.ghost", "url_<id không tồn tại>, url_abc: bỏ qua, không 500", r.status_code == 303 and s.sql("select id,affiliate_url from brokers order by id") == pre, r.status_code)
r = h.post("/admin/brokers/links", {f"url_{k1}": "https://x.test/1"})
c("B6.part", "Dòng không gửi lên thì giữ nguyên (không bị xóa link)", dict(s.sql("select id,affiliate_url from brokers"))[k2] == pre[1][1])
r = h.post("/admin/brokers/links", {f"url_{k1}": ""})
c("B6.clear", "Xóa trống link được, nút Mở tài khoản ẩn, /go 404", s.sql("select affiliate_url from brokers where id=?", (k1,))[0][0] == "" and pub.get(f"/go/broker/{k1}").status_code == 404)
h.post("/admin/brokers/links", {f"url_{k1}": "https://aff.example.test/b1"})
r = h.post("/admin/brokers/links", [(f"url_{k1}", "https://a.test/1"), (f"url_{k1}", "https://a.test/2")])
c("B6.dup", "Tên lặp không 500", r.status_code == 303, r.status_code)
r = h.post("/admin/brokers/links", {f"url_{k1}": "https://aff.example.test/b1"}, files={f"url_{k2}": ("a.txt", b"x")})
c("B6.file", "url_ gửi dạng file: không 500", r.status_code < 500, r.status_code)

i, j = ids["cungnam"], ids["chitu"]
def row(n, **kw):
    x = snap()[ids[n]]
    d = {f"placement_{x[0]}": x[2], f"target_url_{x[0]}": x[3], f"dates_{x[0]}": "01/11 – 30/11"}
    d.update({f"{k}_{x[0]}": v for k, v in kw.items()})
    return d
for label, kw, want in (("javascript", {"target_url": "javascript:alert(1)"}, "invalid_url"), ("ngày sai", {"dates": "99/99 – 30/11"}, "invalid_dates"), ("31/02", {"dates": "31/02"}, "invalid_dates"), ("3 phần", {"dates": "01/11 – 02/11 – 03/11"}, "invalid_dates"),
                        ("ngày ngược có năm", {"dates": "30/11/2026 – 01/11/2026"}, "invalid_dates"), ("chữ", {"dates": "abc"}, "invalid_dates"), ("dài", {"target_url": "https://x.test/" + "a" * 1000}, "too_long")):
    pre = snap()
    d = row("trong", target_url="https://ad.example.test/phai-khong-luu") | row("chitu", **kw)
    r = h.post("/admin/ads/bulk", d)
    c(f"B7.{label}", f"Bulk có thẻ sai ({label}): flash {want}, không lưu thẻ nào", flash(r) == want and snap() == pre, (flash(r), r.status_code, snap() == pre))
pre = snap()
r = h.post("/admin/ads/bulk", row("trong", placement="khong-co"))
c("B7.place", "placement ngoài danh sách: 4xx, không lưu", 400 <= r.status_code < 500 and snap() == pre, r.status_code)
ds = {"30/11": ("2026-11-30", None), "01/11 –": ("2026-11-01", None), "– 30/11": (None, "2026-11-30"), "1/11-30/11": ("2026-11-01", "2026-11-30"), "01/11/2026 – 30/11/2026": ("2026-11-01", "2026-11-30"), "01/12 – 31/01": ("2026-12-01", "2027-01-31"), "": (None, None)}
for txt, want in ds.items():
    r = h.post("/admin/ads/bulk", row("trong", dates=txt))
    got = s.sql("select start_date,end_date from banners where id=?", (ids["trong"],))[0]
    c(f"B8.{txt}", f"Ngày nhập {txt!r} → {want}", got == want, got)
s.sql("update banners set start_date=null,end_date=null where id=?", (ids["trong"],))
r = h.post("/admin/ads/bulk", {"placement_99999": "after-bonus", "placement_abc": "x"})
c("B9.1", "placement_<id lạ>: bỏ qua, không 500", r.status_code == 303, r.status_code)
r = h.post("/admin/ads/bulk", {})
c("B9.2", "Form rỗng: không 500, không đổi", r.status_code == 303)
# Một banner chết chặn lưu cả trang?
h.post(f"/admin/brokers/{k1}/link", {"affiliate_url": ""})
s.sql("update banners set target_url='' where id=?", (ids["theosan"],))
r_ = h.get("/admin/ads").text
payload = []
for x in snap().values():
    m = re.search(rf'name="dates_{x[0]}" value="([^"]*)"', r_)
    payload += [(f"placement_{x[0]}", x[2]), (f"target_url_{x[0]}", "https://ad.example.test/doi" if x[0] == i else x[3]), (f"dates_{x[0]}", m.group(1).replace("&ndash;", "–") if m else "")]
pre = snap()[i][3]
r = h.post("/admin/ads/bulk", payload)
saved = snap()[i][3] != pre
c("B10.1", "Có 1 banner mất link (sàn bị xóa link): vẫn sửa được banner khác ở cùng trang, hoặc lỗi chỉ rõ banner nào", saved, f"flash={flash(r)}: báo chung 'Link phải bắt đầu bằng http', không nói banner nào, không lưu được thẻ nào")
s.stop()

# =========== C. Bảo mật route mới ===========
s = Server("sec3").start()
h = seed(s)
try:
    routes = admin_routes(s.env)
    posts = [re.sub(r"\{\w+\}", lambda m: "hero" if m.group(0) in ("{tab}", "{sid}") else "1", p) for p, ms in routes if "post" in ms and p != "/admin/login"]
    for raw_p, ms in routes:
        if raw_p == "/admin/settings/{tab}":
            posts.extend(f"/admin/settings/{t}" for t in ("brand", "general", "seo", "social", "tracking"))
    c("C0", "Route mới có trong bảng", all(x in posts for x in ("/admin/brokers/links", "/admin/ads/bulk", "/admin/settings/brand")), posts[:5])
    bad = [(p, st) for p in posts if (st := h.post(p, {"x": "1"}, raw=True).status_code) != 403]
    c("C1", f"{len(posts)} route POST: thiếu CSRF đều 403", not bad, bad)
    bad = [(p, st) for p in posts if (st := h.post(p, {"csrf_token": "sai"}, raw=True).status_code) != 403]
    c("C2", "CSRF sai đều 403", not bad, bad)
    anon = Http()
    bad = [(p, st) for p in posts if p != "/admin/logout" and not ((r := anon.post(p, {"x": "1"})).status_code == 303 and "/admin/login" in r.headers.get("location", "")) and (st := r.status_code)]
    c("C3", "Chưa đăng nhập: POST về login", not bad, bad)
    st = s.sql("select count(*) from brokers")[0][0]
    pre = s.sql("select affiliate_url from brokers order by id")
    r = httpx.post(BASE + "/admin/brokers/links", data={"url_1": "https://evil.test/"})
    c("C4", "POST /admin/brokers/links chéo site không cookie: không đổi", s.sql("select affiliate_url from brokers order by id") == pre)
    e = Http().login(EDITOR_EMAIL, EDITOR_PASS)
    bad = []
    for tab in ("general", "brand", "seo", "social", "tracking", "users"):
        if e.get(f"/admin/settings?tab={tab}").status_code != 403:
            bad.append(("GET", tab))
    for pth, d in (("/admin/settings/brand", {"partner_email": "x@evil.test"}), ("/admin/settings/general", {"site_name": "H"}), ("/admin/settings/tracking", {"analytics_head": "<script>1</script>"}), ("/admin/settings/seo", {"meta_title": "H"}), ("/admin/settings/social", {}),
                   ("/admin/settings/users/new", {"email": "h@x.co", "password": "abcdefghij12", "role": "admin"}), ("/admin/settings/users/1/edit", {"password": "abcdefghij12"}), ("/admin/settings/users/1/toggle", {}), ("/admin/settings/users/1/delete", {})):
        if e.post(pth, d).status_code != 403:
            bad.append(("POST", pth))
    c("C5", "Editor 403 toàn bộ Cài đặt, gồm tab brand", not bad, bad)
    c("C6", "Giá trị partner_email không đổi", "x@evil.test" not in str(s.sql("select value from settings")))
    nav = e.get("/admin").text
    c("C7", "Sidebar editor không có Cài đặt, 'Xuất bản' không trỏ settings", "/admin/settings" not in nav)
    print("     editor sửa link affiliate/bulk banner:", e.post("/admin/brokers/links", {"url_1": "https://aff.example.test/a"}).status_code, e.post("/admin/ads/bulk", {}).status_code, "(giống quyền Sàn/Quảng cáo trước đây)", flush=True)
    # Redirect qua back, filters
    evil = ["//evil.com", "https://evil.com", "/\\evil.com", "/\t/evil.com", "/admin/bonus/../..//evil.com", "/admin/posts@evil.com"]
    bads = []
    for v in evil:
        for pth, d in (("/admin/bonus/1/toggle", {}), ("/admin/subscribers/1/delete", {}), ("/admin/subscribers/campaigns/1/delete", {})):
            pass
        for pth in ("/admin/bonus/1/toggle", "/admin/posts/1/toggle", "/admin/ads/1/toggle", "/admin/messages/1/toggle", "/admin/brokers/1/toggle", "/admin/ads/bulk", "/admin/brokers/links"):
            r = h.post(pth, {"back": v, "field": "featured"})
            loc = r.headers.get("location", "")
            if urlsplit(urljoin(BASE, loc)).netloc != f"127.0.0.1:{PORT}":  # "/admin/x/../..//evil.com" vẫn cùng host: không ra ngoài
                bads.append((pth, v, loc))
        r = h.post("/admin/bonus/new?q=" + quote(v) + "&tab=" + quote(v), {"broker_id": 1, "type": "deposit", "title": "Redir", "is_active": "1"})
        loc = r.headers.get("location", "")
        if not loc.startswith("/admin/bonus"):
            bads.append(("bonus/new", v, loc))
        r = h.post(f"/admin/posts/new?q={quote(v)}", {"title": f"Redir {evil.index(v)}", "category": "Tin sàn", "status": "draft"})
        if not r.headers.get("location", "").startswith("/admin/posts"):
            bads.append(("posts/new", v, r.headers.get("location")))
        r = httpx.post(BASE + "/api/subscribe", data={"email": "x", "next": v})
        if urlsplit(urljoin(BASE, r.headers.get("location", ""))).netloc != f"127.0.0.1:{PORT}":
            bads.append(("subscribe", v, r.headers.get("location")))
        p2 = httpx.post(BASE + "/admin/ads/bulk", data={"x": 1}, headers={"Referer": "https://evil.com/admin/x"})
        if "evil" in p2.headers.get("location", "").split("next=")[0]:
            bads.append(("referer", p2.headers.get("location")))
    c("C8", "Open redirect qua back, tab, q, next, Referer: không ra ngoài", not bads, bads[:5])
    r = h.post("/admin/bonus/new?q=a%0d%0aSet-Cookie:x=1", {"broker_id": 1, "type": "deposit", "title": "CRLF", "is_active": "1"})
    c("C9", "CRLF trong q không chèn header", "x=1" not in r.headers.get("set-cookie", ""), r.headers.get("location"))
    r = h.post("/admin/bonus/new?type=%22%3E%3Csvg", {"broker_id": 1, "type": "sai", "title": ""})
    c("C10", "Lỗi 400 phản chiếu q/type đã escape", r.status_code == 400 and "<svg" not in r.text)
    # XSS lưu trong url + tham số
    pay_url = 'https://x.test/"><svg/onload=__xss=1>'
    h.post("/admin/brokers/links", {"url_1": pay_url})
    h.post("/admin/ads/bulk", {"placement_1": "after-bonus", "target_url_1": pay_url, "dates_1": ""})
    print("     url chứa \"><svg lưu qua links/bulk:", s.sql("select affiliate_url from brokers where id=1"), flush=True)
    h.post("/admin/brokers/1/edit", {"name": XSS[:100], "slug": "san-mot", "kind": "forex", "license": XSS, "is_active": "1", "in_compare": "1", "affiliate_url": ""})
    mk_banner(h, XSS[:100], broker_id=1, placement="rail-right", target_url="https://ad.example.test/x")
    mk_post(h, XSS, slug="xss-post", category="Tin sàn", excerpt=XSS, body_md=XSS)
    h.post("/admin/settings/brand", {"partner_email": "ok@qa.test", "logo_path": "/static/img/logo.png", "favicon_path": "/static/img/logo.png"})
    h.post("/admin/home/sections", {"compare_featured_label": XSS, "bonus_eyebrow": XSS, "bonus_title": XSS, "compare_eyebrow": XSS, "compare_title": XSS, "blog_eyebrow": XSS, "blog_title": XSS})
    r = h.post("/admin/settings/brand", {"partner_email": XSS})
    c("C11", "partner_email rác bị từ chối ở tab brand", r.status_code == 400, r.status_code)
    urls = ["/", "/tin-tuc", "/tin-tuc/xss-post", '/tin-tuc/xss-post?cat="><svg/onload=__xss=1>', "/tin-tuc/bai-mot?cat=Tin sàn", "/san", "/san/so-sanh", "/san/san-mot", "/san/so-sanh?ids=1,2,3", "/lien-he",
            '/bonus?type="><svg/onload=__xss=1>', "/admin/ads", "/admin/ads?tab=stats", "/admin/brokers?tab=links", "/admin", "/admin/home?tab=sections", "/admin/settings?tab=brand",
            '/admin/bonus/new?q="><svg/onload=__xss=1>', '/admin/posts/new?q="><svg/onload=__xss=1>', '/admin/ads/new?tab="><svg/onload=__xss=1>', '/admin/brokers/new?tab="><svg/onload=__xss=1>', '/admin/subscribers?q="><svg/onload=__xss=1>', "/admin/settings?tab=users"]
    CHECK = """() => ({x: window.__xss, imgs: document.querySelectorAll('img[src="x"]').length, svg: document.querySelectorAll('svg[onload]').length,
        ev: [...document.querySelectorAll('*')].filter(e => [...e.attributes].some(a => /^on/.test(a.name))).length})"""
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1700, "height": 1000}, bypass_csp=True)
        ctx.route("**/*", FONTS)
        pg = ctx.new_page()
        pg.goto(BASE + "/admin/login")
        pg.fill("input[name=email]", ADMIN_EMAIL)
        pg.fill("input[name=password]", ADMIN_PASS)
        with pg.expect_navigation():
            pg.click("button[type=submit]")
        fails = []
        for u in urls:
            pg.goto(BASE + u)
            pg.wait_for_timeout(100)
            res = pg.evaluate(CHECK)
            if res["x"] or res["imgs"] or res["svg"] or res["ev"]:
                fails.append((u, res))
        c("C12", f"{len(urls)} trang (kể cả drawer có tham số, cat): không có HTML/JS lọt ra", not fails, fails[:4])
        # tìm kiếm trực tiếp thay DOM từ HTML fetch về
        for pth, q in (("/admin/bonus", "Redir"), ("/admin/posts", "xss"), ("/admin/subscribers", "u0")):
            pg.goto(BASE + pth)
            box = pg.locator("[data-live-search] input[name=q]")
            if box.count():
                box.first.fill('"><svg/onload=__xss=1>')
                pg.wait_for_timeout(500)
                res = pg.evaluate(CHECK)
                c(f"C13{pth}", f"Tìm trực tiếp ở {pth}: không chèn HTML", not res["x"] and not res["svg"], res)
                box.first.fill(q)
                pg.wait_for_timeout(500)
                c(f"C14{pth}", f"Tìm trực tiếp ở {pth} ra đúng dòng, URL đổi theo", "q=" in pg.url, pg.url)
                # sau khi vùng data-live bị thay, công tắc, nút xóa còn dùng được
                sw = pg.locator("main form.toggle-form button")
                if sw.count():
                    with pg.expect_response(lambda r: r.url.endswith("/toggle")) as toggled:  # công tắc đổi tại chỗ từ phase 6.1
                        sw.first.click()
                    c(f"C15{pth}", "Sau tìm trực tiếp: công tắc còn CSRF, chạy được", "tbh" not in pg.url and toggled.value.status < 400, toggled.value.status)
        b.close()
    r = pub.get("/tin-tuc/bai-mot?cat=//evil.com")
    c("C16", "cat lạ không vào link về danh sách", "//evil.com" not in r.text)
    c("C17", "Link về danh sách bài chỉ nhận chuyên mục hợp lệ", 'svg' not in pub.get('/tin-tuc/bai-mot?cat="><svg').text)
finally:
    s.stop()

# =========== D. Production + console ===========
s = Server("prodcon", env=prod_env()).start()
s.cli_admin()
h = Http().login()
try:
    n0 = s.log_text().count("[console email]")
    r = pub.post("/api/subscribe", data={"email": "khach@qa.test", "next": "/"})
    c("D1", "Đăng ký ở production + console: sub_failed, không lưu, không log token", flash(r) == "sub_failed" and s.sql("select count(*) from subscribers")[0][0] == 0 and s.log_text().count("[console email]") == n0, (flash(r), s.sql("select count(*) from subscribers")))
    t = httpx.get(BASE + "/", cookies={"tbh_flash": "sub_failed"}).text
    c("D2", "Trang chủ hiện lỗi cạnh form, không có khối 'đã đăng ký'", "Chưa gửi được email" in t and "Kiểm tra hộp thư" not in re.sub(r"Kiểm tra hộp thư.*Chưa", "", t)[:0] + t.split("Chưa gửi được email")[0][-200:], "")
    s.sql("insert into subscribers(name,email,interests,status,token,confirm_count,created_at,updated_at) values('K','a@qa.test','[]','confirmed','t1',0,'2026-01-01 00:00:00','2026-01-01 00:00:00')")
    r = h.post("/admin/subscribers/mail", {"subject": "S", "body": "B", "action": "send"})
    st = s.sql("select status,sent_count,sent_to from campaigns")
    c("D3", "Gửi chiến dịch: send_failed, về nháp, 0 email", flash(r) == "send_failed" and st == [("draft", 0, "[]")] and s.log_text().count("[console email]") == n0, (flash(r), st))
    p = h.get(r.headers["location"])
    c("D4", "Không mất chữ đang soạn", 'value="S"' in p.text and ">B</textarea>" in p.text)
    r = h.post("/admin/subscribers/mail/test", {"subject": "S", "body": "B"})
    c("D5", "Gửi thử: báo lỗi, 502", r.status_code == 502, r.status_code)
    h.post("/admin/subscribers/mail", {"subject": "S2", "body": "B", "action": "draft"})
    c("D6", "Lưu nháp vẫn được", s.sql("select count(*) from campaigns where subject='S2'")[0][0] == 1)
    r = pub.post("/api/contact", data={"topic": "Hợp tác", "email": "k@qa.test", "body": "x"})
    c("D7", "Liên hệ vẫn hoạt động", r.status_code == 303 and s.sql("select count(*) from contact_messages")[0][0] == 1)
    r = pub.post("/huy-dang-ky/t1")
    c("D8", "Hủy đăng ký không phụ thuộc email", r.status_code == 200 and s.sql("select status from subscribers")[0][0] == "unsubscribed")
finally:
    s.stop()

# =========== E. Chức năng dời vào drawer: thao tác thật ===========
s = Server("drawers").start()
h = seed(s)
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script(OPEN_DETAILS)
    ctx.route("**/*", FONTS)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "status of 4" not in m.text else None)
    pg.goto(BASE + "/admin/login")
    pg.fill("input[name=email]", ADMIN_EMAIL)
    pg.fill("input[name=password]", ADMIN_PASS)
    with pg.expect_navigation():
        pg.click("button[type=submit]")
    fl = lambda: pg.locator("[data-flash]").first.inner_text() if pg.locator("[data-flash]").count() else ""

    def confirm():
        with pg.expect_navigation():
            pg.locator("#confirm-dialog button[value=ok]").click()

    # Sàn: bật/tắt hiển thị đã dời vào drawer
    pg.goto(BASE + "/admin/brokers")
    pg.locator("a.btn-row", has_text="Sửa").nth(1).click()
    pg.wait_for_selector(".drawer")
    pg.locator("label:has(input[name=is_active])").click()
    with pg.expect_navigation():
        pg.click(".drawer-foot .btn-save, .drawer-foot button[form=drawer-form]")
    c("E1", "Ẩn sàn qua drawer", s.sql("select is_active from brokers where id=2")[0][0] == 0 and pub.get("/san/san-hai").status_code == 404)
    h.post("/admin/brokers/2/toggle", {"field": "is_active"})
    # Tài khoản
    pg.goto(BASE + "/admin/settings?tab=users")
    pg.locator("a[href='#user-new']").click()
    pg.wait_for_timeout(150)
    box = pg.locator("#user-new input[name=email]")
    c("E2", "+ Thêm tài khoản mở form thấy được", box.is_visible())
    box.fill("moi@qa.test")
    pg.locator("#user-new input[name=password]").fill("MatKhauMoi-123")
    with pg.expect_navigation():
        pg.locator("#user-new button[type=submit], button[form][form*=new]").first.click()
    uid = s.sql("select id from admin_users where email='moi@qa.test'")
    c("E3", "Thêm tài khoản", bool(uid), fl())
    uid = uid[0][0]
    pg.goto(BASE + "/admin/settings?tab=users")
    pg.locator(f"a[href='#user-{uid}']").first.click()
    pg.wait_for_timeout(150)
    pw = pg.locator(f"#user-form-{uid} input[name=password]")
    c("E4", "Mở drawer sửa tài khoản", pw.is_visible())
    with pg.expect_navigation():
        pg.locator(f"form[action='/admin/settings/users/{uid}/toggle'] button").click()
    c("E5", "Khóa tài khoản trong drawer", s.sql("select is_active from admin_users where id=?", (uid,))[0][0] == 0)
    pg.goto(BASE + "/admin/settings?tab=users")
    pg.locator(f"a[href='#user-{uid}']").first.click()
    pg.wait_for_timeout(150)
    pg.locator(f"button[form='user-del-{uid}']").click()
    confirm()
    c("E6", "Xóa tài khoản trong drawer", not s.sql("select id from admin_users where id=?", (uid,)))
    # Người đăng ký: lọc, xóa, lịch sử gửi
    pg.goto(BASE + "/admin/subscribers")
    pg.locator("a[href='#loc']").first.click()
    pg.wait_for_timeout(150)
    c("E7", "Nút lọc người đăng ký mở khối lọc", pg.locator("#loc input[name=q], #loc select, #loc a").first.is_visible())
    pg.goto(BASE + "/admin/subscribers")
    row = pg.locator(".t-row", has_text="u0@qa.test")
    row.hover()
    d = row.locator(".row-tools button")
    c("E8", "Nút Xóa người đăng ký hiện khi rê chuột", d.is_visible())
    pg.mouse.move(0, 0)
    d.focus()
    c("E9", "Nút Xóa nhìn thấy khi Tab tới bằng bàn phím", d.evaluate("e => { const s = getComputedStyle(e.closest('.row-tools')); return s.visibility !== 'hidden' && s.opacity !== '0' && s.display !== 'none'; }"))
    d.click()
    confirm()
    c("E10", "Xóa người đăng ký", s.sql("select count(*) from subscribers where email='u0@qa.test'")[0][0] == 0)
    touch = b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    touch.add_cookies([{"name": k["name"], "value": k["value"], "domain": "127.0.0.1", "path": "/"} for k in ctx.cookies()])
    tp = touch.new_page()
    tp.route("**/*", FONTS)
    tp.goto(BASE + "/admin/subscribers")
    vis = tp.locator(".t-row .row-tools button").first.evaluate("e => { const s = getComputedStyle(e.closest('.row-tools')); return s.visibility !== 'hidden' && s.opacity !== '0' && s.display !== 'none'; }")
    c("E11", "Điện thoại (không có hover): nút Xóa người đăng ký thấy được", vis)
    touch.close()
    pg.goto(BASE + "/admin/subscribers?tab=mail")
    pg.locator("a[href='#lich-su']").click()
    pg.wait_for_timeout(150)
    c("E12", "Lịch sử gửi mở được, có bản nháp", "Nháp" in pg.locator("#lich-su").inner_text())
    pg.keyboard.press("Escape")
    # Enter trong ô tiêu đề = lưu nháp, không gửi
    pg.goto(BASE + "/admin/subscribers?tab=mail")
    pg.fill("#mail-form input[name=subject]", "Enter không gửi")
    pg.fill("#mail-form textarea[name=body]", "Nội dung")
    n0 = s.log_text().count("[console email]")
    with pg.expect_navigation():
        pg.press("#mail-form input[name=subject]", "Enter")
    st = s.sql("select status from campaigns where subject='Enter không gửi'")
    c("E13", "Enter trong tiêu đề email: lưu nháp, không gửi", st == [("draft",)] and s.log_text().count("[console email]") == n0, st)
    with pg.expect_navigation():
        pg.click("button[form=mail-form][name=action][value=draft]")
    c("E14", "Xuất bản ở tab Gửi email cập nhật đúng nháp đó", s.sql("select count(*) from campaigns where subject='Enter không gửi'")[0][0] == 1)
    pg.click("#mail-form button[name=action][value=send]")
    pg.wait_for_selector("#confirm-dialog[open]")
    confirm()
    c("E15", "Gửi thật (dev console) vẫn đi", s.sql("select status from campaigns where subject='Enter không gửi'")[0][0] == "sent" and s.log_text().count("[console email]") > n0)
    # Xuất bản ở màn danh sách
    pg.goto(BASE + "/admin/bonus")
    pg.click("[data-publish]")
    c("E16", "Xuất bản ở màn danh sách báo Đã lưu", pg.locator("[data-publish-note]").is_visible())
    # Xuất bản ở form tab
    for u, sel, val in (("/admin/home?tab=hero", "[name=cta]", "CTA R3"), ("/admin/pages?tab=bonus", "[name=title]", "Tiêu đề R3"), ("/admin/settings?tab=brand", "[name=partner_email]", "hoptac@qa.test"), ("/admin/settings?tab=general", "[name=site_name]", "Tên R3")):
        pg.goto(BASE + u)
        pg.fill(sel, val)
        with pg.expect_navigation():
            pg.click("button[form=page-form]")
        c(f"E17{u}", f"Xuất bản lưu {u}", any(val in json.dumps(json.loads(x[0]), ensure_ascii=False) for x in s.sql("select value from settings")) and "Đã lưu" in fl(), fl())
    t = pub.get("/lien-he").text
    c("E18", "partner_email (tab brand) hiện ở /lien-he", "hoptac@qa.test" in t)
    # Lưu tab general không xóa partner_email; lưu brand không xóa contact_email
    c("E19", "Lưu tab Chung không xóa email hợp tác", "hoptac@qa.test" in str(s.sql("select value from settings where key='partner_email'")))
    # Trang điều khoản còn link?
    home = pub.get("/").text + pub.get("/bonus").text
    c("E20", "/dieu-khoan, /bao-mat có link từ site (DB mới, mặc định)", "/dieu-khoan" in home and "/bao-mat" in home, "không còn link nào; chỉ vào được bằng URL")
    c("E21", "Không lỗi JS/console khi thao tác admin", not errs, errs[:4])
    b.close()
s.stop()

# =========== F. Nâng cấp DB tạo bằng 2e4229e ===========
envu = {"SECRET_KEY": "qa-upgrade-secret-" + "u" * 30}
s = Server("up3", env=envu)
s.cwd = OLD
s.start()
h = seed(s)
pub.post("/api/subscribe", data={"email": "cho@qa.test", "next": "/"}, headers={"CF-Connecting-IP": "9.3.0.1"})
t_cho = s.tokens("cho@qa.test")[-1]
pub.post("/api/subscribe", data={"email": "huy@qa.test", "next": "/"}, headers={"CF-Connecting-IP": "9.3.0.2"})
t_huy = s.tokens("huy@qa.test")[-1]
pub.post(f"/xac-nhan/{t_huy}")
pub.post(f"/huy-dang-ky/{t_huy}")
s.sql("""update campaigns set status='partial', sent_to='["u0@qa.test"]', sent_count=1, sent_at='2026-11-01 00:00:00' where subject='Nháp'""")
h.post("/admin/home/hero", {"eyebrow": "E", "headline": "H cũ", "sub": "S", "cta": "C", "card_label": "L", "image_path": ""})
h.post("/admin/settings/general", {"site_name": "Tên Cũ", "contact_email": "a@qa.test", "partner_email": "b@qa.test", "telegram": ""})
TABLES = ["admin_users", "admin_sessions", "brokers", "bonuses", "posts", "banners", "subscribers", "contact_messages", "campaigns", "settings", "media_files", "click_logs"]
before = {t: s.sql(f"select count(*) from {t}")[0][0] for t in TABLES}
c("F0", "DB cũ ở 0002", s.sql("select version_num from alembic_version") == [("0002",)], s.sql("select version_num from alembic_version"))
s.stop()
del s
s = Server("up3", env=envu, fresh=False).start()
try:
    c("F1", "Lên 0004", s.sql("select version_num from alembic_version") == [("0004",)])
    c("F2", "Số dòng không đổi", before == {t: s.sql(f"select count(*) from {t}")[0][0] for t in TABLES})
    c("F3", "Index unique reconfirm_token, nhiều NULL không đụng", s.sql("select count(*) from subscribers where reconfirm_token is null")[0][0] == before["subscribers"])
    r = subprocess.run([PY, "-m", "alembic", "check"], cwd=ROOT, env=s.env, capture_output=True, text=True, encoding="utf-8")
    c("F4", "alembic check sạch", r.returncode == 0, (r.stdout + r.stderr)[-200:])
    hh = Http()
    hh.cookies, hh.csrf = dict(h.cookies), h.csrf
    c("F5", "Phiên cũ còn", hh.get("/admin").status_code == 200)
    bad = [p for p in PAGES + PUBLIC if hh.get(p).status_code >= 500]
    c("F6", "Mọi trang admin + public chạy trên dữ liệu cũ", not bad, bad)
    r = pub.post(f"/xac-nhan/{t_cho}")
    c("F7", "Link xác nhận cũ còn dùng", r.status_code == 200 and s.sql("select status from subscribers where email='cho@qa.test'")[0][0] == "confirmed")
    t = pub.get("/lien-he").text
    c("F8", "partner_email cũ vẫn hiện", "b@qa.test" in t)
    p_ = hh.get("/admin/settings?tab=brand").text
    c("F9", "Tab brand hiện partner_email cũ", "b@qa.test" in p_)
    r = hh.post("/admin/subscribers/mail", {"subject": "Nháp", "body": "x", "action": "send", "draft_id": s.sql("select id from campaigns where subject='Nháp'")[0][0]})
    tos = re.findall(r"to=(\S+) subject=Nháp", s.log_text())
    c("F10", "Chiến dịch partial cũ gửi tiếp: không gửi lại người đã nhận", "u0@qa.test" not in tos[-5:] and s.sql("select status from campaigns where subject='Nháp'")[0][0] == "sent", tos)
    sub_new = pub.post("/api/subscribe", data={"email": "huy@qa.test", "next": "/"}, headers={"CF-Connecting-IP": "9.3.0.3"})
    c("F11", "Người đã hủy trước nâng cấp: báo sub_wait hoặc sub_ok, không kích hoạt lại", s.sql("select status from subscribers where email='huy@qa.test'")[0][0] == "unsubscribed", flash(sub_new))
    c("F12", "Link xác nhận cũ của người đã hủy không kích hoạt", pub.post(f"/xac-nhan/{t_huy}").status_code == 404)
    t = pub.get("/").text
    print("     DB cũ có hero.image_path rỗng: ảnh mặc định mới có hiện?", "hero-bg.webp" in t, flush=True)
    c("F13", "Footer đã lưu giữ nguyên chứ không mất cột", "Tên Cũ" in t)
    s.stop()
    s.start()
    c("F14", "Restart sau nâng cấp: dữ liệu còn", "Bonus Một" in pub.get("/bonus").text)
finally:
    s.stop()
r = subprocess.run([PY, "-m", "alembic", "downgrade", "0002"], cwd=ROOT, env=s.env, capture_output=True, text=True, encoding="utf-8")
c("F15", "downgrade 0002", r.returncode == 0, r.stderr[-200:])
r = subprocess.run([PY, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=s.env, capture_output=True, text=True, encoding="utf-8")
c("F16", "upgrade lại", r.returncode == 0, r.stderr[-200:])
# =========== G. Production + SMTP qua bộ nhận local (localhost:8015, không ra mạng) ===========
kp, cp = WORK / "smtp.key", WORK / "smtp.crt"
ossl = shutil.which("openssl") or r"C:\Program Files\Git\mingw64\bin\openssl.exe"
subprocess.run([ossl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(kp), "-out", str(cp), "-days", "30", "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost"], check=True, capture_output=True)
from fake_smtp import FakeSMTP  # noqa: E402

sink = FakeSMTP(str(cp), str(kp), 8015, refuse={"tuchoi@qa.test"})
sink.start()
s = Server("prodsmtp", entry="qa/smtp_run.py", env=prod_env(SMTP_BACKEND="smtp", SMTP_HOST="localhost", SMTP_PORT="8015", FROM_EMAIL="no-reply@qa.test", QA_SMTP_CA=str(cp), BASE_URL="https://site.qa.test")).start()
s.cli_admin()
h = Http().login()
try:
    r = pub.post("/api/subscribe", data={"email": "khach@qa.test", "name": "TRÚNG THƯỞNG", "next": "/"})
    c("G1", "Đăng ký: sub_ok, email tới bộ nhận qua STARTTLS", flash(r) == "sub_ok" and len(sink.msgs) == 1 and sink.tls, (flash(r), len(sink.msgs), sink.tls))
    m = sink.msgs[-1] if sink.msgs else ""
    em = email.message_from_string(m, policy=email.policy.default)  # thân UTF-8 được mã hóa, phải giải mã mới kiểm được
    body = em.get_content() if m else ""
    c("G2", "Email: From đúng, link https BASE_URL, có List-Unsubscribe-Post, không có tên", em["From"] == "no-reply@qa.test" and "https://site.qa.test/xac-nhan/" in body and em["List-Unsubscribe-Post"] and "TRÚNG" not in body, (em["From"], body[:200]))
    tk = s.sql("select token from subscribers")[0][0]
    pub.post(f"/xac-nhan/{tk}")
    for em in ("tuchoi@qa.test", "b@qa.test", "c@qa.test"):
        s.sql("insert into subscribers(name,email,interests,status,token,confirm_count,created_at,updated_at) values('',?,'[]','confirmed',?,0,'2026-01-01 00:00:00','2026-01-01 00:00:00')", (em, "t" + em[:3]))
    n0 = len(sink.msgs)
    r = h.post("/admin/subscribers/mail", {"subject": "Tin thật", "body": "Nội dung tiếng Việt", "action": "send"})
    st = s.sql("select status,sent_count from campaigns")
    print("     chiến dịch có 1 địa chỉ bị từ chối:", flash(r), st, "email tới bộ nhận:", len(sink.msgs) - n0, flush=True)
    c("G3", "1 địa chỉ bị SMTP từ chối: người khác vẫn nhận, không báo Đã gửi", len(sink.msgs) - n0 == 3 and flash(r) != "sent" and st[0][1] == 3, (flash(r), st, len(sink.msgs) - n0))
    r = h.post("/admin/subscribers/mail/test", {"subject": "S", "body": "B"})
    c("G4", "Gửi thử 200", r.status_code == 200, r.status_code)
    sink.stop()
    r = pub.post("/api/subscribe", data={"email": "matketnoi@qa.test", "next": "/"}, headers={"CF-Connecting-IP": "9.4.0.1"})
    c("G5", "SMTP tắt: sub_failed, không treo", flash(r) == "sub_failed", flash(r))
finally:
    s.stop()
    sink.stop()
R.save()
