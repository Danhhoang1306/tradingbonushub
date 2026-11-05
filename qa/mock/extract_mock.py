"""Bước 1: trích tự động mọi chuỗi và số liệu mock từ design/*.dc.html -> out/mock_tokens.json.

Cách làm: tìm khối dữ liệu theo tên (BONUSES, BROKERS, POSTS, PAY, state.bonuses, ...), khớp ngoặc
rồi lấy mọi chuỗi và số trong khối. Thêm các chữ cứng trong markup của thiết kế có tên sàn, số, $ hoặc %.
"""
import re

from common import ROOT, dump, norm

DESIGN = ROOT / "design"
FILES = ["Admin.dc.html", "Cac trang.dc.html", "Trang chu v2.dc.html", "Trang chu.dc.html"]
BLOCKS = {  # (nhãn, regex điểm bắt đầu, ngay trước [ hoặc {)
    "Admin.dc.html": [("linkStats", r"\blinkStats:\s*"), ("bonuses", r"\bbonuses:\s*(?=\[)"),
                      ("brokers", r"\bbrokers:\s*(?=\[)"), ("banners", r"\bbanners:\s*(?=\[)"),
                      ("posts", r"\bposts:\s*(?=\[)"), ("subs", r"\bsubs:\s*(?=\[\s*\{)"),
                      ("admins", r"\badmins:\s*"), ("settings", r"\bsettings:\s*(?=\{)")],
    "Cac trang.dc.html": [("BONUSES", r"\bBONUSES\s*=\s*"), ("BROKERS", r"\bBROKERS\s*=\s*"), ("PAY", r"\bPAY\s*=\s*"),
                          ("POSTS", r"\bPOSTS\s*=\s*"), ("post.body", r"\bbody:\s*(?=\[)")],
    "Trang chu v2.dc.html": [("BONUSES", r"\bBONUSES\s*=\s*"), ("brokers", r"\bbrokers\s*=\s*(?=\[)")],
    "Trang chu.dc.html": [("BONUSES", r"\bBONUSES\s*=\s*"), ("brokers", r"\bbrokers\s*=\s*(?=\[)")],
}
# Khóa mang id/kỹ thuật hoặc chữ giao diện, không phải dữ liệu mock
SKIP_KEYS = {"id", "type", "kind", "slot", "placement", "on", "pub", "home", "compare", "featured", "role", "ord",
             "siteName", "metaTitle", "metaDesc", "keywords"}
BRAND = re.compile(r"exness|vantage|vt ?markets|bybit|okx|xxxx", re.I)
STR_RE = re.compile(r"(?:(\w+):\s*)?'((?:[^'\\]|\\.)*)'")
ANY_STR = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")


def match_block(text: str, start: int) -> str:
    open_c = text[start]
    close_c = {"[": "]", "{": "}"}[open_c]
    depth, i, quote = 0, start, None
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 1
            elif c == quote:
                quote = None
        elif c in "'\"`":
            quote = c
        elif c == open_c:
            depth += 1
        elif c == close_c:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    return text[start:]


def scan_block(block: str):
    strings = [m.group(2).replace("\\'", "'") for m in STR_RE.finditer(block) if m.group(1) not in SKIP_KEYS]
    no_str = ANY_STR.sub(" ", block)
    numbers = re.findall(r"(?<![\w.])(\d[\d.]*)(?!\w)", no_str)
    return strings, numbers


def markup_tokens(html: str):
    """Text node trong markup (ngoài <script>) có tên sàn, chữ số, $ hoặc %."""
    body = re.sub(r"<script\b.*?</script>", " ", html, flags=re.S | re.I)
    body = re.sub(r"<style\b.*?</style>", " ", body, flags=re.S | re.I)
    out = []
    for m in re.finditer(r">([^<>]+)<", body):
        t = norm(re.sub(r"\{\{.*?\}\}", " ", m.group(1)))
        if t and (BRAND.search(t) or re.search(r"\d|\$|%", t)):
            out.append(t)
    for m in re.finditer(r'(?:href|src|placeholder|alt|title)="([^"]*)"', body):
        t = norm(m.group(1))
        if t and "{{" not in t and (BRAND.search(t) or re.search(r"\$|%|\d{2}", t)) \
                and not t.startswith(("assets/", "support", "image-slot")):
            out.append(t)
    return out


def main():
    tokens: dict[str, set] = {}

    def add(tok, src):
        tok = norm(str(tok))
        if tok:
            tokens.setdefault(tok, set()).add(src)

    for fname in FILES:
        text = (DESIGN / fname).read_text(encoding="utf-8")
        script_at = text.find("class Component")
        code = text[script_at:]
        for label, pat in BLOCKS[fname]:
            for m in re.finditer(pat, code):
                at = m.end()
                if code[at] not in "[{":
                    continue
                strings, numbers = scan_block(match_block(code, at))
                for s in strings:
                    add(s, f"{fname}:{label}")
                for n in numbers:
                    add(n, f"{fname}:{label}#num")
        for t in markup_tokens(text[:script_at]):
            add(t, f"{fname}:markup")
    # Biến thể định dạng: 18420 -> 18.420, 18,420
    for t in list(tokens):
        if re.fullmatch(r"\d{4,}", t) and not t.startswith("20"):
            with_dot = f"{int(t):,}".replace(",", ".")
            add(with_dot, "variant")
            add(with_dot.replace(".", ","), "variant")
    # Tách danh sách giấy phép / nền tảng thành từng phần tử (FSA, CySEC, FCA -> từng tên)
    for t in list(tokens):
        if "," in t and len(t) < 40 and not re.search(r"\d", t):
            for part in t.split(","):
                add(part, "split")
    # Tên riêng trong brief mục 5
    for t in ["Exness", "Vantage", "VT Markets", "Bybit", "OKX", "xxxx", "Bài viết minh hoạ", "admin@tradingbonushub.com",
              "editor@tradingbonushub.com", "hello@tradingbonushub.com", "@tradingbonushub", "one.exness.link",
              "vantagemarkets.com", "vtmarkets.com"]:
        add(t, "brief#5")
    rows = [{"token": k, "sources": sorted(v)} for k, v in sorted(tokens.items(), key=lambda kv: kv[0].casefold())]
    dump("mock_tokens.json", rows)
    print(f"{len(rows)} token mock -> out/mock_tokens.json")


if __name__ == "__main__":
    main()
