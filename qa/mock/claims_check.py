"""Đối chiếu tuyên bố trong Điều khoản, Bảo mật và trang chủ với hành vi thật (không chỉ đọc code) -> out/claims_check.json.

Chạy: .venv\\Scripts\\python.exe qa\\mock\\claims_check.py (server cổng QA, DB tạm, SMTP console).
"""
import re
import sqlite3

from playwright.sync_api import sync_playwright

from common import BASE, dump
from run_audit import AdminClient, Server

FAKE_IP = "203.0.113.77"


def subscribe(ctx, email):
    r = ctx.request.post(BASE + "/api/subscribe", form={"name": "QA", "email": email, "website": "", "next": "/"},
                         headers={"CF-Connecting-IP": FAKE_IP}, max_redirects=0)
    return r.status


def main():
    out = {}
    with Server("claims") as srv, sync_playwright() as p:
        srv.create_admin()
        b = p.chromium.launch()
        a = AdminClient(b, srv.password)

        # Sàn thiếu giấy phép bị chặn?
        r = a.ctx.request.post(BASE + "/admin/brokers/new", max_redirects=0, form={"name": "Sàn KhongGP", "kind": "forex", "csrf_token": a.csrf()})
        out["broker_no_license_status"] = r.status
        a.post("/admin/brokers/new", {"name": "Sàn A", "kind": "forex", "license": "-", "is_active": "1"})
        out["license_gach_ngang_duoc_chap_nhan"] = srv.counts()["brokers"] == 1

        # "Mỗi ưu đãi ghi rõ mức nạp tối thiểu, phần rút được và thời hạn"
        a.post("/admin/bonus/new", {"broker_id": 1, "type": "deposit", "title": "QAFIC bonus thiếu trường", "is_active": "1"})
        page = a.ctx.new_page()
        page.goto(BASE + "/bonus")
        card = page.inner_text(".bcard")
        out["bonus_thieu_truong_van_dang"] = {"so_bonus": srv.counts()["bonuses"], "the": re.sub(r"\s+", " ", card)[:200]}
        page.goto(BASE + "/")
        out["hero_card_label_khi_khong_featured"] = page.locator(".hero-card").count()

        # Email chỉ tới người đã xác nhận, có link hủy
        anon = b.new_context()
        subscribe(anon, "qa-pending@example.test")
        subscribe(anon, "qa-done@example.test")
        con = sqlite3.connect(srv.db)
        token = con.execute("select token from subscribers where email='qa-done@example.test'").fetchone()[0]
        con.close()
        pg = anon.new_page()
        pg.goto(BASE + "/xac-nhan/" + token)
        pg.click('.status-box form button[type="submit"]')
        pg.wait_for_load_state()
        a.post("/admin/subscribers/mail", {"subject": "QAFIC chiến dịch", "body": "QAFIC thân thư", "action": "send"})

        # Cookie public sau khi xem trang và gửi form
        fresh = b.new_context()
        pf = fresh.new_page()
        for u in ("/", "/bonus", "/lien-he"):
            pf.goto(BASE + u)
        out["cookie_khi_chi_xem"] = [c["name"] for c in fresh.cookies()]
        r = fresh.request.post(BASE + "/api/contact", form={"topic": "x", "name": "QA", "email": "qa-c@example.test", "body": "QAFIC", "website": ""},
                               headers={"CF-Connecting-IP": FAKE_IP}, max_redirects=0)
        out["cookie_sau_form"] = [{"name": c["name"], "expires_in_s": round(c["expires"] - __import__("time").time())} for c in fresh.cookies()]
        fonts = fresh.new_page()
        reqs = []
        fonts.on("request", lambda q: reqs.append(q.url))
        fonts.goto(BASE + "/", wait_until="networkidle")
        out["request_ngoai"] = sorted({re.sub(r"^https?://([^/]+).*", r"\1", u) for u in reqs if not u.startswith(BASE)})
        b.close()
    log = srv.log.read_text(encoding="utf-8", errors="replace")
    blob = srv.db.read_bytes() + b"".join(f.read_bytes() for f in srv.dir.glob("qa.db-*"))
    out["ip_trong_db"] = FAKE_IP.encode() in blob
    out["ip_trong_log_server"] = FAKE_IP in log
    con = sqlite3.connect(srv.db)
    out["cot_co_ip"] = [(t, c[1]) for t in ("subscribers", "contact_messages", "click_logs", "banners", "admin_sessions")
                        for c in con.execute(f"pragma table_info({t})") if "ip" in c[1].lower().split("_")]
    out["campaign"] = con.execute("select status, sent_count from campaigns").fetchall()
    con.close()
    out["log_co_gui_cho_pending"] = "qa-pending@example.test" in log.split("QAFIC chiến dịch")[-1] if "QAFIC chiến dịch" in log else None
    mails = [ln for ln in log.splitlines() if "QAFIC chiến dịch" in ln]
    out["dong_log_chien_dich"] = [ln[:160] for ln in mails][:4]
    dump("claims_check.json", out)
    for k, v in out.items():
        print(k, v)


if __name__ == "__main__":
    main()
