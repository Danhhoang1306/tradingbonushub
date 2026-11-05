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

| Biến | Ý nghĩa | Production | Dev/test |
|---|---|---|---|
| `APP_ENV` | `production`, `development` hoặc `test`. Giá trị khác: server từ chối chạy | mặc định | phải đặt rõ |
| `SECRET_KEY` | Khóa ký token phiên, tối thiểu 32 ký tự | bắt buộc | ngẫu nhiên mỗi lần chạy |
| `BASE_URL` | Gốc URL công khai, dùng trong email, sitemap, canonical | bắt buộc, nên là https | `http://127.0.0.1:$PORT` |
| `SMTP_BACKEND` | `smtp` gửi thật, `console` chỉ ghi log | bắt buộc đặt rõ | `console` |
| `SMTP_HOST`, `FROM_EMAIL` | Máy chủ gửi và địa chỉ gửi | bắt buộc khi `smtp` | bắt buộc khi `smtp` |
| `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` | Cổng 465 = SSL, khác = STARTTLS (mặc định 587) | tùy chọn | tùy chọn |
| `DATABASE_URL` | URL SQLAlchemy | `sqlite:///data/app.db` | như production |
| `UPLOAD_DIR` | Thư mục ảnh upload, phục vụ ở `/media/` | `data/uploads` | như production |
| `PORT` | Cổng (luôn bind 127.0.0.1) | `8000` | `8000` |
| `ADMIN_PASSWORD` | Chỉ cho `create-admin` khi chạy không tương tác | | |

Thiếu cấu hình bắt buộc thì `run.py` in danh sách cần đặt và thoát mã 2. `SMTP_BACKEND=console` ở production được phép
nhưng log cảnh báo khi khởi động: email không được gửi thật.

## Chạy

Trên máy cá nhân (dev):

```powershell
$env:APP_ENV = "development"; $env:PORT = "8010"
.venv\Scripts\python run.py          # tự chạy `alembic upgrade head` rồi bật server
```

Production:

```powershell
$env:SECRET_KEY = "<chuỗi ngẫu nhiên, tối thiểu 32 ký tự>"
$env:BASE_URL = "https://ten-mien-cua-ban"
$env:SMTP_BACKEND = "smtp"; $env:SMTP_HOST = "<máy chủ SMTP>"; $env:FROM_EMAIL = "<địa chỉ gửi>"
.venv\Scripts\python run.py
```

Tạo tài khoản quản trị (không có tài khoản mặc định; mật khẩu nhập qua prompt, tối thiểu 10 ký tự):

```powershell
.venv\Scripts\python -m app.cli create-admin --email ban@example.com
.venv\Scripts\python -m app.cli create-admin --email bientap@example.com --role editor
```

Chạy lại lệnh với email đã có = đặt lại mật khẩu, vai trò giữ nguyên trừ khi truyền `--role`. Đăng nhập tại `/admin/login`.

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

## Sao lưu và phục hồi

Dữ liệu gồm database và thư mục ảnh. Đừng copy file `.db` khi server đang chạy: có thể thiếu dữ liệu nằm trong file `-wal`.

Sao lưu khi server đang chạy (dùng cơ chế backup của SQLite, an toàn dưới tải):

```powershell
.venv\Scripts\python -c "import sqlite3; s=sqlite3.connect('data/app.db'); d=sqlite3.connect('backup.db'); s.backup(d); d.close(); s.close()"
Copy-Item -Recurse data\uploads backup-uploads
```

Hoặc dừng server rồi copy `data\app.db*` và `data\uploads\`.

Phục hồi:

1. Dừng server.
2. Xóa `data\app.db`, `data\app.db-wal`, `data\app.db-shm`.
3. Copy `backup.db` thành `data\app.db`, copy `backup-uploads` thành `data\uploads`.
4. Chạy `run.py` (tự nâng schema nếu bản sao lưu cũ hơn code). Phiên đăng nhập cũ vẫn dùng được nếu `SECRET_KEY` không đổi.
