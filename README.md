# TradingBonusHub

Admin panel cho chương trình trading bonus / rebate / email campaign.
FastAPI + Jinja2 + SQL Server, deploy local qua Cloudflare Tunnel.

---

## Stack

- **App**: FastAPI 0.115 (Python 3.12), Jinja2 templates, single uvicorn worker
- **DB**: SQL Server (ODBC Driver 17), connection pool (20 conn mặc định)
- **Auth**: Argon2id password hashing, CSRF per-session, DB-backed sessions
- **Deploy**: Docker Compose + Cloudflare Tunnel (`cloudflared.exe`)
- **Scheduler**: Windows Task Scheduler cho backup DB hàng ngày

---

## Lần đầu setup

1. Copy `.env.example` → `.env`, điền:
   - `SECRET_KEY` → `python -c "import secrets; print(secrets.token_hex(32))"`
   - `FERNET_KEY` → `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   - `DB_USER` / `DB_PASSWORD` (tạo service account riêng, không dùng `sa`)
   - SMTP / Telegram / Google OAuth nếu dùng
2. Tạo SQL Server login:
   ```sql
   CREATE LOGIN app_user WITH PASSWORD='<strong-password>';
   USE TradingBonusHub;
   CREATE USER app_user FOR LOGIN app_user;
   GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dbo TO app_user;
   ```
3. Cloudflare Tunnel (nếu cần public): `scripts/setup-cloudflare.ps1` (Run as Admin)
4. Đăng ký backup task: `scripts/setup_backup_task.ps1` (Run as Admin) → chạy `backup_db.py` mỗi 2h sáng, giữ 7 bản gần nhất

---

## Hàng ngày

| Lệnh | Tác dụng |
|------|----------|
| `start.bat` | Docker up + Cloudflare Tunnel + chờ `/health` OK |
| `stop.bat` | Tắt Tunnel + Docker |
| `deploy.bat` | Chạy local không qua Docker (port 8000 trực tiếp) |
| `docker compose -f docker-compose.prod.yml logs -f` | Xem log realtime |

Truy cập: `https://tradingbonushub.com` / `portal.` / `admin.`

---

## Backup & Restore

Backup chạy tự động mỗi 2h sáng (Task Scheduler). File lưu tại [data/backups/](data/backups/).

**Backup thủ công:**
```bash
python scripts/backup_db.py
```

**Restore (sẽ ghi đè DB hiện tại — tắt app trước):**
```bash
stop.bat
python scripts/restore_db.py                    # bản mới nhất
python scripts/restore_db.py TradingBonusHub_20260419_020000.bak  # chọn file
start.bat
```

---

## Cấu trúc

```
app/
  main.py              # FastAPI entry, startup (init_db + init_pool)
  config.py            # Env vars, logging (structlog + rotating)
  api/                 # Health, webhooks
  routes/              # Admin + portal views
  db/
    connection.py      # pyodbc pool (20 conn, 60s startup wait, broken-conn replacement)
    init.py            # Schema bootstrap (29 tables)
    repositories/      # Parameterized queries
  services/
    auth.py            # Argon2id + PBKDF2 legacy migration
  middleware/
    auth.py, csrf.py, security.py, db_session.py
email_templates/       # HTML cho mail campaign (signature, promo, ...)
static/                # CSS, JS, uploads (gitignored)
scripts/
  backup_db.py         # Native SQL Server BACKUP, giữ 7 bản
  restore_db.py        # RESTORE WITH REPLACE, có confirm prompt
  setup_backup_task.ps1  # Register Task Scheduler
  setup-cloudflare.ps1   # Cài Tunnel
templates/             # Jinja2 admin/portal
tests/                 # pytest stubs (chưa đầy đủ coverage)
data/backups/          # .bak files (gitignored)
logs/                  # Rotating 10MB × 5 (gitignored)
```

---

## Khi có sự cố

| Triệu chứng | Kiểm tra |
|-------------|----------|
| `/health` trả 503 | DB down — check SQL Server service, check `.env` creds |
| App không start sau reboot | Pool đợi SQL Server 60s (xem `app/db/connection.py:init_pool`) — nếu vẫn fail, start SQL Server thủ công rồi restart app |
| Connection pool exhausted | Tăng `DB_POOL_SIZE` trong `.env` |
| Session bị logout liên tục | Kiểm tra `SECRET_KEY` có đổi không; idle timeout = 30' |
| Tunnel không connect | `cloudflared.yml` credentials, re-run `scripts/setup-cloudflare.ps1` |

Logs: [logs/](logs/) (JSON, rotate 10MB × 5 files).

---

## Rotate secrets

Nếu `.env` lộ (share máy, commit nhầm ...):
1. Sinh `SECRET_KEY` / `FERNET_KEY` mới (xem phần setup).
2. Đổi `DB_PASSWORD` trong SQL Server: `ALTER LOGIN app_user WITH PASSWORD='<new>';`
3. Revoke Google OAuth client, tạo mới trong Google Cloud Console.
4. Đổi `TELEGRAM_BOT_TOKEN` qua `@BotFather` → `/revoke`.
5. Restart app: `stop.bat && start.bat`.

**Lưu ý**: `FERNET_KEY` đổi → dữ liệu mã hóa cũ (API keys brokers, ...) không decrypt được. Chỉ rotate nếu chắc chắn chưa có dữ liệu encrypted, hoặc có plan re-encrypt.
