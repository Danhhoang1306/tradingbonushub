# Cai 2 viec cho may nay (tu chay mot lan, khong can quyen Admin):
#  1. Tu bat site khi dang nhap Windows (file trong thu muc Startup).
#  2. Sao luu database va anh luc 03:17 hang ngay; may tat thi chay bu khi bat lai.
# Go bo: scripts\remove_autostart.ps1
$root = Split-Path -Parent $PSScriptRoot
$startup = [Environment]::GetFolderPath('Startup')
Set-Content -Path "$startup\TradingBonusHub.cmd" -Encoding ascii -Value "@echo off`r`ncall `"$root\start.bat`""

$action = New-ScheduledTaskAction -Execute "$root\.venv\Scripts\pythonw.exe" -Argument 'scripts\backup.py' -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At 3:17am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName 'TradingBonusHub_Backup' -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Start-ScheduledTask -TaskName 'TradingBonusHub_Backup'
Start-Sleep 6
$info = Get-ScheduledTaskInfo -TaskName 'TradingBonusHub_Backup'
Write-Host "Da cai. Backup thu: ma ket qua $($info.LastTaskResult) (0 la OK), lan sau: $($info.NextRunTime)"
