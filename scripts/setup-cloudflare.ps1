# =============================================================================
# setup-cloudflare.ps1
# Set up Cloudflare Tunnel + .env for tradingbonushub.com
# Run once only with Administrator privileges
#
# How to run:
#   Right-click → "Run as Administrator"
#   or: PowerShell (Admin): .\scripts\setup-cloudflare.ps1
# =============================================================================

$ErrorActionPreference = "Stop"
$ProjectDir     = Split-Path -Parent $PSScriptRoot
$CloudflaredExe = Join-Path $ProjectDir "cloudflared.exe"
$ConfigFile     = Join-Path $ProjectDir "cloudflared.yml"
$EnvFile        = Join-Path $ProjectDir ".env"
$EnvExample     = Join-Path $ProjectDir ".env.example"
$TunnelName     = "tradingbonushub"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    [!!] $msg" -ForegroundColor Yellow }

# ── 1. Check / download cloudflared.exe ──────────────────────────────────────
Write-Step "Check cloudflared.exe"

if (-not (Test-Path $CloudflaredExe)) {
    Write-Warn "cloudflared.exe not found, downloading..."
    $url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    Invoke-WebRequest -Uri $url -OutFile $CloudflaredExe -UseBasicParsing
    Write-OK "Downloaded cloudflared.exe"
} else {
    Write-OK "cloudflared.exe already exists"
}

$version = & $CloudflaredExe version 2>&1
Write-OK "Version: $version"

# ── 2. Log in to Cloudflare ───────────────────────────────────────────────────
Write-Step "Log in to Cloudflare (will open browser)"

$credDir  = "$env:USERPROFILE\.cloudflared"
$certFile = "$credDir\cert.pem"

if (Test-Path $certFile) {
    Write-OK "Already logged in (cert.pem exists)"
} else {
    Write-Warn "Not logged in — opening browser..."
    & $CloudflaredExe tunnel login
    if (-not (Test-Path $certFile)) {
        Write-Host "Error: Login failed. Please re-run the script." -ForegroundColor Red
        exit 1
    }
    Write-OK "Login successful"
}

# ── 3. Create tunnel ──────────────────────────────────────────────────────────
Write-Step "Create Cloudflare Tunnel '$TunnelName'"

$existingTunnels = & $CloudflaredExe tunnel list 2>&1
if ($existingTunnels -match $TunnelName) {
    Write-OK "Tunnel '$TunnelName' already exists"
    $tunnelLine = ($existingTunnels -split "`n") | Where-Object { $_ -match $TunnelName } | Select-Object -First 1
    $TunnelId = ($tunnelLine -split "\s+")[0].Trim()
} else {
    $createOutput = & $CloudflaredExe tunnel create $TunnelName 2>&1
    Write-Host $createOutput
    if ($createOutput -match "with id ([a-f0-9\-]{36})") {
        $TunnelId = $Matches[1]
    } else {
        Start-Sleep -Seconds 2
        $listOutput = & $CloudflaredExe tunnel list 2>&1
        $tunnelLine = ($listOutput -split "`n") | Where-Object { $_ -match $TunnelName } | Select-Object -First 1
        $TunnelId = ($tunnelLine -split "\s+")[0].Trim()
    }
}

if (-not $TunnelId -or $TunnelId.Length -ne 36) {
    Write-Host "Error: Could not retrieve Tunnel ID." -ForegroundColor Red
    exit 1
}
Write-OK "Tunnel ID: $TunnelId"

# ── 4. Write cloudflared.yml ──────────────────────────────────────────────────
Write-Step "Write cloudflared.yml"

$credJsonPath = "$credDir\$TunnelId.json"
$configContent = @"
tunnel: $TunnelId
credentials-file: $credJsonPath

ingress:
  - hostname: tradingbonushub.com
    service: http://localhost:8000
  - hostname: www.tradingbonushub.com
    service: http://localhost:8000
  - hostname: admin.tradingbonushub.com
    service: http://localhost:8000
  - hostname: portal.tradingbonushub.com
    service: http://localhost:8000
  - service: http_status:404
"@

Set-Content -Path $ConfigFile -Value $configContent -Encoding UTF8
Write-OK "cloudflared.yml has been updated"

# ── 5. Route DNS for all subdomains ───────────────────────────────────────────
Write-Step "Route DNS (Cloudflare will auto-create CNAME records)"

$hostnames = @(
    "tradingbonushub.com",
    "www.tradingbonushub.com",
    "admin.tradingbonushub.com",
    "portal.tradingbonushub.com"
)

foreach ($hostname in $hostnames) {
    Write-Host "    Routing: $hostname" -NoNewline
    $result = & $CloudflaredExe tunnel route dns --overwrite-dns $TunnelName $hostname 2>&1
    if ($result -match "error|failed" -and $result -notmatch "already") {
        Write-Host " [WARN] $result" -ForegroundColor Yellow
    } else {
        Write-Host " [OK]" -ForegroundColor Green
    }
}

# ── 6. Create .env file ───────────────────────────────────────────────────────
Write-Step "Create .env file"

if (Test-Path $EnvFile) {
    Write-Warn ".env already exists — skipping (will not overwrite)"
} else {
    # Generate SECRET_KEY and FERNET_KEY
    $secretKey = -join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) })

    # FERNET_KEY must be base64url-encoded 32 bytes
    $fernetBytes = New-Object byte[] 32
    (New-Object System.Security.Cryptography.RNGCryptoServiceProvider).GetBytes($fernetBytes)
    $fernetKey = [Convert]::ToBase64String($fernetBytes)

    Write-Host ""
    Write-Host "  Enter SQL Server SA password" -ForegroundColor Yellow
    Write-Host "  (at least 8 chars, with uppercase, digits, special chars — e.g. MyPass@2025):" -ForegroundColor Yellow
    $dbPass = Read-Host "  DB_PASSWORD"

    $envContent = @"
SECRET_KEY=$secretKey
FERNET_KEY=$fernetKey
APP_ENV=production
DB_SERVER=sqlserver
DB_NAME=TradingBonusHub
DB_USER=sa
DB_PASSWORD=$dbPass
DB_POOL_SIZE=20
"@

    Set-Content -Path $EnvFile -Value $envContent -Encoding UTF8
    Write-OK ".env has been created"
}

# ── 7. Register Windows Service for cloudflared ──────────────────────────────
Write-Step "Register Windows Service for Cloudflare Tunnel"

$serviceName = "cloudflared"
$existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue

if ($existingService) {
    Write-OK "Service '$serviceName' already exists"
} else {
    & $CloudflaredExe service install 2>&1 | Out-Null
    Write-OK "Installed cloudflared service (auto-starts with Windows)"
}

# ── 8. Summary ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  SETUP COMPLETE!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Tunnel ID  : $TunnelId"
Write-Host "  Config     : $ConfigFile"
Write-Host "  Env file   : $EnvFile"
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor Cyan
Write-Host "  1. Review .env — fill in SMTP if needed"
Write-Host "  2. Run:  .\start.bat"
Write-Host "  3. Visit https://tradingbonushub.com"
Write-Host ""
