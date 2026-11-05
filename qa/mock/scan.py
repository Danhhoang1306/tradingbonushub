"""Bước 4-5: quét kết quả crawl và mã nguồn với danh sách mock + các mẫu nghi vấn.

Chia token mock làm 2 nhóm:
- strong: chuỗi đặc trưng (tên sàn, tiêu đề, email, link, giấy phép...). Quét text, thuộc tính, HTML gốc, mã nguồn.
- short: chuỗi ngắn hoặc số thuần. Khớp nguyên từ, chỉ ở text hiển thị và thuộc tính nhìn thấy được.
ALLOW: token trùng chữ giao diện được giữ (brief mục 5), kèm lý do. Hit của chúng vẫn đếm riêng, không ẩn đi.
"""
import re
from collections import defaultdict
from urllib.parse import urlparse

from common import BASE, ROOT, dump, fold, load, norm
from crawl import read_crawl

ALLOW = {
    # Nhãn loại bonus / chuyên mục / tab: brief mục 5 GIỮ
    "cashback": "nhãn loại bonus", "crypto": "nhãn loại", "cuộc thi": "nhãn loại bonus", "deposit bonus": "nhãn loại bonus",
    "no-deposit": "nhãn loại bonus", "hướng dẫn": "chuyên mục", "kiến thức": "chuyên mục", "so sánh": "tab/chuyên mục",
    "tin sàn": "chuyên mục", "tin tức": "menu", "tất cả": "tab", "danh sách": "tab admin", "link affiliate": "tab admin",
    "nháp": "trạng thái bài", "đã đăng": "trạng thái bài", "liên tục": "nhãn hạn bonus (expiry_label)", "có": "từ thường",
    "không": "từ thường", "—": "dấu ô trống", "admin": "chữ thường trong khu admin", "biên tập viên": "nhãn vai trò",
    "all": "giá trị tham số", "list": "giá trị tham số", "links": "giá trị tham số", "draft": "giá trị tham số",
    "pub": "giá trị tham số", "broker": "tên kỹ thuật", "web": "từ thường", "app": "từ thường", "pro": "từ thường",
    "ok": "từ thường", "spot": "từ thường", "standard": "chỉ là từ", "voucher": "chữ trong mô tả loại bonus",
    "tự động": "từ thường", "trong ngày": "từ thường", "hôm nay": "nhãn", "thêm sàn": "nút admin",
    "chọn tối đa 3 sàn:": "nhãn mục So sánh", "click theo ngày (30 ngày)": "nhãn admin",
    "copyright © 2026 tradingbonushub. một số liên kết là liên kết affiliate.": "chữ giữ (footer)",
    "ảnh chia sẻ (1200×630)": "nhãn trường admin",
    # Chuỗi con trùng chữ GIỮ: đã xem tay từng hit ở pha A, chỉ khớp trong mô tả loại bonus / hero
    "deposit bonus, cashback": "chuỗi con của hero.sub (GIỮ)", "lợi nhuận": "từ trong mô tả loại bonus",
    "cần kyc đầy đủ": "chuỗi con của points loại crypto (GIỮ)", "không giới hạn": "chú thích ô ngày admin",
    "1–2 ngày": "chuỗi con response_note, xem nhóm tuyên bố",
    'bật "so sánh" cho tối đa 3 sàn để hiện ở mục so sánh trên trang chủ. sàn "nổi bật" có nền tối.': "hướng dẫn admin",
    # Số trần: chỉ xuất hiện trong nhãn/thứ tự (30 ngày, 3 sàn, 500 ký tự, 01..10)
    **{n: "số trong nhãn hoặc thứ tự, không phải số liệu mock" for n in
       ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "20", "30", "50", "500")},
    "chúng tôi phản hồi trong 1–2 ngày làm việc. chúng tôi không tư vấn đầu tư cá nhân.": "chữ giữ (brief GIỮ), xem nhóm tuyên bố",
    "cảnh báo rủi ro: cfd là công cụ phức tạp và có rủi ro mất tiền nhanh do đòn bẩy. bonus không phải lời khuyên đầu tư.": "câu cảnh báo (GIỮ)",
    "so sánh no-deposit, deposit bonus, cashback, cuộc thi giao dịch và khuyến mãi crypto từ các sàn có giấy phép. mỗi ưu đãi ghi rõ khối lượng yêu cầu, thời hạn và giấy phép.": "hero sub (GIỮ), xem nhóm tuyên bố",
}
SOURCE_DIRS = ["templates", "static", "app", "alembic"]
SOURCE_EXT = {".html", ".js", ".css", ".py", ".mako", ".txt", ".ini", ".json", ".svg"}
VISIBLE_ATTRS = {"alt", "placeholder", "title", "value", "aria-label", "content", "text", "label"}

