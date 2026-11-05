"""Chụp màn hình trang chủ + các trang chính với DB rỗng, ở 1440 và 390 -> out/shots/. Cần nhìn bằng mắt:
quét text không thấy được chữ nằm trong ảnh (ví dụ logo trong ảnh nền hero)."""
from playwright.sync_api import sync_playwright

from common import BASE, OUT
from crawl import new_context
from run_audit import Server

PAGES = {"home": "/", "bonus": "/bonus", "san": "/san", "sosanh": "/san/so-sanh", "tin": "/tin-tuc", "gt": "/gioi-thieu",
         "lienhe": "/lien-he", "terms": "/dieu-khoan", "404": "/khong-ton-tai"}


def main():
    (OUT / "shots").mkdir(parents=True, exist_ok=True)
    with Server("shots"), sync_playwright() as p:
        b = p.chromium.launch()
        for vw in ("1440", "390"):
            ctx = new_context(b, vw)
            page = ctx.new_page()
            for name, path in PAGES.items():
                page.goto(BASE + path, wait_until="networkidle")
                page.screenshot(path=str(OUT / "shots" / f"{name}_{vw}.png"), full_page=name != "home")
            ctx.close()
        b.close()


if __name__ == "__main__":
    main()
