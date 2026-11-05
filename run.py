"""Chạy server: nâng cấp schema (alembic upgrade head) rồi bật uvicorn ở 127.0.0.1:$PORT."""
import logging
import os
import sys
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config

from app.config import ConfigError, config


def migrate() -> None:
    cfg = Config(str(Path(__file__).with_name("alembic.ini")))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")


def recover() -> None:
    """Một process: lúc khởi động không có chiến dịch nào thật sự đang gửi."""
    from app import queries
    from app.db import SessionLocal

    with SessionLocal() as db:
        queries.release_stuck_campaigns(db, stale_minutes=0)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        config.validate()
    except ConfigError as e:  # báo rõ cần đặt gì, không in traceback
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        print(f"{e}\nXem mục Biến môi trường trong README.md.", file=sys.stderr)
        sys.exit(2)
    migrate()
    recover()
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.environ.get("PORT", "8000")),
                proxy_headers=False, server_header=False)
