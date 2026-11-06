"""Thư viện chung cho QA chức năng TradingBonusHub v2.

An toàn: chỉ chạy cổng 8014 (không bao giờ 8000), DB + upload nằm ở thư mục tạm QA_WORK,
SMTP_BACKEND=console. Chạy lại: `python qa/run_all.py` (xem đầu file đó).
"""
import atexit
import json
import os
import re
import shutil
import socket
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path
from urllib.parse import urlencode

import httpx

ROOT = Path(__file__).resolve().parent.parent
_venv = ROOT / ".venv" / "Scripts" / "python.exe"
PY = str(_venv) if _venv.exists() else sys.executable
WORK = Path(os.environ.get("QA_WORK") or (Path(tempfile.gettempdir()) / "tbh_qa"))
RESULTS = ROOT / "qa" / "results"
PORT = 8014
BASE = f"http://127.0.0.1:{PORT}"
PROD_KEY = "qa-prod-secret-" + "k" * 40
ADMIN_EMAIL, ADMIN_PASS = "admin@qa.test", "QaAdmin-12345"
EDITOR_EMAIL, EDITOR_PASS = "editor@qa.test", "QaEditor-12345"
assert PORT != 8000


OPEN_DETAILS = "addEventListener('DOMContentLoaded', () => document.querySelectorAll('details.drawer-more').forEach(d => { d.open = true; }));"  # ô phụ của drawer nằm trong khối đóng sẵn (brief 13.1)


def prod_env(**kw):
    """Cấu hình production tối thiểu hợp lệ (vòng 2: SECRET_KEY >= 32, BASE_URL, SMTP_BACKEND bắt buộc)."""
    return {"APP_ENV": "production", "SECRET_KEY": PROD_KEY, "BASE_URL": BASE, "SMTP_BACKEND": "console", **kw}


def admin_routes(env=None, root=None):
    """Danh sách route admin, đọc từ decorator trong mã nguồn (app.routes rỗng với FastAPI hiện tại do _IncludedRouter).
    Có kiểm số lượng: danh sách rỗng từng làm kiểm tra phân quyền đạt mà không thử route nào."""
    out = {}
    for name in ("admin.py", "admin_data.py", "admin_content.py", "admin_people.py"):
        src = Path(root or ROOT, "app", "routes", name).read_text(encoding="utf-8")
        for method, path in re.findall(r'@router\.(get|post)\("([^"]*)"', src):
            out.setdefault("/admin" + path, []).append(method)
    assert len(out) >= 50, f"chỉ tìm thấy {len(out)} route admin"
    return list(out.items())


def port_free(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) != 0


