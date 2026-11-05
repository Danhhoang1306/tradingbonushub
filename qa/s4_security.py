"""Vai D: bảo mật. Phần HTTP + phần trình duyệt (Chromium, bypass_csp để payload lọt escape sẽ thực thi và lộ ra)."""
import io
import re
import socket
import time
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit

import httpx
from PIL import Image
from playwright.sync_api import sync_playwright

from qalib import (ADMIN_EMAIL, ADMIN_PASS, BASE, EDITOR_EMAIL, EDITOR_PASS, PORT, Http, Report, Server, mk_banner, mk_bonus,
                   mk_broker, mk_post, png_bytes)

R = Report("s4_security")
c = R.check
XSS = "Q\"'><img src=x onerror=__xss=1><svg/onload=__xss=1></textarea></title></style><script>__xss=1</script>{{7*7}}"
URL_LOCAL = "/x\"><svg/onload=__xss=1>"
URL_HTTP = "https://x.test/\"><svg/onload=__xss=1>"


def raw_get(path, headers="", timeout=6):
    """GET thô, giữ nguyên chuỗi đường dẫn (httpx sẽ chuẩn hóa ../)."""
    with socket.create_connection(("127.0.0.1", PORT), timeout=timeout) as s:
        s.sendall(f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{PORT}\r\nConnection: close\r\n{headers}\r\n".encode("latin-1"))
        buf = b""
        try:
            while chunk := s.recv(65536):
                buf += chunk
        except TimeoutError:
            return -1, b"", "timeout"
    head, _, body = buf.partition(b"\r\n\r\n")
    first = head.split(b"\r\n")[0].decode("latin-1")
    return int(first.split()[1]) if len(first.split()) > 1 else 0, body, head.decode("latin-1")


class Fields(HTMLParser):
    """Lấy các form POST của trang: action + input/textarea có name."""

    def __init__(self):
        super().__init__()
        self.forms, self.cur = [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form" and (a.get("method") or "").lower() == "post":
            self.cur = {"action": a.get("action"), "fields": []}
            self.forms.append(self.cur)
        elif tag in ("input", "textarea", "select") and self.cur is not None and a.get("name"):
            self.cur["fields"].append((a["name"], a.get("type", tag), a.get("value") or ""))

    def handle_endtag(self, tag):
        if tag == "form":
            self.cur = None


def main_form(html, action):
    p = Fields()
    p.feed(html)
    for f in p.forms:
        if f["action"] == action:
            return f["fields"]
    return []


def fuzz_tab(h, page, action):
    """Điền payload vào mọi ô text của form tab rồi lưu. Trả (status, số ô đã điền)."""
    html = h.get(page).text
    data, n = [], 0
    for name, typ, val in main_form(html, action):
        if name == "csrf_token" or typ in ("file", "hidden", "checkbox", "radio", "select"):
            if typ in ("hidden", "radio", "checkbox", "select") and name != "csrf_token":
                data.append((name, val))
            continue
        if name.endswith("_url"):
            v = URL_HTTP if "social" in name else URL_LOCAL
        elif "image" in name or name.endswith("_path") or name.endswith("_image") or name == "image":
            v = val
        elif "email" in name:
            v = val
        elif "footer_col_links" in name:
            v = f"Nhãn {XSS}|{URL_LOCAL}"
        else:
            v = XSS
        n += 1
        data.append((name, v))
    return h.post(action, data).status_code, n


# =========================== Server development ===========================
s = Server("sec").start()
s.cli_admin()
s.cli_admin(EDITOR_EMAIL, EDITOR_PASS, "editor")
h = Http().login()
pub = httpx.Client(base_url=BASE, timeout=20)

try:
    # ---------- D1. Không đăng nhập: mọi route admin ----------
    spec = pub.get("/openapi.json").json()["paths"]
    anon = Http()
    leaks = []
    n = 0
    for path, ops in spec.items():
        if not path.startswith("/admin") or path in ("/admin/login",):
            continue
        p = re.sub(r"\{(\w+)\}", lambda m: "1" if m.group(1) not in ("tab", "sid") else "hero", path)
        for method in ops:
            n += 1
            r = anon.get(p) if method == "get" else anon.post(p, {"x": "1"})
            ok = (r.status_code == 303 and "/admin/login" in r.headers.get("location", "")) or (r.status_code == 401)
            if path == "/admin/logout":
                ok = r.status_code in (303, 403)
            if not ok:
                leaks.append((method, p, r.status_code))
    c("D1.1", f"Chưa đăng nhập: {n} route admin đều bị chặn", not leaks, leaks)
    c("D1.2", "audience-count chưa đăng nhập 401", anon.get("/admin/subscribers/audience-count").status_code == 401)

    # ---------- D2. CSRF ----------
    mk_broker(h, "Sàn CSRF")
    kid = s.sql("select id from brokers")[0][0]
    n0 = s.sql("select is_active from brokers where id=?", (kid,))
    no = h.post(f"/admin/brokers/{kid}/toggle", {"field": "is_active"}, raw=True)
    bad = h.post(f"/admin/brokers/{kid}/toggle", {"field": "is_active", "csrf_token": "sai"}, raw=True)
    other = Http().login(EDITOR_EMAIL, EDITOR_PASS)
    cross = h.post(f"/admin/brokers/{kid}/toggle", {"field": "is_active", "csrf_token": other.csrf}, raw=True)
    c("D2.1", "CSRF thiếu/sai/của phiên khác đều 403 và không đổi dữ liệu",
      (no.status_code, bad.status_code, cross.status_code) == (403, 403, 403) and s.sql("select is_active from brokers where id=?", (kid,)) == n0,
      (no.status_code, bad.status_code, cross.status_code))
    r = h.post(f"/admin/brokers/{kid}/toggle", {"field": "is_active", "csrf_token": "é"}, raw=True)
    c("D2.2", "CSRF chứa ký tự không ASCII (đã đăng nhập): 403, không 500", r.status_code == 403, r.status_code)
    r = h.post(f"/admin/brokers/{kid}/toggle", {"field": "is_active"}, files={"csrf_token": ("a.txt", b"x")}, raw=True)
    c("D2.3", "csrf_token gửi dạng file: 403, không 500", r.status_code == 403, r.status_code)
    a2 = Http()
    tok = re.search(r'name="csrf_token" value="([^"]+)"', a2.get("/admin/login").text).group(1)
    r = a2.post("/admin/login", {"email": "x@y.z", "password": "x", "csrf_token": "é"}, raw=True)
    c("D2.4", "Đăng nhập với csrf_token không ASCII (không cần tài khoản): không 500", r.status_code < 500, r.status_code)
    r = httpx.post(BASE + "/admin/login", data={"email": "a", "password": "b", "csrf_token": tok})
    c("D2.5", "Đăng nhập không có cookie CSRF: 403", r.status_code == 403, r.status_code)

    # ---------- D3. Open redirect ----------
    evil = ["//evil.com", "https://evil.com", "/\\evil.com", "\\\\evil.com", "/\t/evil.com", "//evil.com/admin", "/admin@evil.com",
            "/admin/../..//evil.com", "/.//evil.com", "http:evil.com", "/admin\r\nSet-Cookie: x=1", "%2f%2fevil.com", "/%2f/evil.com", "/%5cevil.com", "javascript:alert(1)"]
    bads = []
    for v in evil:
        l = Http()
        tok = re.search(r'name="csrf_token" value="([^"]+)"', l.get("/admin/login").text).group(1)
        r = l.post("/admin/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASS, "csrf_token": tok, "next": v}, raw=True)
        host = urlsplit(urljoin(BASE, r.headers.get("location", ""))).netloc
        if host != f"127.0.0.1:{PORT}" or "set-cookie: x" in str(r.headers).lower():
            bads.append(("login", v, r.headers.get("location")))
        r = httpx.post(BASE + "/api/subscribe", data={"email": "x", "next": v})
        host = urlsplit(urljoin(BASE, r.headers.get("location", ""))).netloc
        if host != f"127.0.0.1:{PORT}" or r.status_code != 303:
            bads.append(("subscribe", v, r.status_code, r.headers.get("location")))
        r = h.post(f"/admin/brokers/{kid}/toggle", {"field": "is_active", "back": v})
        host = urlsplit(urljoin(BASE, r.headers.get("location", ""))).netloc
        if host != f"127.0.0.1:{PORT}":
            bads.append(("back", v, r.headers.get("location")))
        # GET /admin/login?next= khi đã đăng nhập
        r = h.get("/admin/login?next=" + quote(v, safe=""))
        host = urlsplit(urljoin(BASE, r.headers.get("location", ""))).netloc
        if host != f"127.0.0.1:{PORT}":
            bads.append(("login-get", v, r.headers.get("location")))
    c("D3.1", f"{len(evil)} payload next/back không đưa ra ngoài host", not bads, bads[:5])
    # redirect_slashes và đường dẫn đặc biệt
    for p in ("//evil.com/", "///evil.com/", "/\\evil.com/", "/admin//evil.com/", "//evil.com/%2f.."):
        st, _, head = raw_get(p)
        loc = re.search(r"location: (.+)", head, re.I)
        ok = not loc or urlsplit(urljoin(BASE, loc.group(1).strip())).netloc == f"127.0.0.1:{PORT}"
        c(f"D3.2{p}", f"GET {p} không redirect ra ngoài", ok, head[:200])
    # /go/ad không nhận URL từ query
    mk_banner(h, "QC go", target_url="https://ad.example.test/ok")
    ban = s.sql("select id from banners")[0][0]
    c("D3.3", "/go/ad chỉ dùng đích trong DB", pub.get(f"/go/ad/{ban}?url=https://evil.com&target_url=https://evil.com").headers["location"] == "https://ad.example.test/ok")
    for u in ("javascript:alert(1)", "data:text/html,x", "//evil.com", "ftp://x", " javascript:alert(1)", "java\tscript:alert(1)", "http://", "https:evil.com"):
        r1 = h.post("/admin/brokers/new", {"name": "Bad URL", "kind": "forex", "affiliate_url": u, "is_active": "1"})
        r2 = h.post("/admin/ads/new", {"name": "Bad", "placement": "after-bonus", "target_url": u})
        c(f"D3.4{u}", f"URL nguy hiểm bị từ chối: {u!r}", r1.status_code == 400 and r2.status_code == 400, (r1.status_code, r2.status_code))

    # ---------- D4. Path traversal /media + tên thiết bị Windows ----------
    mk = h.post("/admin/media/upload", {"alt": "a"}, files={"files": ("a.png", png_bytes(), "image/png")})
    mp = s.sql("select path from media_files")[0][0]
    hexname = mp.rsplit("/", 1)[1]
    paths = ["/media/../app.db", "/media/..%2fapp.db", "/media/..%5capp.db", "/media/%2e%2e/app.db", "/media/%2e%2e%2fapp.db", "/media/..\\app.db",
             "/media/....//app.db", "/media/..%252fapp.db", "/media/..%c0%afapp.db", "/media//../app.db", "/static/../app/config.py", "/static/..%2fapp%2fconfig.py",
             "/static/..%5capp%5cconfig.py", "/static/..%2f.env", "/static/..%5c.env", "/static/%2e%2e/.env", "/media/C:/Windows/win.ini",
             "/media/C:%5cWindows%5cwin.ini", "/media/%5c%5clocalhost%5cc$%5cwindows%5cwin.ini"]
    hits = []
    for p in paths:
        st, body, head = raw_get(p)
        if st == 200:
            hits.append((p, st, body[:16]))  # chỉ ghi 16 byte đầu để nhận dạng, không in nội dung .env
    c("D4.1", f"{len(paths)} đường dẫn traversal không đọc được file ngoài", not hits, [(a, b) for a, b, _ in hits])
    for p in ("/media/", "/static/", "/static/css/", "/media"):
        st, body, _ = raw_get(p)
        c(f"D4.2{p}", f"Không liệt kê thư mục {p}", st in (404, 405, 307), st)
    odd = ["/media/CON", "/media/NUL", "/media/AUX", "/media/COM1", "/media/LPT1", "/static/NUL", "/static/CON", "/media/CONIN$", "/media/a%00.png",
           "/static/css/site.css%00.png", "/media/" + "a" * 5000, "/static/" + "a/" * 2000, f"/media/{hexname}::$DATA", f"/media/{hexname}.", f"/media/{hexname.upper()}",
           "/media/%ff%fe", "/san/%ff%fe", "/san/%00", "/tin-tuc/%00", "/bonus?type=%00", "/xac-nhan/%00", "/huy-dang-ky/%ff"]
    for p in odd:
        t0 = time.time()
        st, body, head = raw_get(p, timeout=8)
        c(f"D4.3{p[:40]}", f"{p[:50]}: phản hồi nhanh, không 500", st not in (500, -1, 0) and time.time() - t0 < 5, f"st={st} t={time.time() - t0:.1f}s")
    c("D4.4", "Server vẫn sống sau đường dẫn lạ", pub.get("/health", timeout=5).status_code == 200)

    # ---------- D5. Upload ----------
    jpg = io.BytesIO()
    Image.new("RGB", (40, 40), (1, 2, 3)).save(jpg, "JPEG")
    gif = io.BytesIO()
    Image.new("P", (10, 10)).save(gif, "GIF")
    bmp = io.BytesIO()
    Image.new("RGB", (10, 10)).save(bmp, "BMP")
    tiff = io.BytesIO()
    Image.new("RGB", (10, 10)).save(tiff, "TIFF")
    ico = io.BytesIO()
    Image.new("RGB", (16, 16)).save(ico, "ICO")
    webp = io.BytesIO()
    Image.new("RGB", (10, 10)).save(webp, "WEBP")
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>__xss=1</script></svg>'
    html = b"<html><script>__xss=1</script></html>"
    reject = {
        "evil.svg": (svg, "image/svg+xml"), "evil.png": (svg, "image/png"), "x.html": (html, "text/html"), "x.png": (html, "image/png"),
        "x.gif": (gif.getvalue(), "image/gif"), "x.bmp": (bmp.getvalue(), "image/bmp"), "x.tif": (tiff.getvalue(), "image/tiff"), "x.ico": (ico.getvalue(), "image/x-icon"),
        "gifpoly.png": (b"GIF89a/*" + b"\x00" * 20 + b"*/=1;alert(1)", "image/png"), "trunc.png": (png_bytes()[:40], "image/png"), "php.jpg": (b"<?php echo 1; ?>", "image/jpeg"),
    }
    for name, (data, ct) in reject.items():
        before = s.sql("select count(*) from media_files")[0][0]
        r = h.post("/admin/media/upload", {"alt": "x"}, files={"files": (name, data, ct)})
        c(f"D5.r{name}", f"Từ chối {name}", r.status_code == 400 and s.sql("select count(*) from media_files")[0][0] == before, r.status_code)
    good = {"poly.png": (png_bytes(extra=html), "image/png"), "double.php.png": (png_bytes(), "image/png"), "../../../evil.png": (png_bytes(), "image/png"),
            "a.jpg": (jpg.getvalue(), "image/jpeg"), "b.webp": (webp.getvalue(), "image/webp"), "fake-ext.html": (png_bytes(), "text/html"), "tên ảnh 😀.png": (png_bytes(), "image/png")}
    for name, (data, ct) in good.items():
        r = h.post("/admin/media/upload", {"alt": "x"}, files={"files": (name, data, ct)})
        path = s.sql("select path from media_files order by id desc limit 1")[0][0]
        rr = pub.get(path)
        c(f"D5.g{name}", f"Ảnh thật {name}: tên ngẫu nhiên, Content-Type ảnh, nosniff",
          r.status_code == 303 and re.fullmatch(r"/media/[0-9a-f]{32}\.(png|jpg|webp)", path) and rr.headers["content-type"].startswith("image/")
          and rr.headers.get("x-content-type-options") == "nosniff", (r.status_code, path, rr.headers.get("content-type")))
    outside = [p.name for p in s.dir.iterdir() if p.suffix.lower() in (".png", ".php", ".html")]
    c("D5.t", "Tên file ../ không ghi ra ngoài thư mục upload", not outside, outside)
    big = png_bytes(extra=b"\x00" * (5 * 1024 * 1024))
    r = h.post("/admin/media/upload", {"alt": "x"}, files={"files": ("big.png", big, "image/png")})
    c("D5.b", "Trên 5MB bị từ chối với thông báo", r.status_code == 400 and "5MB" in r.text, r.status_code)
    r = h.post("/admin/media/upload", {"alt": "x"}, files={"files": ("<img src=x onerror=__xss=1>.png", b"khong", "image/png")})
    c("D5.x", "Tên file độc hại trong lỗi được escape", r.status_code == 400 and "<img src=x" not in r.text, r.text[:100])
    exif = io.BytesIO()
    ex = Image.Exif()
    ex[0x010F] = "ToaDoGPS-canon"
    Image.new("RGB", (20, 20)).save(exif, "JPEG", exif=ex)
    h.post("/admin/media/upload", {"alt": "exif"}, files={"files": ("e.jpg", exif.getvalue(), "image/jpeg")})
    p = s.sql("select path from media_files order by id desc limit 1")[0][0]
    c("D5.e", "Upload bỏ metadata EXIF (GPS, thiết bị) trước khi công khai", b"ToaDoGPS" not in pub.get(p).content, "file phục vụ nguyên byte, còn EXIF")

    # ---------- D6. SQL injection ----------
    pay = "' OR 1=1--"
    mk_bonus(h, kid, "BonusBinhThuong")
    mk_post(h, "BàiBìnhThường")
    for pth in (f"/bonus?type={quote(pay)}", f"/bonus?sort={quote(pay)}", f"/san?kind={quote(pay)}", f"/tin-tuc?cat={quote(pay)}", "/san/" + quote(pay), "/tin-tuc/" + quote(pay),
                f"/san/so-sanh?ids={quote('1) OR 1=1--')}", f"/xac-nhan/{quote(pay)}", f"/huy-dang-ky/{quote(pay)}"):
        r = pub.get(pth)
        c(f"D6.{pth[:30]}", f"SQLi {pth[:44]}: không 500", r.status_code < 500, r.status_code)
    for pth, sel in ((f"/admin/bonus?q={quote(pay)}", "BonusBinhThuong"), (f"/admin/posts?q={quote(pay)}", "BàiBìnhThường"), (f"/admin/media?q={quote(pay)}", 'src="/media/'), (f"/admin/subscribers?q={quote(pay)}", "@x.co")):
        r = h.get(pth)
        c(f"D6.a{pth[:24]}", f"SQLi {pth[:30]}: không trả toàn bộ dòng", r.status_code == 200 and sel not in r.text, r.status_code)
    c("D6.db", "Bảng còn nguyên", s.sql("select count(*) from brokers")[0][0] >= 1)

    # ---------- D7. Vai trò editor ----------
    e = Http().login(EDITOR_EMAIL, EDITOR_PASS)
    deny = []
    for tab in ("general", "seo", "social", "tracking", "users"):
        if e.get(f"/admin/settings?tab={tab}").status_code != 403:
            deny.append(("GET", tab))
    uid = s.sql("select id from admin_users where email=?", (ADMIN_EMAIL,))[0][0]
    for path, d in (("/admin/settings/tracking", {"analytics_head": "<script>__xss=1</script>"}), ("/admin/settings/general", {"site_name": "Hack"}),
                    ("/admin/settings/users/new", {"email": "h@x.co", "password": "abcdefghij12", "role": "admin"}),
                    (f"/admin/settings/users/{uid}/edit", {"password": "abcdefghij12"}), (f"/admin/settings/users/{uid}/toggle", {}), (f"/admin/settings/users/{uid}/delete", {})):
        if e.post(path, d).status_code != 403:
            deny.append(("POST", path))
    c("D7.1", "Editor bị 403 ở mọi route Cài đặt", not deny, deny)
    c("D7.2", "analytics_head không đổi", s.sql("select count(*) from settings where key='analytics_head'")[0][0] == 0)
    c("D7.3", "Sidebar editor không có Cài đặt", "/admin/settings" not in e.get("/admin").text)
    c("D7.4", "Editor làm được nội dung", e.post("/admin/pages/bonus", {"title": "Editor sửa"}).status_code == 303)
    h.post("/admin/pages/bonus", {"title": "Tất cả bonus sàn giao dịch"})

    # ---------- D8. Phiên ----------
    e2 = Http().login(EDITOR_EMAIL, EDITOR_PASS)
    s.sql("update admin_sessions set expires_at='2000-01-01 00:00:00' where user_id=(select id from admin_users where email=?)", (EDITOR_EMAIL,))
    r = e2.get("/admin/bonus?tab=on")
    c("D8.1", "Phiên hết hạn: GET về login, giữ next", r.status_code == 303 and "next=/admin/bonus%3Ftab%3Don" in r.headers["location"], r.headers.get("location"))
    r = e2.post(f"/admin/brokers/{kid}/toggle", {"field": "is_active"})
    loc = r.headers.get("location", "")
    c("D8.2", "Phiên hết hạn khi POST: về login", r.status_code == 303 and "/admin/login" in loc, (r.status_code, loc))
    l = Http()
    tok = re.search(r'name="csrf_token" value="([^"]+)"', l.get(loc).text).group(1)
    nxt = re.search(r'name="next" value="([^"]+)"', l.get(loc).text).group(1)
    tok = re.search(r'name="csrf_token" value="([^"]+)"', l.get(loc).text).group(1)
    r = l.post("/admin/login", {"email": EDITOR_EMAIL, "password": EDITOR_PASS, "csrf_token": tok, "next": nxt}, raw=True)
    r2 = l.get(r.headers["location"])
    c("D8.3", "Đăng nhập lại sau POST hết hạn (nút Xóa/công tắc): không rơi vào trang 405 trắng", r2.status_code == 200, f"về {r.headers['location']} -> {r2.status_code} {r2.text[:40]!r}")
    # logout thu hồi thật
    x = Http().login(EDITOR_EMAIL, EDITOR_PASS)
    cookie = dict(x.cookies)
    x.post("/admin/logout")
    rep = Http()
    rep.cookies = cookie
    c("D8.4", "Dùng lại cookie sau đăng xuất: bị từ chối", rep.get("/admin").status_code == 303)
    # khóa/xóa user đang đăng nhập
    z = Http().login(EDITOR_EMAIL, EDITOR_PASS)
    eid = s.sql("select id from admin_users where email=?", (EDITOR_EMAIL,))[0][0]
    h.post(f"/admin/settings/users/{eid}/toggle")
    c("D8.5", "Khóa tài khoản: phiên đang mở bị đá ra", z.get("/admin").status_code == 303)
    h.post(f"/admin/settings/users/{eid}/toggle")
    z = Http().login(EDITOR_EMAIL, EDITOR_PASS)
    r = h.post(f"/admin/settings/users/{eid}/delete")
    c("D8.6", "Xóa tài khoản đang có phiên: không 500, phiên mất", r.status_code == 303 and z.get("/admin").status_code == 303, r.status_code)
    # mật khẩu đầu/cuối là khoảng trắng và rất dài
    h.post("/admin/settings/users/new", {"email": "sp@qa.test", "password": "  Khoang-Trang-12  ", "role": "editor"})
    l = Http()
    tok = re.search(r'name="csrf_token" value="([^"]+)"', l.get("/admin/login").text).group(1)
    r = l.post("/admin/login", {"email": "sp@qa.test", "password": "  Khoang-Trang-12  ", "csrf_token": tok}, raw=True)
    c("D8.7", "Mật khẩu có khoảng trắng đầu/cuối: đăng nhập đúng với chuỗi vừa đặt", r.status_code == 303, r.status_code)
    pw = "P" * 300
    h.post("/admin/settings/users/new", {"email": "lng@qa.test", "password": pw, "role": "editor"})
    l = Http()
    tok = re.search(r'name="csrf_token" value="([^"]+)"', l.get("/admin/login").text).group(1)
    r = l.post("/admin/login", {"email": "lng@qa.test", "password": pw, "csrf_token": tok}, raw=True)
    c("D8.8", "Mật khẩu 300 ký tự: đăng nhập được với chuỗi vừa đặt (không cắt thầm)", r.status_code == 303, r.status_code)

    # ---------- D9. IP giả ----------
    def bad_login(ip_header):
        l = Http()
        tok = re.search(r'name="csrf_token" value="([^"]+)"', l.get("/admin/login").text).group(1)
        return l.post("/admin/login", {"email": "khong@qa.test", "password": "sai", "csrf_token": tok}, raw=True, headers=ip_header).status_code
    codes = [bad_login({"X-Forwarded-For": f"1.2.3.{i}"}) for i in range(7)]
    c("D9.1", "X-Forwarded-For không lách được giới hạn 5 lần", codes[-1] == 429, codes)
    codes = [bad_login({"CF-Connecting-IP": f"9.9.9.{i}"}) for i in range(7)]
    print("     CF-Connecting-IP đổi mỗi lần, từ loopback:", codes, flush=True)
    c("D9.2", "CF-Connecting-IP đổi mỗi lần từ loopback: mỗi IP một ngăn (đúng thiết kế, chỉ an toàn khi origin chỉ nghe 127.0.0.1 sau Cloudflare)", 429 not in codes, codes)
    with socket.socket() as so:
        so.settimeout(1)
        lan = socket.gethostbyname(socket.gethostname())
        c("D9.3", "Server không nghe trên IP LAN", so.connect_ex((lan, PORT)) != 0, lan)
    r = pub.get("/", headers={"Host": "evil.com", "X-Forwarded-Host": "evil.com", "X-Forwarded-Proto": "https"})
    c("D9.4", "Host/X-Forwarded-Host giả không vào canonical", "evil.com" not in r.text)

    # ---------- D10. Seed XSS khắp nơi ----------
    r = mk_broker(h, XSS[:250], slug="xss-san", tagline=XSS, summary=XSS, license=XSS, min_deposit=XSS[:60], leverage=XSS[:60], platforms=XSS, spread=XSS[:60],
                  withdrawal=XSS[:120], founded=XSS[:20], mono="<i", pros=XSS, cons=XSS, affiliate_url=URL_HTTP, in_compare="1", featured="1")
    kx = s.sql("select id from brokers where slug='xss-san'")[0][0]
    h.post(f"/admin/brokers/{kx}/edit", [("name", XSS[:250]), ("slug", "xss-san"), ("kind", "forex"), ("is_active", "1"), ("in_compare", "1"), ("featured", "1"), ("tagline", XSS), ("summary", XSS),
                                        ("founded", XSS), ("affiliate_url", URL_HTTP), ("pros", XSS), ("cons", XSS), ("license", XSS),
                                        ("account_name", XSS), ("account_min_deposit", XSS), ("account_spread", XSS), ("account_commission", XSS),
                                        ("payment_method", XSS), ("payment_deposit", XSS), ("payment_withdraw", XSS), ("payment_time", XSS)])
    mk_bonus(h, kx, XSS, amount=XSS[:60], min_deposit=XSS[:60], withdrawable=XSS[:60])
    md = (XSS + "\n\n<script>__xss=1</script>\n\n<img src=x onerror=__xss=1>\n\n[a](javascript:__xss=1)\n\n[b](JaVaScRiPt:__xss=1)\n\n[c](data:text/html,<script>__xss=1</script>)\n\n"
          "![d](javascript:__xss=1)\n\n<a href=\"javascript:__xss=1\">e</a>\n\n<iframe src=\"javascript:__xss=1\"></iframe>\n\n<svg onload=__xss=1></svg>\n\n<style>body{background:url(javascript:__xss=1)}</style>\n\n"
          "<form action=\"javascript:__xss=1\"><button>f</button></form>\n\n<math><mtext><table><mglyph><style><img src=x onerror=__xss=1></style>\n\n[g](&#106;avascript:__xss=1)\n\n`<img src=x onerror=__xss=1>`\n\n"
          "<div style=\"position:fixed;inset:0\" onclick=\"__xss=1\">h</div>\n\n[i](x \"t\\\" onmouseover=\\\"__xss=1\")\n")
    mk_post(h, XSS, slug="xss-bai", excerpt=XSS, body_md=md, category="Tin sàn")
    mk_banner(h, XSS[:120], placement="rail-left", broker_id=kx, target_url="https://ad.example.test/1")
    mk_banner(h, XSS[:120], placement="before-blog", broker_id=kx, target_url="https://ad.example.test/2")
    h.post("/admin/media/upload", {"alt": XSS[:255]}, files={"files": ("n.png", png_bytes(), "image/png")})
    pub.post("/api/subscribe", data={"name": XSS, "email": "xss@x.co", "interests": ["nodep"], "next": "/"}, headers={"CF-Connecting-IP": "8.8.0.1"})
    pub.post("/api/contact", data={"topic": XSS, "name": XSS, "email": "xss@x.co", "body": XSS}, headers={"CF-Connecting-IP": "8.8.0.2"})
    h.post("/admin/subscribers/mail", {"subject": XSS, "body": XSS, "action": "draft"})
    tabs = []
    for t in ("sections", "hero", "about", "why", "types", "contact", "menu"):
        tabs.append((f"/admin/home?tab={t}", f"/admin/home/{t}"))
    for t in ("bonus", "san", "tin", "gioithieu", "lienhe", "terms", "privacy", "system"):
        tabs.append((f"/admin/pages?tab={t}", f"/admin/pages/{t}"))
    for t in ("general", "seo", "social"):
        tabs.append((f"/admin/settings?tab={t}", f"/admin/settings/{t}"))
    for page, action in tabs:
        st, n = fuzz_tab(h, page, action)
        c(f"D10.s{action}", f"Lưu payload vào {n} ô của {action}", st == 303 and n > 0, (st, n))

    urls = ["/", "/bonus", "/bonus?type=deposit", "/san", "/san/so-sanh", f"/san/so-sanh?ids={kx}", "/san/xss-san", "/san/xss-san?tab=bonus", "/san/xss-san?tab=accounts", "/san/xss-san?tab=pay",
            "/tin-tuc", "/tin-tuc/xss-bai", "/gioi-thieu", "/gioi-thieu/cach-danh-gia", "/gioi-thieu/affiliate", "/lien-he", "/dieu-khoan", "/bao-mat", "/khong-co-trang",
            "/xac-nhan/saitoken", "/bonus?type=<script>__xss=1</script>", "/tin-tuc?cat=\"><svg/onload=__xss=1>", "/san?kind=\"><svg/onload=__xss=1>", "/admin/login?next=\"><svg/onload=__xss=1>"]
    admin_urls = ["/admin", "/admin/bonus", "/admin/bonus/new", f"/admin/bonus/{s.sql('select max(id) from bonuses')[0][0]}/edit", "/admin/brokers", "/admin/brokers?tab=links", f"/admin/brokers/{kx}/edit",
                  "/admin/ads", "/admin/ads?tab=stats", f"/admin/ads/{s.sql('select max(id) from banners')[0][0]}/edit", "/admin/posts", f"/admin/posts/{s.sql('select max(id) from posts')[0][0]}/edit",
                  "/admin/media", "/admin/subscribers", "/admin/subscribers?tab=mail", f"/admin/subscribers?tab=mail&draft={s.sql('select max(id) from campaigns')[0][0]}", "/admin/messages",
                  f"/admin/messages/{s.sql('select max(id) from contact_messages')[0][0]}", "/admin/settings?tab=users", "/admin/bonus?q=\"><svg/onload=__xss=1>", "/admin/posts?q=\"><svg/onload=__xss=1>",
                  "/admin/media?q=\"><svg/onload=__xss=1>", "/admin/subscribers?q=\"><svg/onload=__xss=1>"] + [p for p, _ in tabs]
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={"width": 1700, "height": 1000}, bypass_csp=True)
        pg = ctx.new_page()
        dlg = []
        pg.on("dialog", lambda d: (dlg.append(d.message), d.dismiss()))
        # /admin/login trước khi đăng nhập
        fails = []
        check = """() => ({x: window.__xss, imgs: document.querySelectorAll('img[src="x"]').length, svg: document.querySelectorAll('svg[onload]').length,
                  scr: [...document.scripts].filter(s => s.textContent.includes('__xss')).length,
                  ev: [...document.querySelectorAll('*')].filter(e => [...e.attributes].some(a => /^on/.test(a.name))).length,
                  jsurl: [...document.querySelectorAll('a[href], form[action], iframe[src]')].filter(e => /^\\s*(javascript|data):/i.test(e.getAttribute('href') || e.getAttribute('action') || e.getAttribute('src') || '')).length})"""
        for u in urls:
            pg.goto(BASE + u)
            pg.wait_for_timeout(120)
            res = pg.evaluate(check)
            if res["x"] or res["imgs"] or res["svg"] or res["scr"] or res["ev"] or res["jsurl"]:
                fails.append((u, res))
        c("D10.1", f"{len(urls)} trang public: không có HTML/JS lọt ra từ payload", not fails and not dlg, fails[:4])
        t = pg.goto(BASE + "/").text()
        c("D10.2", "SSTI: {{7*7}} không được tính", "49" not in re.sub(r"<[^>]+>", "", t) or "{{7*7}}" in t)
        pg.goto(BASE + "/admin/login")
        pg.fill("input[name=email]", ADMIN_EMAIL)
        pg.fill("input[name=password]", ADMIN_PASS)
        pg.click("button[type=submit]")
        pg.wait_for_load_state()
        fails = []
        for u in admin_urls:
            pg.goto(BASE + u)
            pg.wait_for_timeout(120)
            res = pg.evaluate(check)
            if res["x"] or res["imgs"] or res["svg"] or res["scr"] or res["ev"] or res["jsurl"]:
                fails.append((u, res))
        c("D10.3", f"{len(admin_urls)} trang admin: không có HTML/JS lọt ra", not fails and not dlg, fails[:4])
        # hover/mở hộp chọn ảnh, xem trước trực tiếp
        pg.goto(BASE + "/admin/home?tab=hero")
        pg.fill("input[name=eyebrow]", XSS)
        pg.wait_for_timeout(200)
        res = pg.evaluate(check)
        c("D10.4", "Xem trước trực tiếp không chèn HTML", not res["x"] and not res["imgs"], res)
        pg.goto(BASE + f"/admin/brokers/{kx}/edit")
        res = pg.evaluate(check)
        c("D10.5", "Editor dòng (pros, tài khoản) không chèn HTML", not res["x"] and not res["imgs"], res)
        b.close()
    t = pub.get("/tin-tuc/xss-bai").text
    i = t.find('class="prose"')
    body = t[i:t.find("</article>", i) if "</article>" in t[i:] else i + 6000]
    c("D10.6", "Markdown: không còn thẻ/thuộc tính nguy hiểm thật (chữ đã escape không tính)", not re.search(r"<(script|iframe|form|style|svg|math)\b|<[^>]*\son\w+=", body), body[:300])
    c("D10.7", "Không có khối JSON-LD (nếu thêm sau này phải escape </script>)", "ld+json" not in t, "có ld+json")

    # ---------- D11. Analytics bật CSP nới lỏng ----------
    h2 = Http().login()
    h2.post("/admin/settings/tracking", {"analytics_head": "<script>window.dataLayer=[1];</script>"})
    r = pub.get("/bonus")
    c("D11.1", "Có analytics: public nới script-src, in đoạn mã", "'unsafe-inline'" in r.headers["content-security-policy"].split("script-src")[1].split(";")[0] and "window.dataLayer" in r.text)
    c("D11.2", "Admin vẫn CSP chặt khi có analytics", "'unsafe-inline'" not in h2.get("/admin").headers["content-security-policy"].split("script-src")[1].split(";")[0])
    c("D11.3", "Trang noindex/404 không in analytics", "window.dataLayer" not in pub.get("/khong-co").text)
    h2.post("/admin/settings/tracking", {"analytics_head": ""})
finally:
    s.stop()

# =========================== Server production ===========================
s = Server("sec_prod", env={"APP_ENV": "production", "SECRET_KEY": "qa-prod-secret-" + "y" * 40}).start()
s.cli_admin()
try:
    an = Http()
    for p in ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
        c(f"D12.{p}", f"Production: {p} 404", an.get(p).status_code == 404)
    r = an.get("/admin/login")
    sc = r.headers.get("set-cookie", "")
    c("D12.c1", "Cookie CSRF đăng nhập: HttpOnly, Secure, SameSite=Lax", all(x in sc.lower() for x in ("httponly", "secure", "samesite=lax")), sc)
    h = Http()
    tok = re.search(r'name="csrf_token" value="([^"]+)"', h.get("/admin/login").text).group(1)
    r = h.post("/admin/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASS, "csrf_token": tok}, raw=True)
    sess = [x for x in r.headers.get_list("set-cookie") if x.startswith("tbh_session")][0]
    c("D12.c2", "Cookie phiên: HttpOnly, Secure, SameSite=Lax, Max-Age 7 ngày", all(x in sess.lower() for x in ("httponly", "secure", "samesite=lax", "max-age=604800", "path=/")), sess)
    h.refresh_csrf()
    r = h.post("/admin/pages/bonus", {"title": "X"})
    fl = r.headers.get("set-cookie", "")
    c("D12.c3", "Cookie flash: HttpOnly, Secure", all(x in fl.lower() for x in ("httponly", "secure")), fl)
    tok_val = h.cookies["tbh_session"]
    c("D12.c4", "DB lưu hash của token, không lưu token gốc", s.sql("select count(*) from admin_sessions where token_hash=?", (tok_val,))[0][0] == 0)
    pages = {"public": "/", "public2": "/bonus", "404": "/khong-co", "static": "/static/css/site.css", "login": "/admin/login", "redirect": "/admin", "sitemap": "/sitemap.xml", "robots": "/robots.txt", "health": "/health"}
    for name, p in pages.items():
        r = an.c.get(BASE + p)
        miss = [k for k in ("content-security-policy", "x-content-type-options", "x-frame-options", "referrer-policy", "permissions-policy", "strict-transport-security") if k not in r.headers]
        c(f"D13.{name}", f"Header bảo mật đủ ở {p}", not miss, miss)
    r = an.c.get(BASE + "/go/broker/99999999999999999999999")
    miss = [k for k in ("content-security-policy", "x-content-type-options", "x-frame-options", "strict-transport-security") if k not in r.headers]
    c("D13.500", "Header bảo mật có cả ở trang 500", r.status_code == 500 and not miss, (r.status_code, miss))
    c("D13.500b", "Trang 500 production không lộ traceback", "Traceback" not in r.text and "OverflowError" not in r.text)
    r = h.get("/admin")
    c("D13.a", "Admin: no-store, noindex", r.headers.get("cache-control") == "no-store" and "noindex" in r.headers.get("x-robots-tag", ""))
    c("D13.sv", "Không lộ header server", "server" not in r.headers, r.headers.get("server"))
finally:
    s.stop()

# APP_ENV gõ sai (fail-open?)
s = Server("sec_env", env={"APP_ENV": "prod", "SECRET_KEY": ""}).start()
try:
    r = httpx.get(BASE + "/docs")
    c("D14.1", "APP_ENV=prod (gõ tắt): không âm thầm chạy chế độ dev (mở /docs, cookie không Secure, SECRET_KEY ngẫu nhiên)", r.status_code == 404, f"/docs={r.status_code}")
finally:
    s.stop()
s = Server("sec_nokey", env={"APP_ENV": "production", "SECRET_KEY": ""})
try:
    s.start(wait=15)
    c("D14.2", "Production thiếu SECRET_KEY: từ chối chạy", False, "server vẫn chạy")
except RuntimeError:
    c("D14.2", "Production thiếu SECRET_KEY: từ chối chạy", "Thiếu SECRET_KEY" in s.log_text())
finally:
    s.stop()
s = Server("sec_weak", env={"APP_ENV": "production", "SECRET_KEY": "x"}).start()
s.stop()
c("D14.3", "SECRET_KEY quá ngắn ('x') bị từ chối ở production", False, "chấp nhận khóa 1 ký tự")
R.save()
