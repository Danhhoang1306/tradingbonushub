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
$env:APP_ENV = "production"   # đặt rõ: cửa sổ vừa chạy dev còn giữ APP_ENV=development
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

## Chạy thật qua Cloudflare Tunnel

`start.bat` nạp `.env`, chạy server ở cổng 8000 và tunnel; `stop.bat` tắt cả hai (không đụng tunnel dự án khác). Log ở `logs/`.
Site tắt khi tắt máy hoặc khi đóng các cửa sổ đó.

`.env` đang dùng `SMTP_BACKEND=console`: email chỉ ghi log. Khi có SMTP, đặt `SMTP_BACKEND=smtp` + `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `FROM_EMAIL`, rồi bật lại section "Form đăng ký" ở Trang chủ.

## Tự chạy và sao lưu hằng ngày

Chạy một lần trong PowerShell: `powershell -ExecutionPolicy Bypass -File scripts\setup_autostart.ps1`. Site tự bật khi đăng nhập Windows; sao lưu lúc 03:17 vào `..\Tradingbonushub_backups`, giữ 14 bản. Gỡ bằng `scriptsemove_autostart.ps1`. Sao lưu tay: `.venv\Scripts\python scriptsackup.py`.

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
Remove-Item -Recurse -Force backup-uploads -ErrorAction SilentlyContinue
Copy-Item -Recurse data\uploads backup-uploads
```

Hoặc dừng server rồi copy `data\app.db*` và `data\uploads\`.

Phục hồi (chạy tại thư mục dự án, sau khi đã dừng server):

```powershell
Remove-Item data\app.db, data\app.db-wal, data\app.db-shm -ErrorAction SilentlyContinue
Copy-Item backup.db data\app.db
Remove-Item -Recurse -Force data\uploads -ErrorAction SilentlyContinue
Copy-Item -Recurse backup-uploads data\uploads
.venv\Scripts\python run.py
```

`run.py` tự nâng schema nếu bản sao lưu cũ hơn code. Phiên đăng nhập cũ vẫn dùng được nếu `SECRET_KEY` không đổi.