class Server:
    """Một tiến trình `python run.py` với DB/upload riêng ở WORK/<name>."""

    def __init__(self, name, env=None, fresh=True, entry="run.py", port=PORT):
        self.name, self.port, self.entry = name, port, entry
        self.dir = WORK / name
        if fresh and self.dir.exists():
            shutil.rmtree(self.dir, ignore_errors=True)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.db = self.dir / "app.db"
        self.uploads = self.dir / "up"
        self.log_path = self.dir / "server.log"
        self.env = {**os.environ, "APP_ENV": "development", "SMTP_BACKEND": "console", "PORT": str(port),
                    "DATABASE_URL": f"sqlite:///{self.db.as_posix()}", "UPLOAD_DIR": str(self.uploads),
                    "BASE_URL": f"http://127.0.0.1:{port}", "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1",
                    "SECRET_KEY": "qa-secret-key-" + "x" * 40}
        self.env.update(env or {})
        self.proc = None

    def start(self, wait=40):
        assert self.port != 8000, "Cấm cổng 8000"
        assert port_free(self.port), f"Cổng {self.port} đang bận"
        atexit.register(self.stop)  # script chết giữa chừng cũng không bỏ lại server
        self.log = open(self.log_path, "ab")
        self.proc = subprocess.Popen([PY, self.entry], cwd=getattr(self, "cwd", ROOT), env=self.env, stdout=self.log, stderr=subprocess.STDOUT)
        end = time.time() + wait
        while time.time() < end:
            if self.proc.poll() is not None:
                raise RuntimeError(f"Server thoát sớm, xem {self.log_path}")
            try:
                if httpx.get(f"http://127.0.0.1:{self.port}/health", timeout=2).status_code == 200:
                    return self
            except httpx.HTTPError:
                time.sleep(0.2)
        raise RuntimeError("Server không lên")

    def stop(self):
        if self.proc:  # python.exe của venv trên Windows là launcher: phải giết cả cây tiến trình
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.proc.pid)], capture_output=True)
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
        for _ in range(50):
            if port_free(self.port):
                break
            time.sleep(0.1)
        if hasattr(self, "log") and not self.log.closed:
            self.log.close()

    def cli_admin(self, email=ADMIN_EMAIL, password=ADMIN_PASS, role="admin"):
        env = {**self.env, "ADMIN_PASSWORD": password}
        r = subprocess.run([PY, "-m", "app.cli", "create-admin", "--email", email, "--role", role], cwd=getattr(self, "cwd", ROOT), env=env,
                           capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=60)
        assert r.returncode == 0, r.stderr
        return r

    def log_text(self):
        return self.log_path.read_text(encoding="utf-8", errors="replace")

    def tokens(self, email=None):
        """Token xác nhận trong email console (mới nhất ở cuối)."""
        out = []
        for block in self.log_text().split("[console email] ")[1:]:
            m = re.match(r"to=(\S+) subject=", block)
            tok = re.search(r"/xac-nhan/([\w-]+)", block.split("Hủy nhận email:")[0])
            if m and tok and (email is None or m.group(1) == email):
                out.append(tok.group(1))
        return out

    def sql(self, q, args=()):
        con = sqlite3.connect(self.db, timeout=15)
        try:
            cur = con.execute(q, args)
            rows = cur.fetchall()
            con.commit()
            return rows
        finally:
            con.close()

    def __enter__(self):
        return self.start()

    def __exit__(self, *a):
        self.stop()


def _todict(pairs):
    d = {}
    for k, v in pairs:
        d.setdefault(k, []).append(v)
    return d


class Http:
    """Client tự giữ cookie (kể cả Secure trên http) và tự chèn CSRF. Không theo redirect."""

    def __init__(self, base=BASE, **kw):
        self.base = base
        self.c = httpx.Client(timeout=30, follow_redirects=False, **kw)
        self.cookies = {}
        self.csrf = ""

    def _hdr(self, headers):
        h = dict(headers or {})
        if self.cookies:
            h["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        return h

    def _absorb(self, r):
        for sc in r.headers.get_list("set-cookie"):
            k, _, v = sc.split(";", 1)[0].partition("=")
            if "max-age=0" in sc.lower() or v in ('""', ""):
                self.cookies.pop(k.strip(), None)
            else:
                self.cookies[k.strip()] = v.strip()
        return r

    def url(self, path):
        return path if path.startswith("http") else self.base + path

    def get(self, path, headers=None, **kw):
        return self._absorb(self.c.get(self.url(path), headers=self._hdr(headers), **kw))

    def post(self, path, data=None, files=None, headers=None, raw=False, **kw):
        data = data if isinstance(data, list) else dict(data or {})
        if self.csrf and not raw:
            if isinstance(data, dict):
                data.setdefault("csrf_token", self.csrf)
            else:
                data = data + [("csrf_token", self.csrf)]
        hdr = self._hdr(headers)
        if isinstance(data, list):
            if files:
                return self._absorb(self.c.post(self.url(path), data=_todict(data), files=files, headers=hdr, **kw))
            hdr["Content-Type"] = "application/x-www-form-urlencoded"
            return self._absorb(self.c.post(self.url(path), content=urlencode(data), headers=hdr, **kw))
        return self._absorb(self.c.post(self.url(path), data=data, files=files, headers=hdr, **kw))

    def login(self, email=ADMIN_EMAIL, password=ADMIN_PASS, next_="/admin"):
        tok = re.search(r'name="csrf_token" value="([^"]+)"', self.get("/admin/login").text).group(1)
        r = self.post("/admin/login", {"email": email, "password": password, "csrf_token": tok, "next": next_}, raw=True)
        assert r.status_code == 303, (r.status_code, r.text[:300])
        self.refresh_csrf()
        return self

    def refresh_csrf(self):
        m = re.search(r'name="csrf_token" value="([^"]+)"', self.get("/admin").text)
        self.csrf = m.group(1) if m else ""


class Report:
    def __init__(self, name):
        self.name = name
        self.rows = []

    def check(self, cid, desc, ok, detail=""):
        self.rows.append({"id": cid, "desc": desc, "ok": bool(ok), "detail": str(detail)[:800]})
        print(f"[{'PASS' if ok else 'FAIL'}] {cid} {desc}" + (f" :: {str(detail)[:400]}" if not ok else ""), flush=True)
        return bool(ok)

    def save(self):
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / f"{self.name}.json").write_text(json.dumps(self.rows, ensure_ascii=False, indent=1), encoding="utf-8")
        bad = [r for r in self.rows if not r["ok"]]
        print(f"== {self.name}: {len(self.rows) - len(bad)}/{len(self.rows)} đạt", flush=True)
        return bad


