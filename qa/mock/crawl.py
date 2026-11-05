"""Crawl bằng Playwright: toàn bộ public + admin, ở 1440 và 390. Ghi out/crawl_<label>.jsonl.

Mỗi dòng: url, viewport, status, title, text (innerText), alltext (textContent, gồm phần ẩn), attrs,
jsonld, html (DOM sau render), raw (response gốc), images hỏng, nhãn trống, request mạng.
"""
import json
import sqlite3
from collections import deque
from urllib.parse import urldefrag, urljoin, urlparse

from playwright.sync_api import sync_playwright

from common import ADMIN_EMAIL, BASE, OUT, VIEWPORTS

COLLECT_JS = r"""
() => {
  const ATTRS = ['alt','placeholder','title','value','href','src','srcset','content','aria-label','aria-description',
                 'action','formaction','poster','download','label','data-view-url','name'];
  const attrs = [];
  for (const el of document.querySelectorAll('*')) {
    for (const a of ATTRS) {
      if (!el.hasAttribute(a)) continue;
      if (a === 'name' && el.tagName !== 'META') continue;
      if (a === 'value' && el.getAttribute('name') === 'csrf_token') continue;
      const v = el.getAttribute(a);
      if (v) attrs.push({tag: el.tagName.toLowerCase(), attr: a, value: v,
                         name: el.getAttribute('name') || el.getAttribute('property') || ''});
    }
  }
  for (const ta of document.querySelectorAll('textarea')) if (ta.value) attrs.push({tag:'textarea', attr:'value', value: ta.value, name: ta.name});
  for (const o of document.querySelectorAll('option')) attrs.push({tag:'option', attr:'text', value:o.textContent, name:''});
  const brokenImgs = [...document.images].filter(i => !i.complete || i.naturalWidth === 0).map(i => i.currentSrc || i.getAttribute('src'));
  const noAlt = [...document.images].filter(i => !i.hasAttribute('alt')).map(i => i.getAttribute('src'));
  const bgs = new Set();
  for (const el of document.querySelectorAll('body *')) {
    const b = getComputedStyle(el).backgroundImage;
    if (b && b.includes('url(')) bgs.add(b);
  }
  const label = el => (el.innerText || '').trim() || el.getAttribute('aria-label') || el.getAttribute('title') ||
    [...el.querySelectorAll('img')].map(i => i.alt).join('').trim() || (el.value || '').trim();
  const visible = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'; };
  const emptyLabels = [];
  for (const el of document.querySelectorAll('a[href], button, h1, h2, h3, h4, h5, h6, th, dt, dd, label, legend, li, option[value]:not([value=""])')) {
    if (!visible(el) && el.tagName !== 'OPTION') continue;
    if (['TH','DD'].includes(el.tagName) && el.closest('[role="table"]')) continue;
    if (!label(el) && !el.querySelector('input,select,textarea')) emptyLabels.push(el.tagName.toLowerCase() + '.' + (el.className || '') + ' ' + el.outerHTML.slice(0, 140));
  }
  for (const el of document.querySelectorAll('input:not([type=hidden]):not([hidden]), select, textarea')) {
    if (!visible(el)) continue;
    const named = el.labels?.length || el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('placeholder');
    if (!named) emptyLabels.push('control-no-label ' + el.outerHTML.slice(0, 140));
  }
  return {
    title: document.title, text: document.body ? document.body.innerText : '', alltext: document.body ? document.body.textContent : '',
    attrs, jsonld: [...document.querySelectorAll('script[type="application/ld+json"]')].map(s => s.textContent),
    links: [...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href')),
    forms: [...document.querySelectorAll('form[method="get"],form:not([method])')].map(f => f.getAttribute('action')),
    brokenImgs, noAlt, bgs: [...bgs], emptyLabels,
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    html: document.documentElement.outerHTML,
  };
}
"""

