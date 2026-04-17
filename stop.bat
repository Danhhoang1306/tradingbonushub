@echo off
set PROJECT_DIR=%~dp0

echo.
echo [1/2] Dang tat Cloudflare Tunnel...
taskkill /f /im cloudflared.exe >nul 2>&1
echo       Done.

echo.
echo [2/2] Dang tat Docker containers...
docker compose -f "%PROJECT_DIR%docker-compose.prod.yml" down
echo       Done.

echo.
echo He thong da tat.
pause
