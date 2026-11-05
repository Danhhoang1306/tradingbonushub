"""Sao lưu database và ảnh upload khi site đang chạy; giữ 14 bản gần nhất.

Chạy tay: .venv/Scripts/python scripts/backup.py
Mặc định lưu vào thư mục <tên repo>_backups cạnh repo, đổi bằng biến BACKUP_DIR.
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DEST = Path(os.environ.get("BACKUP_DIR", ROOT.parent / f"{ROOT.name}_backups"))
KEEP = 14
PREFIX = "daily_"


def main() -> int:
    source = DATA / "app.db"
    if not source.exists():
        print(f"Không thấy {source}", file=sys.stderr)
        return 2
    final = DEST / f"{PREFIX}{datetime.now():%Y-%m-%d_%H%M%S}"
    work = final.with_name(final.name + ".tmp")
    work.mkdir(parents=True)
    copy = work / "app.db"

    # Backup API của SQLite cho bản sao nhất quán kể cả khi site đang ghi (WAL).
    src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    dst = sqlite3.connect(copy)
    try:
        src.backup(dst)
        result = dst.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        dst.close()
        src.close()
    if result != "ok":
        shutil.rmtree(work)
        print(f"Bản sao lỗi: {result}", file=sys.stderr)
        return 1

    uploads = DATA / "uploads"
    if uploads.exists():
        shutil.copytree(uploads, work / "uploads")
    work.rename(final)

    # Chỉ xóa bản hoàn chỉnh do script này tạo, không đụng bản sao lưu thủ công.
    done = sorted(p for p in DEST.glob(f"{PREFIX}*") if p.is_dir() and not p.name.endswith(".tmp"))
    for old in done[:-KEEP]:
        shutil.rmtree(old)
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} OK {final} (keep {min(len(done), KEEP)})")
    return 0


if __name__ == "__main__":
    sys.stdout = open(ROOT / "logs" / "backup.log", "a", encoding="utf-8") if sys.stdout is None else sys.stdout
    sys.stderr = sys.stdout if sys.stderr is None else sys.stderr
    sys.exit(main())
