@echo off
setlocal

:: Yeu cau quyen Admin
net session >nul 2>&1
if errorlevel 1 (
    echo [*] Dang yeu cau quyen Admin...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

set PROJECT_DIR=%~dp0
set CLOUDFLARED=%PROJECT_DIR%cloudflared.exe
set COMPOSE_FILE=%PROJECT_DIR%docker-compose.prod.yml
set ENV_FILE=%PROJECT_DIR%.env

echo.
echo ============================================================
echo   tradingbonushub.com -- Khoi dong he thong
echo ============================================================
echo.

:: Kiem tra .env
if not exist "%ENV_FILE%" (
    echo [LOI] Chua co file .env
    echo       Chay scripts\setup-cloudflare.ps1 truoc.
    pause
    exit /b 1
)

:: Kiem tra cloudflared.exe
if not exist "%CLOUDFLARED%" (
    echo [LOI] Chua co cloudflared.exe
    echo       Chay scripts\setup-cloudflare.ps1 truoc.
    pause
    exit /b 1
)

:: Kiem tra Docker Desktop dang chay
docker info >nul 2>&1
if errorlevel 1 (
    echo [LOI] Docker Desktop chua chay. Hay mo Docker Desktop roi thu lai.
    pause
    exit /b 1
)

:: Kill sach toan bo cloudflared cu
echo [0/3] Dang kill cloudflared cu (neu co)...
powershell -Command "Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force"
timeout /t 2 /nobreak >nul
echo       Done.

echo.
echo [1/3] Dang khoi dong Docker containers...
docker compose -f "%COMPOSE_FILE%" --env-file "%ENV_FILE%" up -d --build
if errorlevel 1 (
    echo [LOI] Docker compose that bai. Kiem tra logs:
    echo       docker compose -f docker-compose.prod.yml logs
    pause
    exit /b 1
)
echo       Docker containers da chay.

echo.
echo [2/3] Doi app san sang...
set /a RETRIES=0
:healthcheck_loop
if %RETRIES% GEQ 30 (
    echo [LOI] App khong san sang sau 60 giay. Kiem tra logs:
    echo       docker compose -f docker-compose.prod.yml logs
    pause
    exit /b 1
)
curl -sf http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    set /a RETRIES+=1
    timeout /t 2 /nobreak >nul
    goto healthcheck_loop
)
echo       App da san sang!

echo.
echo [3/3] Dang khoi dong Cloudflare Tunnel...
powershell -Command "Start-Process -FilePath '%CLOUDFLARED%' -ArgumentList 'tunnel','--config','%PROJECT_DIR%cloudflared.yml','run' -WindowStyle Minimized"
timeout /t 3 /nobreak >nul
powershell -Command "if ((Get-Process cloudflared -ErrorAction SilentlyContinue).Count -ge 1) { Write-Host '      Tunnel da ket noi.' } else { Write-Host '[LOI] Tunnel khong khoi dong duoc!' }"

echo.
echo ============================================================
echo   He thong da san sang!
echo ============================================================
echo.
echo   Website  : https://tradingbonushub.com
echo   Portal   : https://portal.tradingbonushub.com
echo   Admin    : https://admin.tradingbonushub.com
echo.
echo   Lenh quan ly:
echo     Xem logs    : docker compose -f docker-compose.prod.yml logs -f
echo     Tat he thong: stop.bat
echo.
pause
