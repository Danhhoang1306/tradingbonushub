"""Bước 6: liệt kê chữ viết cứng ở phần public (template + chuỗi Python) và phân loại chuỗi trong app/content.py.

Bổ sung cho pha C của run_audit.py: pha C đo trên trang render thật, file này đọc tĩnh nên thấy cả nhánh hiếm gặp.
Chạy: .venv\\Scripts\\python.exe qa\\mock\\hardcoded.py  -> out/hardcoded_static.json, out/content_strings.json
"""
import ast
import re

from common import ROOT, dump, norm

TPL = [ROOT / "templates" / "base_public.html", *sorted((ROOT / "templates" / "public").glob("*.html"))]
WORD = re.compile(r"[A-Za-zÀ-ỹ]{2,}")


def template_literals():
    out = {}
    for path in TPL:
        src = path.read_text(encoding="utf-8")
        src = re.sub(r"\{#.*?#\}", lambda m: "\n" * m.group(0).count("\n"), src, flags=re.S)
        src = re.sub(r"<(script|style|noscript)\b.*?</\1>", lambda m: "\n" * m.group(0).count("\n"), src, flags=re.S)
        for n, line in enumerate(src.splitlines(), 1):
            # literal chuỗi trong biểu thức Jinja, ví dụ empty("Chưa có sàn nào.")
            for m in re.finditer(r"""(?:\{\{|\{%)(.*?)(?:\}\}|%\})""", line):
                for s in re.findall(r'"([^"]*)"', m.group(1)):
                    if re.search(r"[À-ỹ ]", s) and WORD.search(s):
                        out.setdefault(s, set()).add(f"{path.name}:{n}")
            bare = re.sub(r"\{\{.*?\}\}|\{%.*?%\}", "\x00", line)
            for m in re.finditer(r'(?:alt|placeholder|title|aria-label)="([^"]+)"', bare):
                t = norm(m.group(1).replace("\x00", " "))
                if WORD.search(t):
                    out.setdefault(t, set()).add(f"{path.name}:{n}")
            for m in re.finditer(r">([^<>]+)<|^([^<>]+)<|>([^<>]+)$", bare):
                t = norm((m.group(1) or m.group(2) or m.group(3) or "").replace("\x00", " "))
                if WORD.search(t):
                    out.setdefault(t, set()).add(f"{path.name}:{n}")
    return {k: sorted(v) for k, v in sorted(out.items())}


def python_literals():
    """Chuỗi tiếng Việt trong app/routes/public.py, app/queries.py, app/templating.py, app/mailer.py."""
    out = {}
    for rel in ("app/routes/public.py", "app/queries.py", "app/templating.py", "app/mailer.py"):
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and re.search(r"[À-ỹ]", node.value) \
                    and not (isinstance(getattr(node, "parent", None), ast.Expr)):
                t = norm(node.value)
                if len(t) < 120:
                    out.setdefault(t, set()).add(f"{rel}:{node.lineno}")
    return {k: sorted(v) for k, v in sorted(out.items())}


def content_strings():
    """Mọi chuỗi trong DEFAULTS (không phải id/url/đường dẫn), kèm đường dẫn khóa."""
    import sys
    sys.path.insert(0, str(ROOT))
    from app.content import DEFAULTS
    out = []

    def walk(n, p):
        if isinstance(n, dict):
            for k, v in n.items():
                if k not in ("id", "url", "on"):
                    walk(v, f"{p}.{k}" if p else k)
        elif isinstance(n, list):
            for i, v in enumerate(n):
                walk(v, f"{p}[{i}]")
        elif isinstance(n, str) and n and not n.startswith("/"):
            out.append({"key": p, "text": n})

    walk(DEFAULTS, "")
    return out


# Phân loại tay từng khóa (khớp đầu chuỗi). Không khớp = chữ giao diện. Nếu đổi DEFAULTS, chạy lại để thấy khóa mới.
CLAIM_KEYS = (
    "meta_desc", "hero.sub", "footer.about_text", "footer.copyright", "system_text.header_cta_page",
    "system_text.sub_confirmed_text", "pages.bonus.desc", "pages.san", "pages.gioithieu.desc", "home_about.text",
    "home_about.points", "home_about.badge", "home_bonus.title", "home_why.title", "home_why.text", "home_why.stat",
    "home_why.reasons", "home_contact.text", "about_blocks", "contact_page.response_note",
)
KNOWLEDGE_KEYS = ("bonus_types", "footer.risk_note", "cta_note", "ads_note")


def classify(key: str) -> str:
    if key.startswith(CLAIM_KEYS):
        return "tuyen_bo"  # khẳng định về site/sàn: user cần xác nhận đúng sự thật
    if key.startswith(KNOWLEDGE_KEYS) and not key.endswith((".id", ".short", ".label")):
        return "kien_thuc"  # mô tả chung, cảnh báo, công bố: nên đọc lại nhưng không cam kết về site
    return "giao_dien"


if __name__ == "__main__":
    dump("hardcoded_static.json", {"template": template_literals(), "python": python_literals()})
    rows = [r | {"loai": classify(r["key"])} for r in content_strings()]
    dump("content_strings.json", rows)
    counts = {}
    for r in rows:
        counts[r["loai"]] = counts.get(r["loai"], 0) + 1
    print(len(rows), "chuỗi trong DEFAULTS", counts)
