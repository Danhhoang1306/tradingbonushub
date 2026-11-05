"""So vài trang với design/ (http.server cổng 8015). Ảnh ghép ở QA_WORK/design/. Design tải thư viện qua CDN nên cần mạng;
bản thật chặn Google Fonts không chặn. Không có kết quả tự động: mở ảnh ghép để xem."""
import subprocess
import sys

from PIL import Image
from playwright.sync_api import sync_playwright

from qalib import BASE, ROOT, WORK, Http, Server, mk_banner, mk_bonus, mk_broker, mk_post, png_bytes

OUT = WORK / "design"
OUT.mkdir(parents=True, exist_ok=True)
D = "http://127.0.0.1:8015/"
ds = subprocess.Popen([sys.executable, "-m", "http.server", "8015", "--bind", "127.0.0.1", "--directory", str(ROOT / "design")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
s = Server("design").start()
s.cli_admin()
h = Http().login()
h.post("/admin/media/upload", {"alt": "ảnh"}, files={"files": ("a.png", png_bytes(300, 300), "image/png")})
mp = s.sql("select path from media_files")[0][0]
names = [("Exness", "forex"), ("Vantage", "forex"), ("Bybit", "crypto")]
for i, (n, kd) in enumerate(names):
    mk_broker(h, n, kind=kd, in_compare="1", featured="1" if i == 0 else None, license="FSCA · CySEC")
ids = [x[0] for x in s.sql("select id from brokers order by id")]
for i, t in enumerate(("nodep", "deposit", "cashback", "contest", "crypto", "deposit")):
    mk_bonus(h, ids[i % 3], f"Ưu đãi {t} dành cho tài khoản mới", type=t, amount=f"${(i + 1) * 30}", value_num=str((i + 1) * 30), expiry_date="2030-12-31", min_deposit="$10", withdrawable="Lợi nhuận")
for i in range(6):
    mk_post(h, f"Cách tính khối lượng lot phần {i}", cover_path=mp, excerpt="Tóm tắt", category="Hướng dẫn")
mk_banner(h, "QC", placement="after-bonus", broker_id=ids[0], target_url="https://aff.example.test/")


def lazy(pg):
    pg.evaluate("async()=>{for(let y=0;y<document.body.scrollHeight;y+=500){window.scrollTo(0,y);await new Promise(r=>setTimeout(r,40));}window.scrollTo(0,0)}")
    pg.wait_for_timeout(300)


T = [("home", "Trang%20chu%20v2.dc.html", "/"), ("bonus", "Cac%20trang.dc.html#bonus/all", "/bonus"), ("san", "Cac%20trang.dc.html#san/all", "/san"), ("compare", "Cac%20trang.dc.html#san/compare", "/san/so-sanh"), ("contact", "Cac%20trang.dc.html#gioithieu/contact", "/lien-he")]
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w in (1440, 390):
            for name, dpath, path in T:
                pg = b.new_page(viewport={"width": w, "height": 900})
                try:
                    pg.goto(D + dpath, wait_until="networkidle", timeout=45000)
                    pg.wait_for_timeout(2500)
                    pg.screenshot(path=str(OUT / f"d_{name}_{w}.png"), full_page=True)
                except Exception as e:
                    print("design lỗi", name, w, str(e)[:100], flush=True)
                pg.close()
                pg = b.new_page(viewport={"width": w, "height": 900})
                pg.goto(BASE + path, wait_until="load")
                lazy(pg)
                pg.screenshot(path=str(OUT / f"m_{name}_{w}.png"), full_page=True)
                pg.close()
                a, c = OUT / f"d_{name}_{w}.png", OUT / f"m_{name}_{w}.png"
                if a.exists():
                    ia, ic = Image.open(a), Image.open(c)
                    hh = min(max(ia.height, ic.height), 3000)
                    m = Image.new("RGB", (ia.width + ic.width + 20, hh), (255, 0, 255))
                    m.paste(ia, (0, 0))
                    m.paste(ic, (ia.width + 20, 0))
                    m.thumbnail((1800, 1500))
                    m.save(OUT / f"sbs_{name}_{w}.png")
        b.close()
finally:
    s.stop()
    ds.terminate()
print("xong", OUT, flush=True)
