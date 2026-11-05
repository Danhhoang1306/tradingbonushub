@echo off
rem Tat server cong 8000 va tunnel CUA DU AN NAY. Khong dung den tunnel du an khac tren may.
for /f "tokens=5" %%p in ('netstat -ano ^| findstr "127.0.0.1:8000" ^| findstr LISTENING') do taskkill /PID %%p /F
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"name='cloudflared.exe'\" | Where-Object { $_.CommandLine -like '*--config cloudflared.yml*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
