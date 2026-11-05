"""Quét secret trong TOÀN BỘ lịch sử git (mọi ref, gồm tag old-project-final) -> out/secret_scan.json.

Đọc mọi blob và commit message đến được từ `git rev-list --all`. KHÔNG in giá trị: chỉ ghi mẫu, đường dẫn,
blob, độ dài và 2 ký tự đầu. Không đọc file .env trên đĩa (brief mục 2).
Chạy: .venv\\Scripts\\python.exe qa\\mock\\secret_scan.py
"""
import math
import re
import subprocess
from collections import Counter

from common import ROOT, dump

MAX_BLOB = 3_000_000
HIGH = {  # định dạng đặc trưng: gần như chắc chắn là secret nếu khớp
    "private_key": r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY",
    "aws_key": r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
    "github_token": r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{30,}",
    "google_api": r"\bAIza[0-9A-Za-z_-]{35}\b",
    "slack": r"\bxox[abprs]-[0-9A-Za-z-]{10,}",
    "sendgrid": r"\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}",
    "stripe": r"\b[sr]k_live_[0-9a-zA-Z]{16,}",
    "telegram_bot": r"\b\d{8,10}:AA[A-Za-z0-9_-]{32,}\b",
    "anthropic_openai": r"\bsk-(?:ant-)?[A-Za-z0-9_-]{32,}",
    "jwt": r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    "cf_tunnel": r"(?i)tunnelsecret|tunnel_token|\beyJhIjoi[A-Za-z0-9+/=_-]{20,}",
}
ASSIGN = re.compile(
    r"""(?ix)(?P<key>[\w.-]*(?:pass(?:word|wd)?|pwd|secret|api[_-]?key|access[_-]?key|auth[_-]?token|token|private[_-]?key|fernet|encryption[_-]?key)[\w-]*)
        ["']?[ ]*(?:=|:|:=)[ ]*["']?(?P<val>[^\s"',;#)}\]]{6,})""")  # không vượt qua xuống dòng: KEY= rỗng là bình thường
CONN = re.compile(r"(?i)(?P<scheme>[a-z][a-z0-9+.-]*)://(?P<user>[^\s:/@'\"]{1,64}):(?P<val>[^\s@/'\"]{3,})@(?P<host>[^\s/'\"]+)")
ODBC = re.compile(r"(?i)\b(?:pwd|password)[ \t]*=[ \t]*(?P<val>[^;\s'\"]{4,})[ \t]*;?")
LONG = re.compile(r"(?<![\w/+.-])(?P<val>[a-f0-9]{32,}|[A-Za-z0-9+/_-]{40,}={0,2})(?![\w/+.-])")  # chuỗi dài ngẫu nhiên, gán cho khóa nào cũng bắt
PLACEHOLDER = re.compile(
    r"(?i)^(?:<.*>|\$\{?.*|\{\{?.*|%\(?.*|x{3,}.*|\*{3,}|\.{3,}|none|null|true|false|changeme.*|change[_-]?me.*|example.*|your[_-].*|test.*|dummy.*"
    r"|fake.*|placeholder.*|secret|password|passw0rd|admin|redacted|string|str|int|bool|form\(.*|getenv.*|os\.environ.*|env\(.*|config\..*|settings\..*"
    r"|request\..*|self\..*|args\..*|data\..*|form\..*|payload\..*|body\..*|new_.*|hash.*|get_.*|create_.*|generate.*|token_.*|secrets\..*"
    r"|mapped_column.*|column\(.*|str\s*\|.*)$")
CODE_LIKE = re.compile(r"[()\[\]{}]|^[a-z_]+\.[a-z_]+|^[a-z_]+$|^[A-Z_]+$")
SKIP_PATH = re.compile(r"(?i)(?:\.min\.js|\.min\.css|package-lock\.json|\.lock|/migrations?/)$")


def run(*args, **kw):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True, **kw).stdout


def entropy(s: str) -> float:
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in Counter(s).values()) if n else 0.0


def mask(v: str) -> str:
    return f"{v[:2]}…(len {len(v)}, entropy {entropy(v):.1f})"


