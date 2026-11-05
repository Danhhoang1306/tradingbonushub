"""Như run.py nhưng giả lập SMTP hỏng (giữ SMTP_BACKEND=console, không có kết nối mạng).
QA_MAIL_OK_BATCHES=N: N lần gọi send_many đầu thành công, sau đó trả 0. QA_MAIL_REJECT=địa chỉ: địa chỉ đó luôn bị từ chối.
File QA_MAIL_FLAG tồn tại thì hết hỏng (dùng để thử gửi tiếp chiến dịch mà không restart)."""
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

real = mailer.send_many
calls = [0]
OK = int(os.environ.get("QA_MAIL_OK_BATCHES", "0"))
REJECT = os.environ.get("QA_MAIL_REJECT", "")
FLAG = os.environ.get("QA_MAIL_FLAG", "")


def flaky(messages):
    calls[0] += 1
    if FLAG and Path(FLAG).exists():
        return real(messages)
    if REJECT:
        return real([m for m in messages if m["To"] != REJECT])
    return real(messages) if calls[0] <= OK else 0


mailer.send_many = flaky
admin_people.send_many = flaky

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run.migrate()
    run.recover()
    assert int(os.environ["PORT"]) != 8000
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.environ["PORT"]))
