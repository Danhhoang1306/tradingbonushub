@echo off
rem Bat site that: nap .env, chay server o cong 8000 va Cloudflare Tunnel.
cd /d "%~dp0"
if not exist logs mkdir logs
for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"
start "TradingBonusHub" /min cmd /c ".venv\Scripts\python.exe run.py >> logs\app.log 2>&1"
start "Cloudflare Tunnel" /min cmd /c "cloudflared.exe tunnel --config cloudflared.yml run >> logs\tunnel.log 2>&1"
echo Da bat. Log: logs\app.log, logs\tunnel.log
