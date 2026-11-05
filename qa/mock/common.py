"""Hằng và tiện ích dùng chung cho bộ audit mock (qa/mock). Xem qa/mock/README ở đầu run_audit.py."""
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get("QA_OUT", Path(__file__).parent / "out"))
TMP = Path(os.environ.get("QA_TMP", Path(tempfile.gettempdir()) / "tbh_qa_mock"))
PORT = int(os.environ.get("QA_PORT", "8013"))
if PORT == 8000:
    raise SystemExit("Cấm chạy ở cổng 8000 (brief mục 2).")
BASE = f"http://127.0.0.1:{PORT}"
ADMIN_EMAIL = "qa-mock@example.test"
VIEWPORTS = {"1440": (1440, 900), "390": (390, 844)}
CRAWL_SCOPES = ("public", "admin")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s or "")).strip()


def fold(s: str) -> str:
    """So khớp không phân biệt hoa thường, giữ dấu tiếng Việt."""
    return norm(s).casefold()


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