def png_bytes(w=64, h=64, rgb=(25, 68, 223), extra=b""):
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"") + extra)


# ---------- dữ liệu mẫu qua form admin thật (không chạm DB) ----------

def mk_broker(h, name="Sàn Alpha", **kw):
    d = {"name": name, "slug": "", "mono": "", "kind": "forex", "tagline": "Khẩu hiệu", "summary": "Tóm tắt",
         "license": "FCA", "min_deposit": "$10", "leverage": "1:500", "platforms": "MT5", "spread": "0.1",
         "withdrawal": "1 ngày", "founded": "2010", "affiliate_url": "https://aff.example.test/a", "logo_path": "",
         "pros": "Tốt\nNhanh", "cons": "Phí cao", "is_active": "1"}
    d.update(kw)
    d = {k: v for k, v in d.items() if v is not None}
    r = h.post("/admin/brokers/new", d)
    assert r.status_code == 303, (r.status_code, r.text[:400])
    return r


def mk_bonus(h, broker_id, title="Bonus A", **kw):
    d = {"broker_id": broker_id, "type": "deposit", "title": title, "amount": "$100", "value_num": "100",
         "min_deposit": "$10", "withdrawable": "Có", "expiry_date": "", "is_active": "1"}
    d.update(kw)
    d = {k: v for k, v in d.items() if v is not None}
    r = h.post("/admin/bonus/new", d)
    assert r.status_code == 303, (r.status_code, r.text[:400])
    return r


def mk_post(h, title="Bài A", **kw):
    d = {"title": title, "slug": "", "category": "Hướng dẫn", "excerpt": "Tóm tắt", "body_md": "Nội dung **đậm**",
         "cover_path": "", "status": "published", "published_at": "", "show_home": "1"}
    d.update(kw)
    d = {k: v for k, v in d.items() if v is not None}
    r = h.post("/admin/posts/new", d)
    assert r.status_code == 303, (r.status_code, r.text[:400])
    return r


def mk_banner(h, name="QC A", **kw):
    d = {"name": name, "broker_id": "", "placement": "after-bonus", "target_url": "https://ad.example.test/x",
         "image_path": "", "start_date": "", "end_date": "", "is_active": "1"}
    d.update(kw)
    d = {k: v for k, v in d.items() if v is not None}
    r = h.post("/admin/ads/new", d)
    assert r.status_code == 303, (r.status_code, r.text[:400])
    return r