PATTERNS = {
    "so_cung": r"(?<![\w/.#-])\d[\d.,]*\+(?!\w)|\d[\d.,]*\s?%|\$\s?\d[\d.,]*|\d[\d.,]*\s?(?:USD|USDT)\b",
    "ngay_cung": r"(?<![\d/])\d{1,2}/\d{1,2}(?:/\d{2,4})?(?![\d/])|\b(?:19|20)\d{2}\b|tháng \d{1,2}|quý [IV]+",
    "placeholder": r"(?i)(?<!\w)(?:lorem|ipsum|demo|test|mẫu|minh ho[ạa]|minh họa|ảnh nền|placeholder|sample|todo|fixme|tbd|xxxx?)(?!\w)",
    "jinja_rong": r"\{\{|\}\}|\{%|%\}|(?<!\w)(?:None|undefined|NaN|nan|null|True|False|Traceback)(?!\w)|\[object ",
    "so_0": r"(?<![\w.,/:%$-])0(?![\w.,/:%])",
}
PATTERNS = {k: re.compile(v) for k, v in PATTERNS.items()}


def tiers():
    strong, short, allowed = [], [], []
    for row in load("mock_tokens.json"):
        t = row["token"]
        f = fold(t)
        if f in ALLOW or t.startswith("https://fonts.googleapis.com"):
            allowed.append(row)
        elif re.fullmatch(r"[\d.,:%$/–+\s-]+", t) or len(t) <= 5:
            short.append(row)
        else:
            strong.append(row)
    return strong, short, allowed


def boundary(tok):
    return re.compile(r"(?<![\w.,/$%])" + re.escape(tok) + r"(?![\w%])", re.I)


def snippet(text, at, width=70):
    return norm(text[max(0, at - width):at + width])


def rec_fields(r):
    yield "text", r.get("text", "")
    yield "alltext", r.get("alltext", "")
    for a in r.get("attrs", []):
        if a["attr"] in VISIBLE_ATTRS or a["attr"] in ("href", "src", "action"):
            yield f"@{a['tag']}.{a['attr']}", a["value"]
    for j in r.get("jsonld", []):
        yield "jsonld", j


def pagekey(r):
    u = r.get("url", "")
    return u.replace(BASE, "") + (f" [{r['state']}]" if r.get("state") else "")


