"""Application configuration and constants."""
import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import structlog
from dotenv import load_dotenv

# ── Load .env before anything else ────────────────────────────────────────────
load_dotenv()

# ── UTF-8 on Windows ──────────────────────────────────────────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── App constants ─────────────────────────────────────────────────────────────
SECRET_KEY      = os.environ["SECRET_KEY"]
FERNET_KEY      = os.environ["FERNET_KEY"]
APP_ENV         = os.environ.get("APP_ENV", "production")
APP_VERSION     = "2.0.0"
APP_START_TIME  = datetime.now(timezone.utc)
SESSION_MAX_AGE = 86400  # 24 hours

# ── 1×1 transparent GIF ──────────────────────────────────────────────────────
PIXEL_GIF = bytes([
    0x47, 0x49, 0x46, 0x38, 0x39, 0x61, 0x01, 0x00, 0x01, 0x00,
    0x80, 0x00, 0x00, 0xff, 0xff, 0xff, 0x00, 0x00, 0x00, 0x21,
    0xf9, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x2c, 0x00, 0x00,
    0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0x02, 0x02, 0x44,
    0x01, 0x00, 0x3b,
])

# ── Rate limiter (slowapi) ────────────────────────────────────────────────────
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],         # global fallback for all routes
    application_limits=["200/minute"],    # absolute ceiling per IP
)


# ── Structured logging ────────────────────────────────────────────────────────

def configure_logging() -> None:
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if APP_ENV == "production":
        # Ensure logs directory exists
        Path("logs").mkdir(exist_ok=True)

        # Root stdlib logger
        root = logging.getLogger()
        root.setLevel(logging.INFO)

        # File handler — JSON lines, rotating 10 MB × 5 backups
        file_handler = logging.handlers.RotatingFileHandler(
            "logs/app.jsonl",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_fmt = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
        file_handler.setFormatter(file_fmt)
        root.addHandler(file_handler)

        # Console handler — human-readable
        console_handler = logging.StreamHandler()
        console_fmt = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(),
            foreign_pre_chain=shared_processors,
        )
        console_handler.setFormatter(console_fmt)
        root.addHandler(console_handler)

        structlog.configure(
            processors=shared_processors + [
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

    else:
        # Dev: console only, human-readable
        structlog.configure(
            processors=shared_processors + [
                structlog.dev.ConsoleRenderer(),
            ],
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
