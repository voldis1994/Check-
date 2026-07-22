# CHECK SYSTEM v2 — start live (Windows)
# Mirrors docs/LIVE_OPERATION.md checklist.
# Usage: .\scripts\start_live.ps1 [-SkipBridgeWait] [-Config path]
param(
    [string]$Config = "config\local\system.json",
    [switch]$SkipBridgeWait,
    [int]$MaxBridgeAgeSec = 5,
    [int]$BridgeWaitSec = 60
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "== start_live checklist ==" -ForegroundColor Cyan

# 1. Resolve root (done)
Write-Host "[1] Root: $Root"

# 2. Ensure local config
$configPath = Join-Path $Root $Config
$example = Join-Path $Root "config\system.example.json"
if (-not (Test-Path $configPath)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $configPath) | Out-Null
    Copy-Item $example $configPath
    Write-Host "[2] Seeded $Config from example — edit accounts before trading." -ForegroundColor Yellow
} else {
    Write-Host "[2] Config present: $Config"
}

# 3. Validate config
Write-Host "[3] Validating config..."
python (Join-Path $Root "tools\validate_config.py") --config $configPath
if ($LASTEXITCODE -ne 0) {
    throw "Config validation failed. Fix config\local\system.json (set allowed_account_numbers)."
}

# 4. Kill switch clear
$stopFile = Join-Path $Root "runtime\STOP_TRADING"
if (Test-Path $stopFile) {
    throw "Kill switch active: runtime\STOP_TRADING exists. Remove it or run after intentional pause."
}
Write-Host "[4] Kill switch clear"

# 5. Runtime directories
$dirs = @(
    "runtime\bridge\market",
    "runtime\bridge\status",
    "runtime\bridge\commands",
    "runtime\bridge\acknowledgements",
    "runtime\bridge\archive",
    "runtime\state",
    "runtime\logs"
)
foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Root $d) | Out-Null
}
Write-Host "[5] Runtime directories ready"

# 6. Print allow-list (from validate already enforced non-empty)
Write-Host "[6] Account allow-list enforced by validate_config"

# 7. Bridge heartbeat
function Get-NewestJsonAgeSec([string]$dir) {
    $files = Get-ChildItem -Path $dir -Filter *.json -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
    if (-not $files) { return $null }
    return [int]((Get-Date) - $files[0].LastWriteTime).TotalSeconds
}

if (-not $SkipBridgeWait) {
    Write-Host "[7] Waiting for bridge market/status (max ${BridgeWaitSec}s, age<=${MaxBridgeAgeSec}s)..."
    $deadline = (Get-Date).AddSeconds($BridgeWaitSec)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        $mAge = Get-NewestJsonAgeSec (Join-Path $Root "runtime\bridge\market")
        $sAge = Get-NewestJsonAgeSec (Join-Path $Root "runtime\bridge\status")
        if ($null -ne $mAge -and $null -ne $sAge -and $mAge -le $MaxBridgeAgeSec -and $sAge -le $MaxBridgeAgeSec) {
            Write-Host "    market age=${mAge}s status age=${sAge}s"
            $ready = $true
            break
        }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) {
        throw "Bridge heartbeat not ready. Check EA, BridgeRootPath, DLL imports. Or -SkipBridgeWait."
    }
} else {
    Write-Host "[7] Skipping bridge wait (-SkipBridgeWait)"
}

# 8. Start engine
Write-Host "[8] Starting python -m checktrader ..." -ForegroundColor Green
python -m checktrader --config $configPath
