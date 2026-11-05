@echo off
rem Bat site that: nap .env, chay server cong 8000 va Cloudflare Tunnel. Chay lai khi dang bat thi bo qua.
cd /d "%~dp0"
if not exist logs mkdir logs
for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"
netstat -ano | findstr "127.0.0.1:8000" | findstr LISTENING >nul
if errorlevel 1 (
  start "TradingBonusHub" /min cmd /c ".venv\Scripts\python.exe run.py >> logs\app.log 2>&1"
) else (
  echo Server da chay.
)
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"name='cloudflared.exe'\" | Where-Object { $_.CommandLine -like '*--config cloudflared.yml*' }) { exit 0 } else { exit 1 }"
if errorlevel 1 (
  start "Cloudflare Tunnel" /min cmd /c "cloudflared.exe tunnel --config cloudflared.yml run >> logs\tunnel.log 2>&1"
) else (
  echo Tunnel da chay.
)
echo Log: logs\app.log, logs\tunnel.log
