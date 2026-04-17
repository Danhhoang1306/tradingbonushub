# =============================================================================
# setup-autostart.ps1
# Register Task Scheduler to auto-start tradingbonushub on Windows boot
# Run once with Administrator privileges
# =============================================================================

$TaskName   = "TradingBonusHub_Autostart"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$StartBat   = Join-Path $ProjectDir "start.bat"

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$Action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$StartBat`"" `
    -WorkingDirectory $ProjectDir

# Run 2 minutes after Windows boot (wait for Docker Desktop to start)
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Trigger.Delay = "PT2M"

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 2)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action   $Action `
    -Trigger  $Trigger `
    -Settings $Settings `
    -RunLevel Highest `
    -Force

Write-Host ""
Write-Host "=== Task Scheduler has been registered ===" -ForegroundColor Green
Write-Host "  Task name  : $TaskName"
Write-Host "  Runs when  : Windows startup (after 2 minutes)"
Write-Host "  Script     : $StartBat"
Write-Host ""
Write-Host "Verify: Task Scheduler > Task Scheduler Library > $TaskName"
