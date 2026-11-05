"""Vai F: vận hành. Restart, WAL, migration, proxy https, sitemap/robots, sao lưu theo README, tải đồng thời."""
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import httpx
from playwright.sync_api import sync_playwright

from qalib import (ADMIN_EMAIL, ADMIN_PASS, BASE, PY, ROOT, WORK, Http, Report, Server, mk_banner, mk_bonus, mk_broker, mk_post, png_bytes, prod_env)

R = Report("s6_ops")
c = R.check
pub = httpx.Client(base_url=BASE, timeout=30)

# ---------- F1. Migration trên DB trống ----------
d = WORK / "mig"
shutil.rmtree(d, ignore_errors=True)
d.mkdir(parents=True)
env = {**os.environ, "DATABASE_URL": f"sqlite:///{(d / 'm.db').as_posix()}", "APP_ENV": "development", "PYTHONUTF8": "1"}
al = [PY, "-m", "alembic"]
r = subprocess.run(al + ["upgrade", "head"], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
c("F1.1", "alembic upgrade head trên DB trống", r.returncode == 0, r.stderr[-300:])
r = subprocess.run(al + ["check"], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
c("F1.2", "alembic check: models khớp migration, không thiếu cột", r.returncode == 0, (r.stdout + r.stderr)[-400:])
con = sqlite3.connect(d / "m.db")
tb = sorted(x[0] for x in con.execute("select name from sqlite_master where type='table' and name not like 'sqlite%'"))
c("F1.3", "Đủ 13 bảng", len(tb) == 13, tb)
con.close()
r = subprocess.run(al + ["downgrade", "base"], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
c("F1.4", "downgrade base chạy được", r.returncode == 0, r.stderr[-300:])
r = subprocess.run(al + ["upgrade", "head"], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
c("F1.5", "upgrade lại sau downgrade", r.returncode == 0, r.stderr[-300:])

# ---------- F2. Restart, WAL, ảnh ----------
s = Server("ops", env=prod_env())
s.start()
s.cli_admin()
h = Http().login()
h.post("/admin/media/upload", {"alt": "ảnh"}, files={"files": ("a.png", png_bytes(), "image/png")})
mp = s.sql("select path from media_files")[0][0]
mk_broker(h, "Sàn Restart", logo_path=mp)
kid = s.sql("select id from brokers")[0][0]
mk_bonus(h, kid, "Bonus Restart")
mk_post(h, "Bài Restart")
for _ in range(3):
    pub.get(f"/go/broker/{kid}")
r = sqlite3.connect(s.db).execute("pragma journal_mode").fetchone()[0]
c("F2.1", "journal_mode=wal trong DB thật", r == "wal", r)
c("F2.2", "File -wal tồn tại khi đang chạy", (s.dir / "app.db-wal").exists())
s.stop()
s.start()
c("F2.3", "Restart: dữ liệu còn", "Bonus Restart" in pub.get("/bonus").text and s.sql("select clicks from brokers")[0][0] == 3)
c("F2.4", "Restart: ảnh còn", pub.get(mp).status_code == 200)
r = h.get("/admin")
c("F2.5", "Restart (SECRET_KEY cố định): phiên còn", r.status_code == 200, r.status_code)
# kill -9 giữa chừng
mk_post(h, "Bài trước khi tắt nóng")
subprocess.run(["taskkill", "/T", "/F", "/PID", str(s.proc.pid)], capture_output=True)
s.stop()
s.start()
c("F2.6", "Tắt nóng: dữ liệu đã commit còn", "Bài trước khi tắt nóng" in pub.get("/tin-tuc").text)
c("F2.7", "integrity_check ok", s.sql("pragma integrity_check")[0][0] == "ok")

# ---------- F3. Sao lưu đúng theo README rồi phục hồi ----------
c("F3.0", "README có hướng dẫn sao lưu", "Sao lưu" in (ROOT / "README.md").read_text(encoding="utf-8"))
readme = (ROOT / "README.md").read_text(encoding="utf-8")
c("F3.1", "README có hướng dẫn phục hồi", re.search(r"[Pp]hục hồi|[Kk]hôi phục|restore", readme), "chỉ có 1 dòng 'Sao lưu: copy data/app.db* và data/uploads/'")
stop = threading.Event()


def writer():
    i = 0
    w = Http()
    while not stop.is_set():
        try:
            w.get(f"/go/broker/{kid}")
        except httpx.HTTPError:
            pass
        i += 1
        time.sleep(0.002)


writers = [threading.Thread(target=writer) for _ in range(4)]
[t.start() for t in writers]
bad, n = 0, 40
last = None
bk = WORK / "bk"
for i in range(n):
    shutil.rmtree(bk, ignore_errors=True)
    bk.mkdir()
    # đúng README mới: sqlite3 backup khi đang chạy
    src, dst = sqlite3.connect(s.db, timeout=15), sqlite3.connect(bk / "app.db")
    src.backup(dst)
    dst.close()
    src.close()
    try:
        cn = sqlite3.connect(bk / "app.db")
        ok = cn.execute("pragma integrity_check").fetchone()[0]
        cn.close()
    except sqlite3.DatabaseError as e:
        ok = str(e)
    if ok != "ok":
        bad += 1
        last = ok
stop.set()
[t.join() for t in writers]
c("F3.2", f"Sao lưu bằng sqlite3 backup khi site đang ghi ({n} lần): bản sao toàn vẹn", bad == 0, f"{bad}/{n} bản hỏng: {str(last)[:160]}")
s.stop()
shutil.rmtree(WORK / "ops_rs", ignore_errors=True)
s2 = Server("ops_rs", env=s.env | {"DATABASE_URL": f"sqlite:///{(WORK / 'ops_rs' / 'app.db').as_posix()}", "UPLOAD_DIR": str(WORK / "ops_rs" / "up")})
for name in ("app.db", "app.db-wal", "app.db-shm"):
    if (s.dir / name).exists():
        shutil.copy2(s.dir / name, s2.dir / name)
shutil.copytree(s.uploads, s2.uploads, dirs_exist_ok=True)
s2.start()
c("F3.3", "Phục hồi từ bản sao lạnh: dữ liệu + ảnh", "Bonus Restart" in pub.get("/bonus").text and pub.get(mp).status_code == 200)
s2.stop()

# ---------- F4. Proxy https, BASE_URL https ----------
kp, cp = WORK / "qa.key", WORK / "qa.crt"
ossl = shutil.which("openssl") or r"C:\Program Files\Git\mingw64in\openssl.exe"
subprocess.run([ossl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(kp), "-out", str(cp), "-days", "30",
                "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost"], check=True, capture_output=True)
PBASE = "https://localhost:8016"
s = Server("ops_px", env=prod_env(BASE_URL=PBASE + "/")).start()
s.cli_admin()
px = subprocess.Popen([PY, str(ROOT / "qa" / "https_proxy.py"), str(cp), str(kp), "8016", "8014"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            if httpx.get(PBASE + "/health", verify=False, timeout=2).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.2)
    errs = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(ignore_https_errors=True)
        ctx.route("**/*", lambda r: r.fulfill(status=200, body="", content_type="text/css") if "fonts.g" in r.request.url else r.continue_())
        pg = ctx.new_page()
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.goto(PBASE + "/admin/login")
        pg.fill("input[name=email]", ADMIN_EMAIL)
        pg.fill("input[name=password]", ADMIN_PASS)
        with pg.expect_navigation():
            pg.click("button[type=submit]")
        c("F4.1", "Đăng nhập qua https proxy (production, cookie Secure)", pg.url.rstrip("/").endswith("/admin"), pg.url)
        ck = {x["name"]: x for x in ctx.cookies()}
        c("F4.2", "Cookie phiên Secure+HttpOnly+Lax trong trình duyệt", ck["tbh_session"]["secure"] and ck["tbh_session"]["httpOnly"] and ck["tbh_session"]["sameSite"] == "Lax", ck.get("tbh_session"))
        pg.goto(PBASE + "/admin/brokers/new")
        pg.fill("input[name=name]", "Sàn Proxy")
        pg.fill("input[name=affiliate_url]", "https://aff.example.test/p")
        with pg.expect_navigation():
            pg.click(".drawer-foot .btn-save")
        c("F4.3", "POST qua proxy, redirect giữ https", pg.url.startswith(PBASE + "/admin/brokers"), pg.url)
        c("F4.4", "Không lỗi console/CSP/mixed content qua https", not errs, errs[:4])
        b.close()
    hx = httpx.Client(verify=False, base_url=PBASE, timeout=20)
    t = hx.get("/").text
    c("F4.5", "canonical https đúng BASE_URL (có / cuối vẫn chuẩn)", f'rel="canonical" href="{PBASE}/"' in t, re.findall(r'rel="canonical" href="[^"]+"', t))
    sm = hx.get("/sitemap.xml").text
    root = ET.fromstring(sm)
    locs = [e.text for e in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    c("F4.6", "Sitemap XML hợp lệ, mọi loc là https BASE_URL, có sàn", locs and all(u.startswith(PBASE + "/") for u in locs) and any("/san/san-proxy" in u for u in locs), locs[:3])
    rb = hx.get("/robots.txt").text
    c("F4.7", "robots: Disallow admin/go/api/xác nhận, Sitemap https", f"Sitemap: {PBASE}/sitemap.xml" in rb and "Disallow: /admin" in rb and "Disallow: /go/" in rb, rb)
    r = hx.get("/bonus/")
    loc = r.headers.get("location", "")
    c("F4.8", "URL có / cuối qua proxy: không redirect về http:// (hạ cấp) hay lộ origin", (not loc) or loc.startswith("/") or loc.startswith("https://"), f"{r.status_code} {loc}")
    # rate limit theo IP thật từ CF-Connecting-IP
    hx.post("/api/subscribe", data={"email": "p@qa.test", "next": "/"}, headers={"X-Test-Real-IP": "198.51.100.1"})
    log = s.log_text()
    c("F4.9", "Link trong email là https BASE_URL", f"{PBASE}/xac-nhan/" in log and f"{PBASE}/huy-dang-ky/" in log)
    codes = [hx.post("/api/subscribe", data={"email": f"pp{i}@qa.test", "next": "/"}, headers={"X-Test-Real-IP": "198.51.100.2", "CF-Connecting-IP": f"1.1.1.{i}"}).headers.get("set-cookie", "") for i in range(6)]
    c("F4.10", "Qua proxy: client tự gửi CF-Connecting-IP giả không lách được (proxy ghi đè)", "sub_rate" in codes[-1], codes[-1][:50])
    pg_noindex = hx.get("/admin/login")
    c("F4.11", "Login có noindex", "noindex" in pg_noindex.text)
finally:
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(px.pid)], capture_output=True)
    s.stop()

# ---------- F5. Thiếu cấu hình production: từ chối chạy ----------
for cid, drop, want in (("F5.1", "BASE_URL", "Thiếu BASE_URL"), ("F5.3", "SMTP_BACKEND", "Thiếu SMTP_BACKEND")):
    s = Server("ops_cfg", env=prod_env())
    s.env.pop(drop)
    try:
        s.start(wait=15)
        c(cid, f"Production thiếu {drop}: từ chối chạy", False, "server vẫn chạy")
    except RuntimeError:
        c(cid, f"Production thiếu {drop}: thoát, báo rõ", want in s.log_text() and "Traceback" not in s.log_text(), s.log_text()[-240:])
    finally:
        s.stop()
s = Server("ops_warn", env=prod_env()).start()
c("F5.2", "SMTP_BACKEND=console ở production: có cảnh báo lúc khởi động", "email KHÔNG được gửi" in s.log_text(), s.log_text()[-200:])
s.stop()

# ---------- F6. Tải đồng thời ----------
s = Server("ops_load").start()
s.cli_admin()
h = Http().login()
mk_broker(h, "Tải", in_compare="1", featured="1")
kid = s.sql("select id from brokers")[0][0]
for i in range(8):
    mk_bonus(h, kid, f"B{i}")
for i in range(5):
    mk_post(h, f"P{i}")
mk_banner(h, "L1", placement="after-bonus")
ban = s.sql("select id from banners")[0][0]
N = 300


def hit(i):
    with httpx.Client(timeout=60) as x:
        p = ["/", f"/go/broker/{kid}", "/bonus", f"/go/ad/{ban}", "/tin-tuc/p1"][i % 5]
        t0 = time.time()
        r = x.get(BASE + p)
        return p, r.status_code, time.time() - t0


t0 = time.time()
with ThreadPoolExecutor(60) as ex:
    res = list(ex.map(hit, range(N)))
dur = time.time() - t0
codes = {}
for _, st, _ in res:
    codes[st] = codes.get(st, 0) + 1
slow = max(x[2] for x in res)
c("F6.1", f"{N} request, 60 luồng: không 5xx", all(k < 500 for k in codes), codes)
print(f"     {N} req trong {dur:.1f}s, chậm nhất {slow:.2f}s", flush=True)
c("F6.2", "Click đếm chính xác dưới tải (không mất lượt)", s.sql("select clicks from brokers")[0][0] == N // 5 and s.sql("select clicks from banners")[0][0] == N // 5, s.sql("select clicks from brokers") + s.sql("select clicks from banners"))
c("F6.3", "Lượt xem bài chính xác", s.sql("select views from posts where slug='p1'")[0][0] == N // 5, s.sql("select views from posts where slug='p1'"))
c("F6.4", "ClickLog khớp", s.sql("select sum(count) from click_logs")[0][0] == 2 * (N // 5), s.sql("select kind,sum(count) from click_logs group by kind"))
c("F6.5", "Không 'database is locked' / QueuePool trong log", not re.search(r"database is locked|QueuePool limit", s.log_text()))
s.stop()
bad = R.save()
