"""Cấu hình đọc từ biến môi trường (không tự đọc file .env)."""
import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit

BASE_DIR = Path(__file__).resolve().parent.parent
APP_ENVS = ("production", "development", "test")
SMTP_BACKENDS = ("smtp", "console")
MIN_SECRET_LENGTH = 32


class ConfigError(RuntimeError):
    pass


class Config:
    def __init__(self) -> None:
        env = os.environ.get
        # Mặc định production (an toàn khi lên tunnel). Chạy local phải đặt APP_ENV=development.
        self.app_env = env("APP_ENV", "production").strip().lower()
        # Giá trị lạ được coi là production để luôn an toàn; validate() sẽ từ chối chạy.
        self.is_production = self.app_env not in ("development", "test")
        # Production thiếu SECRET_KEY: server từ chối khởi động, còn alembic/CLI vẫn chạy được.
        self.secret_key = env("SECRET_KEY", "") or ("" if self.is_production else secrets.token_hex(32))
        self.database_url = env("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'data' / 'app.db').as_posix()}")
        self.port = int(env("PORT", "8000"))
        self.base_url_set = bool(env("BASE_URL", "").strip())
        self.base_url = env("BASE_URL", f"http://127.0.0.1:{self.port}").strip().rstrip("/")
        self.upload_dir = Path(env("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads")))
        self.smtp_backend = env("SMTP_BACKEND", "").strip().lower() or ("" if self.is_production else "console")
        self.smtp_host = env("SMTP_HOST", "")
        self.smtp_port = int(env("SMTP_PORT", "587"))
        self.smtp_user = env("SMTP_USER", "")
        self.smtp_pass = env("SMTP_PASS", "")
        self.from_email = env("FROM_EMAIL", "")
        self.templates_dir = BASE_DIR / "templates"
        self.static_dir = BASE_DIR / "static"

    def problems(self) -> list[str]:
        """Lỗi cấu hình khiến server không được phép chạy."""
        out = []
        if self.app_env not in APP_ENVS:
            out.append(f"APP_ENV={self.app_env!r} không hợp lệ, chỉ nhận: {', '.join(APP_ENVS)}.")
        if self.smtp_backend and self.smtp_backend not in SMTP_BACKENDS:
            out.append(f"SMTP_BACKEND={self.smtp_backend!r} không hợp lệ, chỉ nhận: {', '.join(SMTP_BACKENDS)}.")
        if self.smtp_backend == "smtp":
            if not self.smtp_host:
                out.append("Thiếu SMTP_HOST khi SMTP_BACKEND=smtp.")
            if not self.from_email:
                out.append("Thiếu FROM_EMAIL khi SMTP_BACKEND=smtp.")
        if self.is_production:
            if not self.secret_key:
                out.append("Thiếu SECRET_KEY.")
            elif len(self.secret_key) < MIN_SECRET_LENGTH:
                out.append(f"SECRET_KEY quá ngắn, cần tối thiểu {MIN_SECRET_LENGTH} ký tự.")
            if not self.base_url_set:
                out.append("Thiếu BASE_URL (dùng trong email, sitemap, canonical), ví dụ https://ten-mien-cua-ban.")
            else:
                parts = urlsplit(self.base_url)
                if parts.scheme not in ("http", "https") or not parts.netloc:
                    out.append(f"BASE_URL={self.base_url!r} không phải URL http(s) hợp lệ.")
            if not self.smtp_backend:
                out.append("Thiếu SMTP_BACKEND: đặt smtp để gửi email thật, hoặc console nếu chủ động không gửi.")
        return out

    def warnings(self) -> list[str]:
        """Cấu hình chạy được nhưng cần chủ site biết."""
        out = []
        if self.is_production and self.smtp_backend == "console":
            out.append("SMTP_BACKEND=console ở production: email KHÔNG được gửi, chỉ ghi log.")
        if self.is_production and self.base_url_set and not self.base_url.startswith("https://"):
            out.append(f"BASE_URL={self.base_url} không dùng https ở production.")
        return out

    def validate(self) -> None:
        problems = self.problems()
        if problems:
            raise ConfigError("Cấu hình không hợp lệ:\n- " + "\n- ".join(problems))

    def require_secret(self) -> None:
        if not self.secret_key:
            raise ConfigError("Thiếu SECRET_KEY khi APP_ENV=production")


config = Config()
