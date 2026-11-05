"""Chạy app như run.py nhưng `today_vn()` đọc giờ từ file QA_NOW_FILE (ISO có múi giờ), đổi được khi server đang chạy.
Chỉ dùng để kiểm ranh giới ngày theo giờ Việt Nam. Không sửa code sản phẩm: vá `datetime` trong module lúc chạy."""
import datetime as dt
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import uvicorn  # noqa: E402

import run  # noqa: E402
from app import models, utils  # noqa: E402


class Fake(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        t = dt.datetime.fromisoformat(Path(os.environ["QA_NOW_FILE"]).read_text().strip())
        return t.astimezone(tz) if tz else t.replace(tzinfo=None)


utils.datetime = Fake
models.datetime = Fake  # utcnow(): phiên, hẹn giờ bài viết

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run.migrate()
    assert int(os.environ["PORT"]) != 8000
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.environ["PORT"]))
