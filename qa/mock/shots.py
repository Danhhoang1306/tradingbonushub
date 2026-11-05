"""Chụp màn hình để nhìn bằng mắt (quét text không thấy chữ nằm trong ảnh) -> out/shots/.

- DB rỗng: các trang chính ở 1440 và 390.
- Dữ liệu hư cấu: trang chủ ở 1700px để thấy rail hai bên hero (rail chỉ hiện từ 1572px).
"""
from playwright.sync_api import sync_playwright

from common import BASE, OUT
from crawl import new_context
from run_audit import AdminClient, Server, seed_fiction

PAGES = {"home": "/", "bonus": "/bonus", "san": "/san", "sosanh": "/san/so-sanh", "tin": "/tin-tuc", "gt": "/gioi-thieu",
         "lienhe": "/lien-he", "terms": "/dieu-khoan", "privacy": "/bao-mat", "404": "/khong-ton-tai"}


def empty_shots(browser):
    for vw in ("1440", "390"):
        ctx = new_context(browser, vw)
        page = ctx.new_page()
        for name, path in PAGES.items():
            page.goto(BASE + path, wait_until="networkidle")
            page.screenshot(path=str(OUT / "shots" / f"{name}_{vw}.png"), full_page=name != "home")
        if vw == "1440":
            page.goto(BASE + "/", wait_until="networkidle")
            page.screenshot(path=str(OUT / "shots" / "home_full_1440.png"), full_page=True)
        ctx.close()


def rail_shots(browser, srv):
    a = AdminClient(browser, srv.password)
    seed_fiction(a, srv)
    ctx = browser.new_context(viewport={"width": 1700, "height": 1000}, locale="vi-VN")
    page = ctx.new_page()
    beacons = []
    page.on("request", lambda r: beacons.append(r.url) if "/api/ad-view/" in r.url else None)
    page.goto(BASE + "/", wait_until="networkidle")
    page.screenshot(path=str(OUT / "shots" / "rail_1700.png"))
    page.evaluate("window.scrollTo(0, 780)")
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "shots" / "rail_1700_scroll.png"))
    page.evaluate("window.scrollTo(0, 0)")
    state = page.evaluate("""() => [...document.querySelectorAll('.rail')].map(r => {
        const b = r.getBoundingClientRect();
        return {cls: r.className, display: getComputedStyle(r).display, x: Math.round(b.x), w: Math.round(b.width),
                h: Math.round(b.height), text: r.innerText.replace(/\\s+/g, ' ').slice(0, 160)}; })""")
    print("rail:", state)
    print("beacon:", beacons)
    ctx.close()


def main():
    (OUT / "shots").mkdir(parents=True, exist_ok=True)
    with Server("shots") as srv, sync_playwright() as p:
        srv.create_admin()
        b = p.chromium.launch()
        empty_shots(b)
        rail_shots(b, srv)
        b.close()


if __name__ == "__main__":
    main()