def scan_text(text, where, out):
    for name, pat in HIGH.items():
        for m in re.finditer(pat, text):
            line = text.count("\n", 0, m.start()) + 1
            out.append({"muc": "dinh_dang", "mau": name, **where, "dong": line, "mask": mask(m.group(0))})
    for rx, label in ((CONN, "conn_string"), (ODBC, "odbc_pwd"), (ASSIGN, "gan_gia_tri")):
        for m in rx.finditer(text):
            v = m.group("val").strip()
            if PLACEHOLDER.match(v):
                continue
            line = text.count("\n", 0, m.start()) + 1
            code_like = bool(CODE_LIKE.search(v))
            strong = not code_like and len(v) >= 8
            key = m.groupdict().get("key") or m.groupdict().get("scheme")
            out.append({"muc": "nghi_van" if strong else "yeu", "mau": label, "khoa": key, **where, "dong": line, "mask": mask(v)})
    for m in LONG.finditer(text):
        v = m.group("val")
        if entropy(v) >= 3.6 and re.search(r"\d", v) and re.search(r"[a-zA-Z]", v):
            line = text.count("\n", 0, m.start()) + 1
            out.append({"muc": "chuoi_dai", "mau": "chuoi_dai", **where, "dong": line, "mask": mask(v)})


def main():
    objs = [ln.split(" ", 1) for ln in run("rev-list", "--all", "--objects").decode("utf-8", "replace").splitlines()]
    paths = {o[0]: o[1] for o in objs if len(o) == 2}
    types = {}
    batch = "\n".join(paths).encode() + b"\n"
    for ln in run("cat-file", "--batch-check", input=batch).decode().splitlines():
        sha, typ, size = ln.split()[:3]
        types[sha] = (typ, int(size))
    out, skipped_big, scanned = [], [], 0
    for sha, path in paths.items():
        typ, size = types.get(sha, ("", 0))
        if typ != "blob":
            continue
        if size > MAX_BLOB:
            skipped_big.append({"path": path, "size": size})
            continue
        if SKIP_PATH.search(path):
            continue
        data = run("cat-file", "blob", sha)
        if b"\0" in data[:8000]:
            continue
        scanned += 1
        scan_text(data.decode("utf-8", "replace"), {"path": path, "blob": sha[:10]}, out)
    commits = run("rev-list", "--all").decode().split()
    msgs = run("log", "--all", "--format=%H%n%an <%ae>%n%B%n---").decode("utf-8", "replace")
    scan_text(msgs, {"path": "(commit message)", "blob": ""}, out)
    sensitive = [p for p in sorted(set(paths.values())) if re.search(
        r"(?i)(^|/)\.env($|\.)|\.pem$|\.key$|\.p12$|\.pfx$|id_rsa|credentials?\.json|\.db$|\.sqlite3?$|\.bak$|cloudflared\.ya?ml$|tunnel.*\.json$|mail to/", p)]
    tag = run("rev-list", "old-project-final").decode().split()
    # blob nghi vấn có nằm ở HEAD hay chỉ trong lịch sử
    head = set(run("ls-tree", "-r", "HEAD").decode("utf-8", "replace").split())
    for f in out:
        f["con_o_HEAD"] = any(h.startswith(f["blob"]) for h in head) if f["blob"] else False
    rep = {"commits": len(commits), "commits_tag_old": len(tag), "blobs_text": scanned, "file_nhay_cam": sensitive,
           "qua_lon_bo_qua": skipped_big, "tong": Counter(f["muc"] for f in out),
           "dinh_dang": [f for f in out if f["muc"] == "dinh_dang"], "nghi_van": [f for f in out if f["muc"] == "nghi_van"],
           "chuoi_dai": [f for f in out if f["muc"] == "chuoi_dai"],
           "yeu_so_luong": sum(1 for f in out if f["muc"] == "yeu")}
    dump("secret_scan.json", rep)
    print({k: (len(v) if isinstance(v, list) else v) for k, v in rep.items()})


if __name__ == "__main__":
    main()
