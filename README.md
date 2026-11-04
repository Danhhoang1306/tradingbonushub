# TradingBonusHub v2

Site so sánh bonus sàn forex/crypto + trang quản trị. FastAPI + Jinja2 (server render), SQLAlchemy 2, SQLite (WAL), Alembic.
Database bắt đầu rỗng; mọi dữ liệu (bonus, sàn, bài viết, banner, chữ trên trang) do admin nhập.

## Cài đặt (Windows, Python 3.12)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt       # chạy site
.venv\Scripts\pip install -r requirements-dev.txt   # thêm pytest, httpx, playwright
```

## Biến môi trường

App chỉ đọc biến môi trường (không tự đọc `.env`). Danh sách tên biến ở `.env.example`.

| Biến | Ý nghĩa | Mặc định |
|---|---|---|
| `SECRET_KEY` | Khóa ký token phiên. Bắt buộc khi `APP_ENV=production` | ngẫu nhiên mỗi lần chạy (dev) |
| `APP_ENV` | `production` bật cookie Secure, HSTS, tắt `/docs` | `development` |
| `DATABASE_URL` | URL SQLAlchemy | `sqlite:///data/app.db` |
| `PORT` | Cổng (luôn bind 127.0.0.1) | `8000` |
| `BASE_URL` | Gốc URL công khai, dùng trong email, sitemap, canonical | `http://127.0.0.1:8000` |
| `UPLOAD_DIR` | Thư mục ảnh upload, phục vụ ở `/media/` | `data/uploads` |
| `SMTP_BACKEND` | `smtp` gửi thật, `console` chỉ ghi log | `console` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `FROM_EMAIL` | Cấu hình SMTP (cổng 465 = SSL, khác = STARTTLS) | |

## Chạy

```powershell
$env:PORT = "8010"; $env:SECRET_KEY = "<chuỗi ngẫu nhiên dài>"
.venv\Scripts\python run.py          # tự chạy `alembic upgrade head` rồi bật server
```

Tạo tài khoản quản trị (không có tài khoản mặc định; mật khẩu nhập qua prompt, tối thiểu 10 ký tự):

```powershell
.venv\Scripts\python -m app.cli create-admin --email ban@example.com
.venv\Scripts\python -m app.cli create-admin --email bientap@example.com --role editor
```

Chạy lại lệnh với email đã có = đặt lại mật khẩu. Đăng nhập tại `/admin/login`.

Không tương tác (script, CI, terminal không có console): đặt biến `ADMIN_PASSWORD` trước khi chạy lệnh. Không có tham số
dòng lệnh cho mật khẩu.

## Test

```powershell
.venv\Scripts\python -m pytest
```

Test dùng DB và thư mục upload tạm, `SMTP_BACKEND=console`; không đụng `data/app.db`.

## Cấu trúc

- `app/` backend: `models.py` (bảng), `content.py` (nội dung trang + giá trị mặc định), `routes/public.py`,
  `routes/admin*.py`, `security.py`, `uploads.py`, `mailer.py`, `templating.py` (filter Jinja).
- `alembic/` migration. Thêm cột/bảng: sửa `models.py` rồi `alembic revision --autogenerate -m "..."`.
- `templates/public`, `templates/admin`, `static/` giao diện. Hợp đồng dữ liệu cho template: `docs/VIEW_CONTEXT.md`.

## Ghi chú vận hành

- Site chạy sau Cloudflare Tunnel: IP thật lấy từ `CF-Connecting-IP` khi request đến từ 127.0.0.1.
- Rate limit (đăng nhập, đăng ký, liên hệ) lưu trong bộ nhớ: chỉ chạy một process uvicorn.
- Sao lưu: copy `data/app.db*` và `data/uploads/`.
