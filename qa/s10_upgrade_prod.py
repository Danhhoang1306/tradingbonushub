"""Vòng 2: (A) nâng cấp thật: DB + dữ liệu tạo bằng code commit 9c29ee1 (schema 0001), rồi chạy code hiện tại.
(B) quy trình production trong README trên bản git archive + venv mới, cổng 8014, BASE_URL giả, SMTP_BACKEND=console,
proxy TLS 8016. Lệnh sao lưu lấy nguyên văn từ README."""
import atexit
import io
import os
import re
import shutil
import sqlite3
import subprocess
import tarfile
import time

import httpx
from playwright.sync_api import sync_playwright

from qalib import ADMIN_EMAIL, ADMIN_PASS, BASE, PORT, PROD_KEY, PY, ROOT, WORK, Http, Report, Server, mk_banner, mk_bonus, mk_broker, mk_post, png_bytes

R = Report("s10_upgrade_prod")
c = R.check
pub = httpx.Client(base_url=BASE, timeout=30)


def extract(rev, dest):
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    tar = subprocess.run(["git", "archive", rev], cwd=ROOT, capture_output=True, check=True).stdout
    tarfile.open(fileobj=io.BytesIO(tar)).extractall(dest, filter="data")


# ===================== A. Nâng cấp từ 0001 có dữ liệu =====================
OLD = WORK / "old_code"
extract("9c29ee1", OLD)
env_up = {"SECRET_KEY": "qa-upgrade-secret-" + "u" * 30}
s = Server("up", env=env_up)
s.cwd = OLD
s.start()
s.cli_admin()
h = Http().login()
h.post("/admin/media/upload", {"alt": "logo"}, files={"files": ("l.png", png_bytes(), "image/png")})
mp = s.sql("select path from media_files")[0][0]
mk_broker(h, "Sàn Cũ", logo_path=mp, in_compare="1", featured="1")
mk_broker(h, "Sàn Không Giấy Phép", license="")
kid = s.sql("select id from brokers order by id")[0][0]
mk_bonus(h, kid, "Bonus Cũ", expiry_date="2030-01-01")
mk_post(h, "Bài Cũ")
mk_banner(h, "QC Cũ", broker_id=kid, target_url="", placement="after-bonus", image_path=mp)
pub.get("/")
pub.get(f"/go/broker/{kid}")
for em, ip in (("cho@qa.test", "1"), ("xn@qa.test", "2"), ("huy@qa.test", "3")):
    pub.post("/api/subscribe", data={"email": em, "interests": ["crypto"], "next": "/"}, headers={"CF-Connecting-IP": f"9.1.1.{ip}"})
tok = {e: s.tokens(e)[-1] for e in ("cho@qa.test", "xn@qa.test", "huy@qa.test")}
pub.get(f"/xac-nhan/{tok['xn@qa.test']}")
pub.get(f"/xac-nhan/{tok['huy@qa.test']}")
pub.get(f"/huy-dang-ky/{tok['huy@qa.test']}")
pub.post("/api/contact", data={"topic": "Hợp tác", "name": "K", "email": "k@qa.test", "body": "Xin chào 😀"}, headers={"CF-Connecting-IP": "9.1.1.4"})
h.post("/admin/subscribers/mail", {"subject": "Đã gửi cũ", "body": "x", "action": "send"})
h.post("/admin/subscribers/mail", {"subject": "Nháp cũ", "body": "x", "action": "draft"})
h.post("/admin/subscribers/mail", {"subject": "Kẹt cũ", "body": "x", "action": "draft"})
s.sql("update campaigns set status='sending' where subject='Kẹt cũ'")
hero_form = re.findall(r'name="(\w+)"[^>]*value="([^"]*)"', h.get("/admin/home?tab=hero").text)
h.post("/admin/home/hero", {"eyebrow": "E", "headline": "H cũ", "sub": "S", "cta": "C", "card_label": "L", "image_path": "/static/img/hero-bg.webp"})
h.post("/admin/pages/san", {"title": "Sàn đã sửa", "desc": "D", "meta_title": "", "meta_desc": ""})
h.post("/admin/settings/general", {"site_name": "Tên Cũ", "contact_email": "a@qa.test", "partner_email": "", "telegram": ""})
TABLES = ["admin_users", "admin_sessions", "brokers", "bonuses", "posts", "banners", "subscribers", "contact_messages", "campaigns", "settings", "media_files", "click_logs"]
before = {t: s.sql(f"select count(*) from {t}")[0][0] for t in TABLES}
rows_before = s.sql("select email,status,token,interests,confirmed_at from subscribers order by id")
c("U0", "DB cũ ở revision 0001", s.sql("select version_num from alembic_version") == [("0001",)], s.sql("select version_num from alembic_version"))
s.stop()

