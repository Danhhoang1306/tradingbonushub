"""Đường đi sạch của người dùng mới, làm đúng theo README: bản git archive HEAD, venv mới, pip install -r requirements.txt,
python run.py, create-admin, đăng nhập bằng Chromium. Cổng 8014. Không đụng data/ của repo (mọi thứ nằm trong bản sao)."""
import io
import os
import shutil
import subprocess
import tarfile
import time

import httpx
from playwright.sync_api import sync_playwright

from qalib import ROOT, WORK, Report, port_free

R = Report("s0_fresh_install")
D = WORK / "fresh"
PORT = "8014"
if D.exists():
    shutil.rmtree(D, ignore_errors=True)
D.mkdir(parents=True)
tar = subprocess.run(["git", "archive", "HEAD"], cwd=ROOT, capture_output=True, check=True).stdout
tarfile.open(fileobj=io.BytesIO(tar)).extractall(D, filter="data")
t0 = time.time()
r = subprocess.run(["py", "-3.12", "-m", "venv", ".venv"], cwd=D, capture_output=True, text=True)
R.check("F0.1", "py -3.12 -m venv .venv", r.returncode == 0, r.stderr)
vpy, vpip = str(D / ".venv/Scripts/python.exe"), str(D / ".venv/Scripts/pip.exe")
r = subprocess.run([vpip, "install", "-r", "requirements.txt"], cwd=D, capture_output=True, text=True, encoding="utf-8", errors="replace")
R.check("F0.2", "pip install -r requirements.txt", r.returncode == 0, r.stdout[-400:] + r.stderr[-400:])
print("pip mất", round(time.time() - t0), "giây", flush=True)

drop = ("APP_ENV", "SECRET_KEY", "DATABASE_URL", "UPLOAD_DIR", "BASE_URL", "PORT", "SMTP_BACKEND", "ADMIN_PASSWORD")
clean_env = {k: v for k, v in os.environ.items() if k not in drop}
assert port_free(8014)

# 1) README: "APP_ENV mặc định development", "SECRET_KEY ngẫu nhiên mỗi lần chạy (dev)". Không đặt gì thì sao?
env = {**clean_env, "PORT": PORT}
p = subprocess.Popen([vpy, "run.py"], cwd=D, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
try:
    out, _ = p.communicate(timeout=20)
    txt = out.decode("utf-8", "replace")
except subprocess.TimeoutExpired:
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
    txt = "(đang chạy)"
R.check("F0.3", "Không đặt gì: mặc định production, thoát mã 2, liệt kê cấu hình thiếu, không traceback", p.returncode == 2 and "Thiếu SECRET_KEY" in txt and "Traceback" not in txt, (p.returncode, txt[-300:]))

# 2) Theo đúng mục Chạy của README
env = {**clean_env, "APP_ENV": "development", "PORT": PORT}
log = open(D / "run.log", "wb")
p = subprocess.Popen([vpy, "run.py"], cwd=D, env=env, stdout=log, stderr=subprocess.STDOUT)
try:
    up = False
    for _ in range(100):
        try:
            up = httpx.get(f"http://127.0.0.1:{PORT}/health", timeout=2).status_code == 200
            if up:
                break
        except httpx.HTTPError:
            time.sleep(0.3)
    R.check("F0.4", "python run.py (APP_ENV=development + PORT theo README) lên được, /health 200", up)
    R.check("F0.5", "DB rỗng: trang chủ 200", httpx.get(f"http://127.0.0.1:{PORT}/").status_code == 200)
    R.check("F0.6", "Tự tạo data/app.db trong bản sao", (D / "data" / "app.db").exists())
    ae = {**env, "ADMIN_PASSWORD": "MatKhauManh-123"}
    r = subprocess.run([vpy, "-m", "app.cli", "create-admin", "--email", "ban@example.com"], cwd=D, env=ae,
                       capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
    R.check("F0.7", "create-admin bằng ADMIN_PASSWORD", r.returncode == 0, r.stderr + r.stdout)
    r = subprocess.run([vpy, "-m", "app.cli", "create-admin", "--email", "ban2@example.com"], cwd=D, env=env,
                       capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
    R.check("F0.8", "create-admin không console, không biến: báo lỗi sạch, không treo",
            r.returncode == 2 and "Traceback" not in r.stderr, r.stderr)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for host in ("127.0.0.1", "localhost"):
            ctx = b.new_context()
            pg = ctx.new_page()
            pg.goto(f"http://{host}:{PORT}/admin/login")
            pg.fill("input[name=email]", "ban@example.com")
            pg.fill("input[name=password]", "MatKhauManh-123")
            pg.click("button[type=submit]")
            pg.wait_for_load_state()
            ok = pg.url.rstrip("/").endswith("/admin")
            R.check(f"F0.9-{host}", f"Đăng nhập theo đúng các bước README qua http://{host}:{PORT}", ok,
                    f"url={pg.url} text={pg.inner_text('body')[:200]!r}")
            ctx.close()
        b.close()
finally:
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
    log.close()

# 3) Chạy từ thư mục khác (Task Scheduler, service)
pcwd = subprocess.Popen([vpy, str(D / "run.py")], cwd=str(WORK), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
try:
    ok = False
    for _ in range(60):
        try:
            ok = httpx.get(f"http://127.0.0.1:{PORT}/health", timeout=2).status_code == 200
            if ok:
                break
        except httpx.HTTPError:
            if pcwd.poll() is not None:
                break
            time.sleep(0.3)
    R.check("F0.10", "python <đường dẫn tuyệt đối>/run.py từ thư mục khác vẫn chạy", ok,
            pcwd.stdout.read()[-500:] if pcwd.poll() is not None else "")
finally:
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(pcwd.pid)], capture_output=True)

r = subprocess.run([vpip, "install", "-r", "requirements-dev.txt"], cwd=D, capture_output=True, text=True, encoding="utf-8", errors="replace")
R.check("F0.11", "pip install -r requirements-dev.txt", r.returncode == 0, r.stderr[-300:])
r = subprocess.run([vpy, "-m", "pytest", "-q"], cwd=D, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=clean_env, timeout=500)
R.check("F0.12", "README Test: pytest xanh trên bản sao sạch", r.returncode == 0, r.stdout[-500:])
print(r.stdout[-200:])
R.save()
