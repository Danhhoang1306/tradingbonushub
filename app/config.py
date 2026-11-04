"""Cấu hình đọc từ biến môi trường (không tự đọc file .env)."""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    def __init__(self) -> None:
        env = os.environ.get
        # Mặc định production (an toàn khi lên tunnel). Chạy local phải đặt APP_ENV=development.
        self.app_env = env("APP_ENV", "production").strip().lower()
        self.is_production = self.app_env == "production"
        # Production thiếu SECRET_KEY: server từ chối khởi động (require_secret), còn alembic/CLI vẫn chạy được.
        self.secret_key = env("SECRET_KEY", "") or ("" if self.is_production else secrets.token_hex(32))
        self.database_url = env("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'data' / 'app.db').as_posix()}")
        self.port = int(env("PORT", "8000"))
        self.base_url = env("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        self.upload_dir = Path(env("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads")))
        self.smtp_backend = env("SMTP_BACKEND", "console").strip().lower()
        self.smtp_host = env("SMTP_HOST", "")
        self.smtp_port = int(env("SMTP_PORT", "587"))
        self.smtp_user = env("SMTP_USER", "")
        self.smtp_pass = env("SMTP_PASS", "")
        self.from_email = env("FROM_EMAIL", "")
        self.templates_dir = BASE_DIR / "templates"
        self.static_dir = BASE_DIR / "static"

    def require_secret(self) -> None:
        if not self.secret_key:
            raise RuntimeError("Thiếu SECRET_KEY khi APP_ENV=production")


config = Config()