PUBLIC_SEEDS = [
    "/", "/bonus", "/bonus?sort=value", "/bonus?sort=expiry", "/bonus?type=abc",
    *[f"/bonus?type={t}" for t in ("nodep", "deposit", "cashback", "contest", "crypto")],
    "/san", "/san?kind=forex", "/san?kind=crypto", "/san/so-sanh", "/san/so-sanh?ids=", "/san/so-sanh?ids=1,2,3",
    "/san/so-sanh?ids=999", "/san/khong-co", "/san/khong-co?tab=bonus",
    "/tin-tuc", "/tin-tuc?page=2", "/tin-tuc/khong-co",
    *[f"/tin-tuc?cat={c}" for c in ("Hướng dẫn", "Kiến thức", "So sánh", "Tin sàn")],
    "/gioi-thieu", "/gioi-thieu/cach-danh-gia", "/gioi-thieu/affiliate", "/lien-he", "/dieu-khoan", "/bao-mat",
    "/xac-nhan/token-sai", "/huy-dang-ky/token-sai", "/khong-ton-tai", "/admin/login",
]
ADMIN_SEEDS = [
    "/admin", *[f"/admin/bonus?tab={t}" for t in ("all", "on", "off", "exp")], "/admin/bonus/new",
    "/admin/brokers?tab=list", "/admin/brokers?tab=links", "/admin/brokers/new",
    "/admin/ads?tab=banner", "/admin/ads?tab=stats", "/admin/ads/new",
    *[f"/admin/home?tab={t}" for t in ("sections", "hero", "about", "why", "types", "contact", "menu")],
    *[f"/admin/posts?tab={t}" for t in ("all", "pub", "draft")], "/admin/posts/new",
    *[f"/admin/pages?tab={t}" for t in ("bonus", "san", "tin", "gioithieu", "lienhe", "terms", "privacy", "system")],
    "/admin/media", "/admin/subscribers?tab=list", "/admin/subscribers?tab=mail",
    "/admin/messages?tab=all", "/admin/messages?tab=unread",
    *[f"/admin/settings?tab={t}" for t in ("general", "seo", "social", "tracking", "users")],
]
RAW_PROBES = [
    "/sitemap.xml", "/robots.txt", "/health", "/docs", "/redoc", "/openapi.json", "/go/broker/1", "/go/ad/1",
    "/design/", "/design/Admin.dc.html", "/design/support.js", "/design/image-slot.js", "/design/assets/logo.png",
    "/design/.image-slots.state.json", "/Admin.dc.html", "/support.js", "/image-slot.js", "/static/support.js",
    "/static/image-slot.js", "/static/design/Admin.dc.html", "/static/../design/Admin.dc.html",
    "/static/%2e%2e/design/Admin.dc.html", "/media/../design/support.js", "/media/%2e%2e/%2e%2e/design/support.js",
    "/Trading%20Bonus%20Hub%20design.zip", "/.env", "/static/.env", "/mail%20to/",
]
SKIP_FOLLOW = ("/go/", "/admin/logout", "/api/", "/media/", "/static/")


def canon(base_url: str, href: str | None) -> str | None:
    if not href:
        return None
    url = urldefrag(urljoin(base_url, href))[0]
    p = urlparse(url)
    if p.scheme not in ("http", "https") or url.rstrip("/").split("?")[0] == "":
        return None
    return url if p.netloc == urlparse(BASE).netloc else None


def visit(page, url, net):
    net.clear()
    resp = page.goto(url, wait_until="load", timeout=30000)
    return finish(page, resp, net, url)


def finish(page, resp, net, url):
    """Cuộn hết trang để ảnh lazy tải, rồi thu thập."""
    page.evaluate("async () => { const h = document.body ? document.body.scrollHeight : 0;"
                  " for (let y = 0; y < h; y += 700) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 15)); }"
                  " window.scrollTo(0, 0); }")
    try:
        page.wait_for_load_state("networkidle", timeout=3000)
    except Exception:
        pass
    data = page.evaluate(COLLECT_JS)
    try:
        raw = resp.text() if resp else ""
    except Exception:
        raw = ""
    data.update(url=page.url, requested=url, status=resp.status if resp else None, raw=raw, network=list(net))
    return data


def bfs(page, seeds, net, out, vw, scope, admin_only=False, limit=400):
    queue, seen = deque(BASE + s for s in seeds), set()
    while queue and len(seen) < limit:
        url = queue.popleft()
        key = url
        if key in seen:
            continue
        seen.add(key)
        try:
            data = visit(page, url, net)
        except Exception as e:
            out.write(json.dumps({"url": url, "viewport": vw, "scope": scope, "error": str(e)[:300]}, ensure_ascii=False) + "\n")
            continue
        data.update(viewport=vw, scope=scope)
        out.write(json.dumps(data, ensure_ascii=False) + "\n")
        for href in data["links"] + [f for f in data["forms"] if f]:
            nxt = canon(page.url, href)
            if not nxt:
                continue
            path = urlparse(nxt).path
            if path.startswith(SKIP_FOLLOW):
                continue
            if admin_only != path.startswith("/admin"):
                continue
            queue.append(nxt)
    return len(seen)


def login(page, password, email=ADMIN_EMAIL):
    page.goto(BASE + "/admin/login")
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_url("**/admin*")


def new_context(browser, vw):
    w, h = VIEWPORTS[vw]
    ctx = browser.new_context(viewport={"width": w, "height": h}, locale="vi-VN", ignore_https_errors=False)
    ctx.set_default_timeout(20000)
    return ctx


def attach_net(page):
    net = []
    def on_resp(r):
        net.append({"url": r.url, "status": r.status, "type": r.request.resource_type})
    def on_fail(r):
        net.append({"url": r.url, "status": "FAILED", "type": r.resource_type, "error": r.failure})
    page.on("response", on_resp)
    page.on("requestfailed", on_fail)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    return net, errors


