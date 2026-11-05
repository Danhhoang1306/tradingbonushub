"""Audit mock TradingBonusHub v2. Chạy lại: .venv\\Scripts\\python.exe qa\\mock\\run_audit.py

Tự khởi động server ở cổng QA (8013, QA_PORT đổi được), mỗi pha một DB mới trong thư mục tạm, không đụng
data/app.db, tự tắt server khi xong. Kết quả ở qa/mock/out/ (gitignore vì chứa chuỗi mock trích từ design/).

Pha:
  A  DB rỗng: kiểm không có seed, crawl public+admin ở 1440/390, trạng thái form, 404/500, quét.
  B  Dữ liệu hư cấu ("Sàn A") nhập qua form admin: phải hiện đúng chỗ; xóa hết qua admin: phải về như pha A.
  C  Đổi MỌI chuỗi trong Setting thành sentinel: chữ còn lại trên public là chữ viết cứng;
     sentinel không có ở admin nghĩa là khóa đó không sửa được từ admin.
"""
import json
import os
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

import crawl as C
import extract_mock
import scan as S
from common import ADMIN_EMAIL, BASE, OUT, PORT, ROOT, TMP, dump, fold, norm

PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
TABLES = ["admin_users", "admin_sessions", "brokers", "bonuses", "posts", "banners", "subscribers", "contact_messages",
          "campaigns", "settings", "media_files", "click_logs"]
QA_IGNORE = [r"qa-mock@example\.test", r"qa-editor@example\.test", r"qa-(?:sub|contact)-\d+@example\.test"]
MARKERS = ["Sàn A", "Sàn B", "san-a", "san-b", "QAFIC", "fic.example", "fic-telegram", "fic-mail@example.test"]


