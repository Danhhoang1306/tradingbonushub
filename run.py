"""Chạy server: nâng cấp schema (alembic upgrade head) rồi bật uvicorn ở 127.0.0.1:$PORT."""
import logging
import os
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config


def migrate() -> None:
    cfg = Config(str(Path(__file__).with_name("alembic.ini")))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    migrate()
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.environ.get("PORT", "8000")),
                proxy_headers=False, server_header=False)