s = Server("up", env=env_up, fresh=False).start()
try:
    c("U1", "run.py nâng lên head (0003)", s.sql("select version_num from alembic_version") == [("0003",)], s.sql("select version_num from alembic_version"))
    after = {t: s.sql(f"select count(*) from {t}")[0][0] for t in TABLES}
    c("U2", "Số dòng mọi bảng không đổi", before == after, {k: (before[k], after[k]) for k in before if before[k] != after[k]})
    c("U3", "Subscriber giữ nguyên email/token/trạng thái", s.sql("select email,status,token,interests,confirmed_at from subscribers order by id") == rows_before)
    c("U4", "Cột mới có giá trị mặc định", s.sql("select count(*) from subscribers where confirm_count=0 and confirm_sent_at is null")[0][0] == 3 and s.sql("select count(*) from campaigns where sent_to='[]'")[0][0] == 3)
    ddl = dict(s.sql("select name, sql from sqlite_master where type='table'"))
    c("U5", "Sau batch alter còn UNIQUE email/token", "email" in ddl["subscribers"] and s.sql("select count(*) from sqlite_master where tbl_name='subscribers' and type='index'")[0][0] >= 2, ddl["subscribers"][:300])
    r = subprocess.run([PY, "-m", "alembic", "check"], cwd=ROOT, env=s.env, capture_output=True, text=True, encoding="utf-8")
    c("U6", "alembic check không lệch", r.returncode == 0, (r.stdout + r.stderr)[-200:])
    h2 = Http()
    h2.cookies, h2.csrf = dict(h.cookies), h.csrf
    c("U7", "Phiên admin cũ còn dùng được (SECRET_KEY giữ nguyên)", h2.get("/admin").status_code == 200)
    st = dict(s.sql("select subject,status from campaigns"))
    c("U8", "Chiến dịch: sent giữ, nháp giữ, kẹt về draft", st == {"Đã gửi cũ": "sent", "Nháp cũ": "draft", "Kẹt cũ": "draft"}, st)
    r = pub.post(f"/xac-nhan/{tok['cho@qa.test']}")
    c("U9", "Link xác nhận cũ trong email đã gửi: GET hiện nút, POST xác nhận được", r.status_code == 200 and s.sql("select status from subscribers where email='cho@qa.test'")[0][0] == "confirmed")
    r = pub.get(f"/huy-dang-ky/{tok['xn@qa.test']}")
    c("U10", "Link hủy trong email cũ vẫn dùng được", r.status_code == 200 and f'/huy-dang-ky/{tok["xn@qa.test"]}"' in r.text)
    t = pub.get("/").text
    c("U11", "Trang chủ 200, dữ liệu cũ còn", "Bonus Cũ" in t and "Tên Cũ" in t and "H cũ" in t)
    c("U12", "Ảnh hero đã lưu trỏ file vừa bị xóa khỏi repo: không phải ảnh gãy", "hero-bg.webp" not in t or pub.get("/static/img/hero-bg.webp").status_code == 200, f"HTML còn hero-bg.webp, file trả {pub.get('/static/img/hero-bg.webp').status_code}")
    c("U13", "Trang mới dùng khóa pages cũ: /san/so-sanh, phương pháp, affiliate 200", all(pub.get(p).status_code == 200 for p in ("/san/so-sanh", "/gioi-thieu/cach-danh-gia", "/gioi-thieu/affiliate")))
    c("U14", "Sàn cũ không có giấy phép vẫn hiển thị", pub.get("/san/san-khong-giay-phep").status_code == 200)
    kk = s.sql("select id from brokers where slug='san-khong-giay-phep'")[0][0]
    p_ = h2.get(f"/admin/brokers/{kk}/edit")
    c("U15", "Mở form sửa sàn thiếu giấy phép: 200", p_.status_code == 200)
    h2.post(f"/admin/brokers/{kid}/delete")
    c("U16", "FK cascade còn sau migration: xóa sàn xóa bonus, banner SET NULL", s.sql("select count(*) from bonuses")[0][0] == 0 and s.sql("select count(*), max(broker_id) from banners") == [(1, None)], s.sql("select count(*), max(broker_id) from banners"))
