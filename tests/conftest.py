"""Test chạy trên DB SQLite tạm + thư mục upload tạm. Không đụng data/app.db, không gửi email thật."""
import os
import shutil
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="tbh-test-"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{(_TMP / 'test.db').as_posix()}",
    "UPLOAD_DIR": str(_TMP / "uploads"),
    "APP_ENV": "test",
    "SECRET_KEY": "test-secret-key",
    "SMTP_BACKEND": "console",
    "BASE_URL": "http://testserver",
})

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import mailer  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import AdminUser, Bonus, Broker  # noqa: E402
from app.security import ad_view_limiter, hash_password, login_limiter, public_form_limiter  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PASSWORD = "mat-khau-test-123"


def pytest_sessionstart(session):
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")  # kiểm tra luôn migration


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture(autouse=True)
def clean_state():
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    login_limiter.reset()
    public_form_limiter.reset()
    ad_view_limiter.reset()
    mailer.outbox.clear()
    upload_dir = Path(os.environ["UPLOAD_DIR"])
    if upload_dir.exists():
        for f in upload_dir.iterdir():
            f.unlink()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def make_user(db, email="admin@example.test", role="admin") -> AdminUser:
    u = AdminUser(email=email, password_hash=hash_password(PASSWORD), role=role)
    db.add(u)
    db.commit()
    return u


def titles(items, key="title") -> list[str]:
    return [x[key] for x in items]


def errors_of(r) -> dict:
    """Lỗi validate trong context (drawer admin, form tab admin, form liên hệ, thư viện ảnh)."""
    c = r.context
    if c.get("drawer"):
        return c["drawer"]["errors"]
    if isinstance(c.get("form"), dict):
        return c["form"]["errors"]
    return c.get("errors") or c.get("mail_form", {}).get("errors", {})


def flash_code(r):
    return (r.context.get("flash") or {}).get("code")


def login(client, email="admin@example.test", password=PASSWORD, next_path="/admin"):
    token = client.get("/admin/login").context["csrf_token"]
    return client.post("/admin/login", data={"email": email, "password": password, "csrf_token": token,
                                             "next": next_path}, follow_redirects=False)


class AdminClient:
    """TestClient đã đăng nhập; post() tự gắn csrf_token."""

    def __init__(self, client):
        self.c = client
        self.csrf = client.get("/admin").context["csrf_token"]

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def post(self, url, data=None, files=None, **kw):
        payload = {"csrf_token": self.csrf, **(data or {})}
        return self.c.post(url, data=payload, files=files, follow_redirects=False, **kw)


@pytest.fixture
def admin(client, db):
    make_user(db)
    assert login(client).status_code == 303
    return AdminClient(client)


def make_broker(db, name="Sàn A", **kw) -> Broker:
    from app.utils import slugify
    defaults = dict(slug=slugify(name), name=name, mono=name[:2].upper(), kind="forex",
                    affiliate_url="https://example.com/aff", is_active=True)
    k = Broker(**(defaults | kw))
    db.add(k)
    db.commit()
    return k


def make_bonus(db, broker, title="Thưởng nạp 50%", **kw) -> Bonus:
    b = Bonus(**(dict(broker_id=broker.id, type="deposit", title=title, amount="50%", is_active=True) | kw))
    db.add(b)
    db.commit()
    return b
