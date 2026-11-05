# Go bo nhung gi setup_autostart.ps1 da cai. Khong xoa cac ban sao luu.
Remove-Item "$([Environment]::GetFolderPath('Startup'))\TradingBonusHub.cmd" -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName 'TradingBonusHub_Backup' -Confirm:$false -ErrorAction SilentlyContinue
Write-Host 'Da go.'
