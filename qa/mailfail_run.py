"""Như run.py nhưng giả lập SMTP hỏng: send_many trả 0 (giữ SMTP_BACKEND=console, không có kết nối mạng nào)."""
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import uvicorn  # noqa: E402

import run  # noqa: E402
from app import mailer  # noqa: E402
from app.routes import admin_people  # noqa: E402


def dead(messages):
    return 0


mailer.send_many = dead
admin_people.send_many = dead

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run.migrate()
    assert int(os.environ["PORT"]) != 8000
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.environ["PORT"]))