finally:
    s.stop()
r = subprocess.run([PY, "-m", "alembic", "downgrade", "0001"], cwd=ROOT, env=s.env, capture_output=True, text=True, encoding="utf-8")
c("U17", "downgrade 0001 có dữ liệu", r.returncode == 0, r.stderr[-200:])
c("U18", "Dữ liệu còn sau downgrade", sqlite3.connect(s.db).execute("select count(*) from subscribers").fetchone()[0] == 3)
r = subprocess.run([PY, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=s.env, capture_output=True, text=True, encoding="utf-8")
c("U19", "upgrade lại", r.returncode == 0, r.stderr[-200:])

# ===================== B. Quy trình production theo README =====================
D = WORK / "prod"
extract("HEAD", D)
readme = (D / "README.md").read_text(encoding="utf-8")
c("P0.1", "README có khối Production", "Production:" in readme)
subprocess.run(["py", "-3.12", "-m", "venv", ".venv"], cwd=D, check=True, capture_output=True)
r = subprocess.run([".venv\\Scripts\\pip", "install", "-q", "-r", "requirements.txt"], cwd=D, capture_output=True, text=True, shell=True)
c("P0.2", "pip install", r.returncode == 0, r.stderr[-200:])
vpy = str(D / ".venv/Scripts/python.exe")
drop = ("APP_ENV", "SECRET_KEY", "DATABASE_URL", "UPLOAD_DIR", "BASE_URL", "PORT", "SMTP_BACKEND", "ADMIN_PASSWORD", "SMTP_HOST", "FROM_EMAIL")
clean = {k: v for k, v in os.environ.items() if k not in drop} | {"PYTHONUTF8": "1"}
PBASE = "https://localhost:8016"
r = subprocess.run([vpy, "run.py"], cwd=D, env=clean | {"PORT": str(PORT)}, capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=30)
c("P1", "Thiếu hết: thoát 2, liệt kê đủ 3 thứ một lần, không traceback", r.returncode == 2 and all(x in r.stderr for x in ("SECRET_KEY", "BASE_URL", "SMTP_BACKEND")) and "Traceback" not in r.stderr, (r.returncode, r.stderr[-300:]))
c("P1b", "Chưa tạo DB khi cấu hình sai", not (D / "data" / "app.db").exists())
env = clean | {"PORT": str(PORT), "SECRET_KEY": PROD_KEY, "BASE_URL": PBASE, "SMTP_BACKEND": "console"}
r = subprocess.run([vpy, "run.py"], cwd=D, env=env | {"SMTP_BACKEND": "smtp"}, capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=30)
c("P1c", "SMTP_BACKEND=smtp thiếu host/from: thoát 2 trước khi mở kết nối", r.returncode == 2 and "SMTP_HOST" in r.stderr, r.stderr[-200:])
LOG = D / "run.log"


def start():
    f = open(LOG, "ab")
    p = subprocess.Popen([vpy, "run.py"], cwd=D, env=env, stdout=f, stderr=subprocess.STDOUT)
    for _ in range(100):
        try:
            if httpx.get(f"{BASE}/health", timeout=2).status_code == 200:
                return p, f
        except httpx.HTTPError:
            time.sleep(0.2)
    raise RuntimeError("không lên")


def stop(p, f):
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
    f.close()
    time.sleep(0.5)


p, f = start()
kp, cp = WORK / "qa.key", WORK / "qa.crt"
ossl = shutil.which("openssl") or r"C:\Program Files\Git\mingw64\bin\openssl.exe"
subprocess.run([ossl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(kp), "-out", str(cp), "-days", "30", "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost"], check=True, capture_output=True)
px = subprocess.Popen([PY, str(ROOT / "qa" / "https_proxy.py"), str(cp), str(kp), "8016", str(PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
atexit.register(lambda: subprocess.run(["taskkill", "/T", "/F", "/PID", str(px.pid)], capture_output=True))
atexit.register(lambda: subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True))
try:
    for _ in range(50):
        try:
            if httpx.get(PBASE + "/health", verify=False, timeout=2).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.2)
    log = LOG.read_text(encoding="utf-8", errors="replace")
    c("P2", "Khởi động có cảnh báo console, không phải lỗi", "email KHÔNG được gửi" in log, log[-200:])
    r = subprocess.run([vpy, "-m", "app.cli", "create-admin", "--email", ADMIN_EMAIL], cwd=D, env=env | {"ADMIN_PASSWORD": ADMIN_PASS}, capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
    c("P3", "create-admin ở production", r.returncode == 0, r.stderr[-200:])
    hx = httpx.Client(verify=False, base_url=PBASE, timeout=20)
    errs = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(ignore_https_errors=True)
        ctx.route("**/*", lambda r_: r_.fulfill(status=200, body="", content_type="text/css") if "fonts.g" in r_.request.url else r_.continue_())
        pg = ctx.new_page()
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.goto(PBASE + "/admin/login")
        pg.fill("input[name=email]", ADMIN_EMAIL)
        pg.fill("input[name=password]", ADMIN_PASS)
        with pg.expect_navigation():
            pg.click("button[type=submit]")
        c("P4", "Đăng nhập qua https", pg.url.rstrip("/").endswith("/admin"), pg.url)
        ck = {x["name"]: x for x in ctx.cookies()}
        c("P5", "Cookie Secure/HttpOnly/Lax", ck["tbh_session"]["secure"] and ck["tbh_session"]["httpOnly"] and ck["tbh_session"]["sameSite"] == "Lax")
        pg.goto(PBASE + "/admin/media")
        pg.set_input_files("input[name=files]", str((lambda q: (q.write_bytes(png_bytes()), q)[1])(WORK / "prod_logo.png")))
        with pg.expect_navigation():
            pg.locator("form[action='/admin/media/upload'] button[type=submit]").click()
        mp = sqlite3.connect(D / "data" / "app.db").execute("select path from media_files").fetchone()[0]
        pg.goto(PBASE + "/admin/brokers/new")
        pg.fill(".drawer input[name=name]", "Sàn Thật")
        pg.fill("input[name=license]", "FCA")
        pg.fill("input[name=affiliate_url]", "https://aff.example.test/a")
        with pg.expect_navigation():
            pg.click(".drawer-foot .btn-save")
        c("P6", "Thêm sàn cần license qua UI", "Đã thêm" in pg.locator("[data-flash]").first.inner_text())
        pg.goto(PBASE + "/admin/posts/new")
        pg.fill("input[name=title]", "Bài trước sao lưu")
        pg.fill("textarea[name=body_md]", "x")
        with pg.expect_navigation():
            pg.click(".drawer-foot .btn-save")
        # khách đăng ký qua https, bấm nút xác nhận
        k = b.new_context(ignore_https_errors=True).new_page()
        k.route("**/*", lambda r_: r_.fulfill(status=200, body="", content_type="text/css") if "fonts.g" in r_.request.url else r_.continue_())
        k.goto(PBASE + "/#lien-he")
        k.fill("#lien-he input[name=email]", "khach@qa.test")
        with k.expect_navigation():
            k.locator("#lien-he button[type=submit]").click()
        c("P7", "Production + console: khách thấy lỗi, không thấy 'Kiểm tra hộp thư'", "Chưa gửi được email" in k.inner_text("#lien-he"), k.inner_text("#lien-he")[:160])
        cn = sqlite3.connect(D / "data" / "app.db")
        cn.execute("insert into subscribers(name,email,interests,status,token,confirm_count,created_at,updated_at) values('','da-co@qa.test','[]','pending','tokenqa',0,'2026-01-01 00:00:00','2026-01-01 00:00:00')")
        cn.commit()
        cn.close()
        k.goto(PBASE + "/xac-nhan/tokenqa")
        with k.expect_navigation():
            k.locator(".status-box form button").click()
        c("P8", "Bấm nút xác nhận trên https: CSP form-action không chặn", "Đã xác nhận" in k.inner_text("body"), k.inner_text("body")[:120])
        b.close()
    c("P9", "Không lỗi console/CSP", not errs, errs[:3])
    t = hx.get("/").text
    c("P10", "canonical, sitemap https", f'href="{PBASE}/"' in t and all(u.startswith(PBASE) for u in re.findall(r"<loc>([^<]+)", hx.get("/sitemap.xml").text)))
    c("P11", "HSTS có, /docs 404, /openapi.json 404", "strict-transport-security" in hx.get("/").headers and hx.get("/docs").status_code == 404 and hx.get("/openapi.json").status_code == 404)
    code = "from app.mailer import build; m = build('a@b.co','s','t','https://x/huy-dang-ky/t'); print(m['List-Unsubscribe-Post'], m['List-Unsubscribe'])"
    r = subprocess.run([vpy, "-c", code], cwd=D, env=env, capture_output=True, text=True, encoding="utf-8")
    c("P12", "Email có List-Unsubscribe-Post", "One-Click" in r.stdout, r.stdout + r.stderr[-120:])

    # Sao lưu: lấy nguyên văn khối lệnh trong README
    block = re.search(r"Sao lưu khi server đang chạy.*?```powershell\n(.*?)```", readme, re.S).group(1)
    ps = ["powershell", "-NoProfile", "-Command", block.replace("\n", "; ")]
    r = subprocess.run(ps, cwd=D, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    c("P13", "Lệnh sao lưu README chạy được khi server đang chạy", r.returncode == 0 and (D / "backup.db").exists() and (D / "backup-uploads").exists(), (r.stderr or r.stdout)[-300:])
    c("P14", "backup.db toàn vẹn, có dữ liệu", sqlite3.connect(D / "backup.db").execute("select count(*) from posts").fetchone()[0] == 1)
    # sự cố: mất dữ liệu sau khi sao lưu
    cn = sqlite3.connect(D / "data" / "app.db")
    cn.execute("delete from posts")
    cn.commit()
    cn.close()
    name = mp.rsplit("/", 1)[1]
finally:
    stop(p, f)
# Phục hồi theo 4 bước README
(D / "data" / "uploads" / name).unlink()  # ảnh cũng mất nhưng thư mục còn
block = re.search(r"Phục hồi \(chạy tại.*?```powershell\n(.*?)```", readme, re.S).group(1)
cmds = [ln for ln in block.splitlines() if ln.strip() and "run.py" not in ln]  # đúng lệnh README, run.py chạy bên dưới
r = subprocess.run(["powershell", "-NoProfile", "-Command", "; ".join(cmds)], cwd=D, capture_output=True, text=True, encoding="utf-8", errors="replace")
c("P14b", "Lệnh phục hồi README chạy được", r.returncode == 0, r.stderr[-300:])
p, f = start()
try:
    c("P15", "Sau phục hồi: dữ liệu về", sqlite3.connect(D / "data" / "app.db").execute("select count(*) from posts").fetchone()[0] == 1 and httpx.get(BASE + "/health").status_code == 200)
    st = httpx.get(BASE + mp).status_code
    c("P16", "Sau lệnh phục hồi README: ảnh trở lại", st == 200, f"ảnh {st}; Copy-Item lồng vào data\\uploads\\backup-uploads={(D / 'data' / 'uploads' / 'backup-uploads').exists()}")
finally:
    stop(p, f)
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(px.pid)], capture_output=True)

block = re.search(r"Production:.*?```powershell\n(.*?)```", readme, re.S).group(1)
c("P17", "Khối Production trong README đặt rõ APP_ENV=production", 'APP_ENV = "production"' in block, block[:200])
R.save()
