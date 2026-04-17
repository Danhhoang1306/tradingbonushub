@echo off
setlocal

set PROJECT_DIR=%~dp0

echo.
echo ============================================================
echo   tradingbonushub.com -- Deploy nhanh (local)
echo ============================================================
echo.

:: Kill process cu tren port 8000
echo [1/2] Tat server cu...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul
echo       Done.

echo.
echo [2/2] Khoi dong server moi...
cd /d "%PROJECT_DIR%"
start /min "TradingBonusHub" python run.py

:: Doi app san sang
set /a RETRIES=0
:healthcheck_loop
if %RETRIES% GEQ 15 (
    echo [LOI] App khong san sang sau 30 giay.
    pause
    exit /b 1
)
curl -sf http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    set /a RETRIES+=1
    timeout /t 2 /nobreak >nul
    goto healthcheck_loop
)

echo.
echo ============================================================
echo   Deploy thanh cong!
echo ============================================================
echo   http://localhost:8000
echo.
pause