class Server:
    def __init__(self, name):
        self.dir = TMP / name
        shutil.rmtree(self.dir, ignore_errors=True)
        (self.dir / "up").mkdir(parents=True)
        self.db = self.dir / "qa.db"
        self.password = secrets.token_urlsafe(18)
        self.log = (OUT / f"server_{name}.log")
        env = {k: v for k, v in os.environ.items() if not k.startswith("SMTP_")}
        env.update(APP_ENV="development", SECRET_KEY=secrets.token_hex(16), DATABASE_URL=f"sqlite:///{self.db.as_posix()}",
                   UPLOAD_DIR=str(self.dir / "up"), PORT=str(PORT), BASE_URL=BASE, SMTP_BACKEND="console",
                   PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        self.env = env

    def __enter__(self):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", PORT)) == 0:
                raise SystemExit(f"Cổng {PORT} đang bận.")
        OUT.mkdir(parents=True, exist_ok=True)
        self.logf = self.log.open("w", encoding="utf-8")
        self.proc = subprocess.Popen([PY, "run.py"], cwd=ROOT, env=self.env, stdout=self.logf, stderr=subprocess.STDOUT)
        for _ in range(100):
            try:
                urllib.request.urlopen(BASE + "/health", timeout=1)
                return self
            except Exception:
                time.sleep(0.2)
        raise SystemExit("Server không lên, xem " + str(self.log))

    def __exit__(self, *exc):
        self.proc.terminate()
        self.proc.wait(10)
        self.logf.close()

    def create_admin(self, email=ADMIN_EMAIL, role="admin", password=None):
        env = dict(self.env, ADMIN_PASSWORD=password or self.password)
        subprocess.run([PY, "-m", "app.cli", "create-admin", "--email", email, "--role", role], cwd=ROOT, env=env,
                       check=True, capture_output=True)

    def counts(self):
        con = sqlite3.connect(self.db)
        out = {t: con.execute(f"select count(*) from {t}").fetchone()[0] for t in TABLES}
        con.close()
        return out


class AdminClient:
    """Thao tác admin bằng HTTP form thật (có CSRF), qua cookie của trình duyệt đã đăng nhập."""

    def __init__(self, browser, password):
        self.ctx = C.new_context(browser, "1440")
        self.page = self.ctx.new_page()
        C.login(self.page, password)

    def csrf(self, path="/admin/bonus/new"):
        self.page.goto(BASE + path)
        return self.page.get_attribute('input[name="csrf_token"]', "value")

    def post(self, path, fields=()):
        items = list(fields.items()) if isinstance(fields, dict) else list(fields)
        items.append(("csrf_token", self.csrf()))
        r = self.ctx.request.post(BASE + path, data=urlencode(items, doseq=True), max_redirects=0,
                                  headers={"Content-Type": "application/x-www-form-urlencoded"})
        if r.status not in (200, 204, 303):
            raise RuntimeError(f"POST {path} -> {r.status}: {r.text()[:300]}")
        return r

    def upload(self, name):
        from PIL import Image
        import io
        buf = io.BytesIO()
        Image.new("RGB", (64, 64), (25, 68, 223)).save(buf, "PNG")
        r = self.ctx.request.post(BASE + "/admin/media/upload", max_redirects=0, multipart={
            "csrf_token": self.csrf(), "alt": "QAFIC ảnh " + name,
            "files": {"name": name + ".png", "mimeType": "image/png", "buffer": buf.getvalue()}})
        if r.status not in (200, 303):
            raise RuntimeError(f"upload -> {r.status}")

    def delete_all(self, list_path):
        n = 0
        for _ in range(50):
            self.page.goto(BASE + list_path)
            actions = self.page.eval_on_selector_all('form[action$="/delete"]', "fs => fs.map(f => f.getAttribute('action'))")
            actions = [a for a in actions if "/settings/users/" not in a]
            if not actions:
                return n
            self.post(actions[0])
            n += 1
        raise RuntimeError("không xóa hết " + list_path)


def seed_fiction(a: AdminClient, srv: Server):
    """Dữ liệu hư cấu, nhập qua form admin + form public. Không dùng tên sàn thật."""
    a.upload("qafic-logo")
    a.upload("qafic-cover")
    con = sqlite3.connect(srv.db)
    paths = [r[0] for r in con.execute("select path from media_files order by id")]
    con.close()
    logo, cover = paths[0], paths[1]
    for i, name in enumerate(("Sàn A", "Sàn B")):
        a.post("/admin/brokers/new", [
            ("name", name), ("kind", "forex" if i == 0 else "crypto"), ("tagline", f"QAFIC tagline {name}"),
            ("summary", f"QAFIC tóm tắt {name}"), ("license", "QAFIC-LIC"), ("min_deposit", "QAFIC-MIN"),
            ("leverage", "QAFIC-LEV"), ("platforms", "QAFIC-PLAT"), ("spread", "QAFIC-SPREAD"),
            ("withdrawal", "QAFIC-WD"), ("founded", "QAFIC-Y"), ("affiliate_url", f"https://fic.example/{i}"),
            ("logo_path", logo if i == 0 else ""), ("pros", "QAFIC ưu điểm"), ("cons", "QAFIC lưu ý"),
            ("account_name", "QAFIC acc"), ("account_min_deposit", "QAFIC-AM"), ("account_spread", "QAFIC-AS"),
            ("account_commission", "QAFIC-AC"), ("payment_method", "QAFIC pay"), ("payment_deposit", "QAFIC-PD"),
            ("payment_withdraw", "QAFIC-PW"), ("payment_time", "QAFIC-PT"), ("in_compare", "1"),
            ("is_active", "1"), *([("featured", "1")] if i == 0 else [])])
    types = ["nodep", "deposit", "cashback", "contest", "crypto"]
    for i, t in enumerate(types):
        a.post("/admin/bonus/new", {"broker_id": 1 if i != 4 else 2, "type": t, "title": f"QAFIC bonus {t}", "amount": f"QAFIC-{i}",
                                    "value_num": str(i + 1), "min_deposit": "QAFIC-BM", "withdrawable": "QAFIC-BW", "is_active": "1"})
    for i, st in enumerate(("published", "published", "draft")):
        a.post("/admin/posts/new", {"title": f"QAFIC bài {i}", "category": "Hướng dẫn", "excerpt": "QAFIC tóm tắt bài",
                                    "body_md": "QAFIC nội dung **đậm**", "cover_path": cover if i == 0 else "", "status": st, "show_home": "1"})
    for i, pl in enumerate(("after-bonus", "before-blog", "rail-left", "rail-right")):
        a.post("/admin/ads/new", {"name": f"QAFIC banner {pl}", "broker_id": 1, "placement": pl,
                                  "image_path": cover if i in (1, 3) else "", "is_active": "1"})
    a.post("/admin/settings/general", {"site_name": "TradingBonusHub", "contact_email": "fic-mail@example.test",
                                       "partner_email": "fic-mail@example.test", "telegram": "fic-telegram",
                                       "logo_path": "/static/img/logo.png", "favicon_path": "/static/img/logo.png"})
    a.post("/admin/settings/social", [("social_label", "QAFIC social"), ("social_url", "https://fic.example/social")])
    a.post("/admin/subscribers/mail", {"subject": "QAFIC nháp", "body": "QAFIC thân thư", "action": "draft"})
    # Người đăng ký + tin nhắn qua form public; click + view để bộ đếm khác 0
    p = a.ctx.new_page()
    p.goto(BASE + "/")
    p.fill('form[action="/api/subscribe"] input[name="name"]', "QAFIC người đăng ký")
    p.fill('form[action="/api/subscribe"] input[name="email"]', "qafic-sub@example.test")
    p.click('form[action="/api/subscribe"] button[type="submit"]')
    p.goto(BASE + "/lien-he")
    p.fill('form[action="/api/contact"] input[name="name"]', "QAFIC khách")
    p.fill('form[action="/api/contact"] input[name="email"]', "qafic-msg@example.test")
    p.fill('form[action="/api/contact"] textarea[name="body"]', "QAFIC tin nhắn")
    p.click('form[action="/api/contact"] button[type="submit"]')
    p.close()
    for u in ("/go/broker/1", "/go/ad/1"):
        a.ctx.request.get(BASE + u, max_redirects=0)


def wipe_fiction(a: AdminClient, srv: Server):
    out = {}
    con = sqlite3.connect(srv.db)  # nút xóa của 4 nhóm này nằm trong drawer: lấy id rồi POST đúng route của nút đó
    ids = {t: [r[0] for r in con.execute(f"select id from {t}")] for t in ("bonuses", "banners", "posts", "brokers")}
    con.close()
    for table, group in (("bonuses", "bonus"), ("banners", "ads"), ("posts", "posts"), ("brokers", "brokers")):
        for i in ids[table]:
            a.post(f"/admin/{group}/{i}/delete")
        out[table] = len(ids[table])
    for name, path in (("subscriber", "/admin/subscribers?tab=list"), ("message", "/admin/messages")):
        out[name] = a.delete_all(path)
    a.post("/admin/settings/general", {"site_name": "TradingBonusHub", "contact_email": "", "partner_email": "", "telegram": "",
                                       "logo_path": "/static/img/logo.png", "favicon_path": "/static/img/logo.png"})
    a.post("/admin/settings/social", [("social_label", ""), ("social_url", "")])
    out["media"] = a.delete_all("/admin/media")
    return out


def text_map(label):
    """(url, viewport, state) -> tập dòng text hiển thị + thuộc tính nhìn thấy."""
    out = {}
    for r in C.read_crawl(label):
        if "error" in r:
            continue
        lines = {norm(x) for x in r.get("text", "").splitlines() if norm(x)}
        lines |= {f"@{a['attr']}={norm(a['value'])}" for a in r.get("attrs", []) if a["attr"] in S.VISIBLE_ATTRS}
        out[(r["url"].replace(BASE, ""), r["viewport"], r.get("state", ""))] = lines
    return out


def marker_hits(label):
    found = {}
    for r in C.read_crawl(label):
        if "error" in r:
            continue
        blob = fold(r.get("raw", "") + " " + r.get("html", "") + " " + r.get("alltext", ""))
        for m in MARKERS:  # nguyên từ: tránh "Sàn" + "Bài viết" liền nhau ở sidebar khớp nhầm "Sàn B"
            if re.search(r"(?<!\w)" + re.escape(fold(m)) + r"(?!\w)", blob):
                found.setdefault(m, set()).add(r["url"].replace(BASE, ""))
    return {k: sorted(v) for k, v in found.items()}


def walk_sentinel(node, counter, table, path=""):
    """Thay mọi chuỗi nội dung bằng ZQ<n>Z. Giữ id, url, đường dẫn ảnh, cờ."""
    if isinstance(node, dict):
        return {k: (v if k in ("id", "url", "on") else walk_sentinel(v, counter, table, f"{path}.{k}")) for k, v in node.items()}
    if isinstance(node, list):
        return [walk_sentinel(v, counter, table, f"{path}[{i}]") for i, v in enumerate(node)]
    if isinstance(node, str):
        if not node or node.startswith("/") or path.endswith(("_path", "image", "og_image", "site_name")):
            return node
        counter[0] += 1
        tok = f"ZQ{counter[0]}Z"
        table[tok] = {"path": path, "default": node}
        return tok
    return node


def apply_sentinels(srv: Server):
    env = dict(srv.env)
    code = "import json;from app.content import DEFAULTS;print(json.dumps(DEFAULTS,ensure_ascii=False))"
    defaults = json.loads(subprocess.run([PY, "-c", code], cwd=ROOT, env=env, check=True, capture_output=True, encoding="utf-8").stdout)
    counter, table = [0], {}
    con = sqlite3.connect(srv.db, timeout=20)
    stored = {k: json.loads(v) for k, v in con.execute("select key, value from settings")}
    now = "2026-11-05 00:00:00"
    for key, value in defaults.items():
        if key in ("legal",):  # legal là Markdown rỗng theo mặc định
            value = {"terms_md": "ZQTERMZ", "privacy_md": "ZQPRIVZ"}
            table["ZQTERMZ"] = {"path": "legal.terms_md", "default": ""}
            table["ZQPRIVZ"] = {"path": "legal.privacy_md", "default": ""}
            new = value
        elif key == "contact_page":
            value = dict(value, intro="ZQINTROZ")
            table["ZQINTROZ"] = {"path": "contact_page.intro", "default": ""}
            new = walk_sentinel({k: v for k, v in value.items() if k != "intro"}, counter, table, key)
            new["intro"] = "ZQINTROZ"
        elif key in ("social", "analytics_head", "contact_email", "partner_email", "telegram", "branding"):
            new = stored.get(key, value)
        elif key == "pages":
            for pv in value.values():
                pv["meta_title"] = pv["meta_title"] or "x"
                pv["meta_desc"] = pv["meta_desc"] or "x"
                pv["desc"] = pv["desc"] or "x"
            new = walk_sentinel(value, counter, table, key)
        else:
            new = walk_sentinel(value, counter, table, key)
        blob = json.dumps(new, ensure_ascii=False)
        cur = con.execute("update settings set value=? where key=?", (blob, key))
        if cur.rowcount == 0:
            con.execute("insert into settings(key, value, created_at, updated_at) values (?,?,?,?)", (key, blob, now, now))
    con.commit()
    con.close()
    dump("sentinels.json", table)
    return table


def phase_a():
    with Server("A") as srv:
        before_admin = srv.counts()
        srv.create_admin()
        editor_pw = secrets.token_urlsafe(18)
        srv.create_admin("qa-editor@example.test", "editor", editor_pw)
        counts = C.crawl("empty", srv.password, db_path=srv.db, states=True, editor_password=editor_pw)
        after = srv.counts()
    log = srv.log.read_text(encoding="utf-8", errors="replace")
    rep = S.scan_crawl("empty", ignore=QA_IGNORE)
    return {"rows_on_boot": before_admin, "rows_after_crawl": after, "crawl_counts": counts, "pages": rep["pages"],
            "server_tracebacks": log.count("Traceback")}


def phase_b():
    with Server("B") as srv:
        srv.create_admin()
        with sync_playwright() as p:
            b = p.chromium.launch()
            a = AdminClient(b, srv.password)
            seed_fiction(a, srv)
            seeded = srv.counts()
            b.close()
        c_seed = C.crawl("fiction", srv.password)
        shown = marker_hits("fiction")
        with sync_playwright() as p:
            b = p.chromium.launch()
            a = AdminClient(b, srv.password)
            deleted = wipe_fiction(a, srv)
            b.close()
        c_wipe = C.crawl("wiped", srv.password)
        left = srv.counts()
        con = sqlite3.connect(srv.db)
        files = [f.name for f in (srv.dir / "up").rglob("*") if f.is_file()]
        leftovers = {t: [str(r) for r in con.execute(f"select * from {t}").fetchall()][:6] for t in ("campaigns", "click_logs")}
        con.close()
    rep_f = S.scan_crawl("fiction", extra_strong=["Sàn A", "QAFIC"], ignore=QA_IGNORE)
    rep_w = S.scan_crawl("wiped", ignore=QA_IGNORE)
    remaining = marker_hits("wiped")
    # So với pha A theo từng URL
    base, wiped = text_map("empty"), text_map("wiped")
    diffs = {}
    for key, lines in wiped.items():
        if key in base:
            extra, missing = lines - base[key], base[key] - lines
            if extra or missing:
                diffs[f"{key[0]} @{key[1]}"] = {"chi_o_sau_xoa": sorted(extra)[:12], "chi_o_ban_dau": sorted(missing)[:12]}
    return {"rows_seeded": seeded, "crawl_fiction": c_seed, "marker_shown": {k: len(v) for k, v in shown.items()},
            "marker_pages": shown, "control_scan_detected": {k: len(rep_f["mock_strong"].get(k, [])) for k in ("Sàn A", "QAFIC")},
            "deleted": deleted, "rows_after_wipe": left, "crawl_wiped": c_wipe, "marker_after_wipe": remaining,
            "upload_files_left": files, "leftover_rows": leftovers, "diff_vs_empty": diffs}, rep_w


def phase_c():
    with Server("C") as srv:
        srv.create_admin()
        with sync_playwright() as p:
            b = p.chromium.launch()
            a = AdminClient(b, srv.password)
            seed_fiction(a, srv)
            b.close()
        table = apply_sentinels(srv)
        C.crawl("sentinel", srv.password, db_path=srv.db, states=True, viewports={"1440": (1440, 900)})
    rows = C.read_crawl("sentinel")
    pub_blob = " ".join(r.get("html", "") + r.get("alltext", "") for r in rows if r.get("scope") == "public")
    admin_blob = " ".join(r.get("html", "") for r in rows if r.get("scope") == "admin")
    tok_re = re.compile(r"ZQ\w+?Z")
    public_seen, admin_seen = set(tok_re.findall(pub_blob)), set(tok_re.findall(admin_blob))
    remain = {}
    for r in rows:
        if r.get("scope") != "public" or "error" in r:
            continue
        page = r["url"].replace(BASE, "")
        for line in r.get("text", "").splitlines():
            t = norm(tok_re.sub(" ", line))
            if t and not re.search(r"QAFIC|Sàn [AB]|fic[-.]", t):
                remain.setdefault(t, set()).add(page)
        for at in r.get("attrs", []):
            if at["attr"] in ("alt", "placeholder", "title", "aria-label") or (at["attr"] == "content" and at["name"] not in ("viewport",)):
                t = norm(tok_re.sub(" ", at["value"]))
                if t and not re.search(r"QAFIC|Sàn [AB]|fic[-.]|^http", t):
                    remain.setdefault(f"@{at['attr']}: {t}", set()).add(page)
    rep = {"sentinels": len(table),
           "not_on_public": {k: table[k] for k in table if k not in public_seen},
           "not_in_admin": {k: table[k] for k in table if k not in admin_seen},
           "hardcoded_visible": {k: {"pages": len(v), "sample": sorted(v)[:3]} for k, v in sorted(remain.items())}}
    dump("sentinel_report.json", rep)
    return {k: (len(v) if isinstance(v, dict) else v) for k, v in rep.items()}


def main():
    wanted = sys.argv[1:] or ["A", "B", "C"]
    t0 = time.time()
    extract_mock.main()
    summary = {}
    if "A" in wanted:
        summary["A"] = phase_a()
        print("Pha A xong", summary["A"], flush=True)
        dump("summary_A.json", summary["A"])
    if "B" in wanted:
        summary["B"], _ = phase_b()
        print("Pha B xong", flush=True)
        dump("summary_B.json", summary["B"])
    if "C" in wanted:
        summary["C"] = phase_c()
        print("Pha C xong", summary["C"], flush=True)
        dump("summary_C.json", summary["C"])
    summary["source"] = {k: (len(v) if hasattr(v, "__len__") and k != "files" else v) for k, v in S.scan_source().items()}
    for phase in "ABC":  # chạy riêng từng pha vẫn giữ kết quả pha khác
        if phase not in summary and (OUT / f"summary_{phase}.json").exists():
            summary[phase] = json.loads((OUT / f"summary_{phase}.json").read_text(encoding="utf-8"))
    dump("summary.json", summary)
    print(f"Xong sau {time.time() - t0:.0f}s. Xem qa/mock/out/summary.json")


if __name__ == "__main__":
    main()