def form_states(page, net, out, vw, db_path):
    """Trạng thái form: lỗi, thành công, trang xác nhận/hủy đăng ký, trang 500. Làm bẩn DB: chỉ gọi ở cuối."""
    def rec(tag, resp, url):
        d = finish(page, resp, net, url)
        d.update(viewport=vw, scope="public", state=tag)
        out.write(json.dumps(d, ensure_ascii=False) + "\n")

    sub = 'form[action="/api/subscribe"]'
    page.goto(BASE + "/")
    page.evaluate("s => { document.querySelector(s).noValidate = true }", sub)
    page.fill(sub + ' input[name="email"]', "khong-hop-le")
    net.clear()
    with page.expect_navigation():
        page.click(sub + ' button[type="submit"]')
    rec("subscribe-invalid", None, "/#dang-ky")

    page.goto(BASE + "/")
    page.fill(sub + ' input[name="name"]', "QA")
    page.fill(sub + ' input[name="email"]', f"qa-sub-{vw}@example.test")
    net.clear()
    with page.expect_navigation():
        page.click(sub + ' button[type="submit"]')
    rec("subscribe-ok", None, "/#dang-ky")

    page.goto(BASE + "/lien-he")
    net.clear()
    with page.expect_navigation():
        page.click('form[action="/api/contact"] button[type="submit"]')
    rec("contact-invalid", None, "/lien-he")

    page.goto(BASE + "/lien-he")
    page.fill('form[action="/api/contact"] input[name="email"]', f"qa-contact-{vw}@example.test")
    page.fill('form[action="/api/contact"] textarea[name="body"]', "Nội dung kiểm thử của QA")
    net.clear()
    with page.expect_navigation():
        page.click('form[action="/api/contact"] button[type="submit"]')
    rec("contact-ok", None, "/lien-he")

    con = sqlite3.connect(db_path)
    token = con.execute("select token from subscribers where email=?", (f"qa-sub-{vw}@example.test",)).fetchone()[0]
    con.close()
    for tag, path in (("sub-confirmed", f"/xac-nhan/{token}"), ("sub-unsubscribed", f"/huy-dang-ky/{token}")):
        net.clear()
        rec(tag, page.goto(BASE + path), path)

    # Trang 500 thật: thiếu bảng bonuses làm trang chủ lỗi DB, rồi trả lại ngay. (Thiếu settings thì app tự dùng mặc định, vẫn 200.)
    con = sqlite3.connect(db_path, timeout=20)
    con.execute("alter table bonuses rename to bonuses_qa")
    con.commit()
    try:
        net.clear()
        rec("error-500", page.goto(BASE + "/"), "/")
    finally:
        con.execute("alter table bonuses_qa rename to bonuses")
        con.commit()
        con.close()


def crawl(label, password, db_path=None, states=False, editor_password=None, viewports=VIEWPORTS):
    """Trả về số URL đã mở theo viewport/scope. states=True thêm form_states (làm bẩn DB)."""
    path = OUT / f"crawl_{label}.jsonl"
    OUT.mkdir(parents=True, exist_ok=True)
    counts, probes = {}, []
    with sync_playwright() as p, path.open("w", encoding="utf-8") as out:
        browser = p.chromium.launch()
        for vw in viewports:
            ctx = new_context(browser, vw)
            page = ctx.new_page()
            net, errs = attach_net(page)
            counts[f"public@{vw}"] = bfs(page, PUBLIC_SEEDS, net, out, vw, "public")
            if vw == next(iter(viewports)):
                for path_ in RAW_PROBES:
                    r = ctx.request.get(BASE + path_, max_redirects=0)
                    body = r.text() if r.status < 400 or "text" in r.headers.get("content-type", "") else ""
                    probes.append({"path": path_, "status": r.status, "type": r.headers.get("content-type", ""),
                                   "location": r.headers.get("location", ""), "body": body[:200000]})
            login(page, password)
            counts[f"admin@{vw}"] = bfs(page, ADMIN_SEEDS, net, out, vw, "admin", admin_only=True)
            if editor_password:
                ectx = new_context(browser, vw)
                epage = ectx.new_page()
                enet, _ = attach_net(epage)
                login(epage, editor_password, "qa-editor@example.test")
                for u in ("/admin", "/admin/settings"):
                    d = visit(epage, BASE + u, enet)
                    d.update(viewport=vw, scope="admin", state="editor")
                    out.write(json.dumps(d, ensure_ascii=False) + "\n")
                ectx.close()
            ctx.close()
            if errs:
                out.write(json.dumps({"url": "(pageerror)", "viewport": vw, "scope": "js", "error": errs[:20]}, ensure_ascii=False) + "\n")
        if states:  # sau cùng, để crawl ở cả hai viewport thấy đúng DB rỗng
            for vw in viewports:
                ctx = new_context(browser, vw)
                page = ctx.new_page()
                net, _ = attach_net(page)
                form_states(page, net, out, vw, db_path)
                ctx.close()
        browser.close()
    (OUT / f"probes_{label}.json").write_text(json.dumps(probes, ensure_ascii=False, indent=1), encoding="utf-8")
    return counts


def read_crawl(label):
    with (OUT / f"crawl_{label}.jsonl").open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]