def scan_crawl(label, extra_strong=(), ignore=()):
    """ignore: regex các giá trị do QA tự tạo (email QA...) không tính là hit."""
    rows = read_crawl(label)
    strong, short, allowed = tiers()
    strong_f = [(row["token"], fold(row["token"])) for row in strong] + [(t, fold(t)) for t in extra_strong]
    short_re = [(row["token"], boundary(row["token"])) for row in short]
    allow_f = [(row["token"], boundary(row["token"])) for row in allowed]
    ign = re.compile("|".join(ignore)) if ignore else None
    hits = {"mock_strong": defaultdict(list), "mock_short": defaultdict(list), "mock_allowed": defaultdict(set)}
    pats = {k: defaultdict(set) for k in PATTERNS}
    misc = {"dead_links": defaultdict(set), "external": defaultdict(set), "broken_img": defaultdict(set),
            "failed_req": defaultdict(set), "empty_label": defaultdict(set), "bad_cdn": defaultdict(set),
            "overflow": {}, "errors": [], "no_alt": defaultdict(set)}
    pages = set()
    for r in rows:
        if "error" in r:
            misc["errors"].append({k: r.get(k) for k in ("url", "viewport", "error")})
            continue
        vw, page = r["viewport"], pagekey(r)
        pages.add((r["scope"], vw, page))
        for field, value in rec_fields(r):
            if ign:
                value = ign.sub(" ", value)
            fv = fold(value)
            for tok, f in strong_f:
                at = fv.find(f)
                if at >= 0:
                    hits["mock_strong"][tok].append((page, vw, field, snippet(fv, at)))
            if field == "alltext" or field.endswith((".href", ".src", ".action")):
                continue
            nv = norm(value)
            for tok, rx in short_re:
                m = rx.search(nv)
                if m:
                    hits["mock_short"][tok].append((page, vw, field, snippet(nv, m.start())))
            for tok, rx in allow_f:
                if rx.search(nv):
                    hits["mock_allowed"][tok].add(page)
            for name, rx in PATTERNS.items():
                if nv.startswith(("http://", "https://", "/")):
                    continue  # URL mã hóa có %xx
                for m in rx.finditer(nv):
                    pats[name][(m.group(0), field if field == "text" else "attr")].add(page + "  «" + snippet(nv, m.start(), 45) + "»")
        for src_name in ("raw", "html"):  # HTML gốc: gồm comment, script, phần ẩn
            body = fold(ign.sub(" ", r.get(src_name, "")) if ign else r.get(src_name, ""))
            for tok, f in strong_f:
                at = body.find(f)
                if at >= 0:
                    hits["mock_strong"][tok].append((page, vw, src_name, snippet(body, at)))
            if "{{" in body or "{%" in body:
                pats["jinja_rong"][("{{ trong " + src_name, "html")].add(page)
            for m in re.finditer(r"<!--(.*?)-->", r.get(src_name, ""), re.S):
                pats["placeholder"][("comment HTML", "html")].add(page + " «" + norm(m.group(1))[:80] + "»")
        for a in r.get("attrs", []):
            v = a["value"].strip()
            if a["attr"] in ("href", "src", "action", "formaction"):
                if a["attr"] == "href" and (v in ("#", "") or v.lower().startswith("javascript:")):
                    misc["dead_links"][v].add(page)
                if v.startswith(("http://", "https://", "//")):
                    host = urlparse(v).netloc
                    if host != urlparse(BASE).netloc:
                        misc["external"][host].add(page + " " + v[:100])
        for src in r.get("brokenImgs", []):
            misc["broken_img"][src or "(rỗng)"].add(page)
        for src in r.get("noAlt", []):
            misc["no_alt"][src or "(rỗng)"].add(page)
        for e in r.get("emptyLabels", []):
            misc["empty_label"][e].add(f"{page} @{vw}")
        if r.get("overflow", 0) > 0:
            misc["overflow"][f"{page} @{vw}"] = r["overflow"]
        for n in r.get("network", []):
            u = n["url"]
            if re.search(r"unpkg|support\.js|image-slot|babel|/design/|\.dc\.html", u, re.I):
                misc["bad_cdn"][u].add(page)
            host = urlparse(u).netloc
            if host != urlparse(BASE).netloc:
                misc["external"][host].add("req: " + u[:100])
            status = n["status"]
            if status == "FAILED" or (isinstance(status, int) and status >= 400 and n["type"] != "document"):
                misc["failed_req"][f"{status} {u[:100]}"].add(page)
    report = {
        "label": label, "records": len(rows), "pages": len(pages),
        "pages_by_scope": {f"{s}@{v}": sum(1 for p in pages if p[0] == s and p[1] == v) for s, v, _ in pages},
        "mock_strong": {k: v[:8] + [f"... tổng {len(v)}"] for k, v in hits["mock_strong"].items()},
        "mock_short": {k: v[:8] + [f"... tổng {len(v)}"] for k, v in hits["mock_short"].items()},
        "mock_allowed": {k: f"{len(v)} trang" for k, v in hits["mock_allowed"].items()},
        "patterns": {n: [{"match": m[0], "where": m[1], "count": len(p), "sample": sorted(p)[:4]}
                         for m, p in sorted(d.items(), key=lambda kv: str(kv[0]))] for n, d in pats.items()},
        "misc": {k: ({kk: sorted(vv)[:5] + [f"tổng {len(vv)}"] for kk, vv in v.items()} if isinstance(v, defaultdict) else v)
                 for k, v in misc.items()},
    }
    dump(f"scan_{label}.json", report)
    return report


def scan_source():
    strong, short, _ = tiers()
    strong_f = [(r["token"], fold(r["token"])) for r in strong]
    short_re = [(r["token"], boundary(r["token"])) for r in short if not re.fullmatch(r"\d+", r["token"])]
    hits, pats = defaultdict(list), defaultdict(list)
    files = 0
    design_refs = []
    for d in SOURCE_DIRS:
        for p in (ROOT / d).rglob("*"):
            if not p.is_file() or "__pycache__" in p.parts or p.suffix not in SOURCE_EXT:
                continue
            files += 1
            rel = p.relative_to(ROOT).as_posix()
            text = p.read_text(encoding="utf-8", errors="replace")
            for n, line in enumerate(text.splitlines(), 1):
                fl = fold(line)
                for tok, f in strong_f:
                    if f in fl:
                        hits[tok].append(f"{rel}:{n}: {norm(line)[:130]}")
                if not p.suffix == ".css":
                    for tok, rx in short_re:
                        if rx.search(line):
                            hits[tok].append(f"{rel}:{n}: {norm(line)[:130]}")
                    if PATTERNS["placeholder"].search(line):
                        pats["placeholder"].append(f"{rel}:{n}: {norm(line)[:130]}")
                    if re.search(r"https?://", line):
                        pats["url"].append(f"{rel}:{n}: {norm(line)[:130]}")
                    if re.search(r"""(?:href|src)=["']#["']""", line):
                        pats["dead_link"].append(f"{rel}:{n}: {norm(line)[:130]}")
                if re.search(r"unpkg|support\.js|image-slot|babel|design/|\.dc\.html", line, re.I):
                    design_refs.append(f"{rel}:{n}: {norm(line)[:130]}")
    rep = {"files": files, "mock_hits": {k: v[:12] for k, v in hits.items()}, "patterns": pats, "design_refs": design_refs}
    dump("scan_source.json", rep)
    return rep
