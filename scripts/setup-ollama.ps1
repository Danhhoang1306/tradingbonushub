# ============================================================
#  Setup Ollama for AI Translation
#  Run this once on the Windows host
# ============================================================

Write-Host ""
Write-Host "============================================"
Write-Host "  Ollama Setup for TradingBonusHub"
Write-Host "============================================"
Write-Host ""

# Check if Ollama is installed
$ollamaPath = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaPath) {
    Write-Host "[!] Ollama is not installed." -ForegroundColor Red
    Write-Host "    Download from: https://ollama.com/download"
    Write-Host ""
    pause
    exit 1
}

Write-Host "[OK] Ollama found: $($ollamaPath.Source)" -ForegroundColor Green

# Set OLLAMA_KEEP_ALIVE to 15 minutes (auto-unload model from RAM)
$current = [System.Environment]::GetEnvironmentVariable("OLLAMA_KEEP_ALIVE", "User")
if ($current -ne "15m") {
    [System.Environment]::SetEnvironmentVariable("OLLAMA_KEEP_ALIVE", "15m", "User")
    Write-Host "[OK] Set OLLAMA_KEEP_ALIVE=15m (model auto-unloads after 15 min idle)" -ForegroundColor Green
} else {
    Write-Host "[OK] OLLAMA_KEEP_ALIVE already set to 15m" -ForegroundColor Green
}

# Pull the translation model
Write-Host ""
Write-Host "[..] Pulling qwen2.5:7b model (this may take a while)..." -ForegroundColor Yellow
ollama pull qwen2.5:7b

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[OK] Model qwen2.5:7b ready!" -ForegroundColor Green
} else {
    Write-Host "[!] Failed to pull model" -ForegroundColor Red
}

Write-Host ""
Write-Host "============================================"
Write-Host "  Setup Complete!"
Write-Host "============================================"
Write-Host ""
Write-Host "  Usage:"
Write-Host "    1. Start Ollama:  ollama serve"
Write-Host "    2. Go to Admin -> Articles -> Edit"
Write-Host "    3. Click 'Translate with AI' button"
Write-Host ""
Write-Host "  Model auto-unloads from RAM after 15 min idle."
Write-Host "  Ollama process stays running but uses minimal memory."
Write-Host ""
pause
