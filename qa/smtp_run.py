"""Như run.py cho production + smtp, chỉ thêm tin chứng chỉ tự ký của bộ nhận local (qa/fake_smtp.py).
Vẫn kiểm chứng chỉ và tên máy. Không có kết nối nào ra ngoài localhost."""
import logging
import os
import ssl
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import uvicorn  # noqa: E402

import run  # noqa: E402
from app import mailer  # noqa: E402

assert os.environ["SMTP_HOST"] == "localhost", "Chỉ dùng với bộ nhận local"
mailer.ssl = SimpleNamespace(create_default_context=lambda: ssl.create_default_context(cafile=os.environ["QA_SMTP_CA"]))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run.migrate()
    run.recover()
    assert int(os.environ["PORT"]) != 8000
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.environ["PORT"]))
