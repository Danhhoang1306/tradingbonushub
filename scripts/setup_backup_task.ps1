# Register a Task Scheduler job to run backup_db.py daily at 2:00 AM.
# Run this script once only (with Administrator privileges).
#
# How to run:
#   Right-click → "Run as Administrator"
#   PowerShell: .\scripts\setup_backup_task.ps1

$TaskName   = "TradingBonusHub_BackupDB"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$PythonExe  = (Get-Command python).Source
$ScriptPath = Join-Path $ProjectDir "scripts\backup_db.py"
$LogPath    = Join-Path $ProjectDir "logs\backup.log"

# Remove existing task if it already exists
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$Action  = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "`"$ScriptPath`" >> `"$LogPath`" 2>&1" `
    -WorkingDirectory $ProjectDir

$Trigger = New-ScheduledTaskTrigger -Daily -At "02:00"

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action   $Action `
    -Trigger  $Trigger `
    -Settings $Settings `
    -RunLevel Highest `
    -Force

Write-Host ""
Write-Host "=== Task Scheduler has been registered ===" -ForegroundColor Green
Write-Host "  Task name : $TaskName"
Write-Host "  Runs at   : 2:00 AM daily"
Write-Host "  Log file  : $LogPath"
Write-Host ""
Write-Host "Verify in Task Scheduler > Task Scheduler Library > $TaskName"
Write-Host "Run manually now: python `"$ScriptPath`""
