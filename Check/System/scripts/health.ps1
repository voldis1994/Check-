# CHECK SYSTEM v2 — health check
# Usage: .\scripts\health.ps1 [-Config path]
param(
    [string]$Config = "config\local\system.json",
    [int]$MaxAgeSec = 5
)
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$failed = 0

function Ok($msg) { Write-Host "OK   $msg" -ForegroundColor Green }
function Bad($msg) { Write-Host "FAIL $msg" -ForegroundColor Red; $script:failed++ }
function Info($msg) { Write-Host "INFO $msg" }

Write-Host "== health ==" -ForegroundColor Cyan

$configPath = Join-Path $Root $Config
if (-not (Test-Path $configPath)) {
    Bad "Config missing: $Config"
} else {
    python (Join-Path $Root "tools\validate_config.py") --config $configPath --allow-empty-accounts 2>$null
    if ($LASTEXITCODE -eq 0) {
        Ok "Config loads: $Config"
    } else {
        python (Join-Path $Root "tools\validate_config.py") --config $configPath
        if ($LASTEXITCODE -eq 0) { Ok "Config loads (live accounts set)" }
        else { Bad "Config validation failed" }
    }
}

$stopFile = Join-Path $Root "runtime\STOP_TRADING"
if (Test-Path $stopFile) {
    Bad "Kill switch ACTIVE (runtime\STOP_TRADING)"
} else {
    Ok "Kill switch clear"
}

function Report-Bridge($name, $dir) {
    $path = Join-Path $Root $dir
    if (-not (Test-Path $path)) {
        Bad "$name dir missing: $dir"
        return
    }
    $files = Get-ChildItem -Path $path -Filter *.json -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
    if (-not $files) {
        Bad "$name: no JSON files"
        return
    }
    $age = [int]((Get-Date) - $files[0].LastWriteTime).TotalSeconds
    Info "$name latest=$($files[0].Name) age=${age}s"
    if ($age -le $MaxAgeSec) { Ok "$name heartbeat age<=${MaxAgeSec}s" }
    else { Bad "$name stale (age=${age}s > ${MaxAgeSec}s)" }
}

Report-Bridge "market" "runtime\bridge\market"
Report-Bridge "status" "runtime\bridge\status"

$statePath = Join-Path $Root "runtime\state\instance.json"
if (Test-Path $statePath) {
    Ok "State file present: runtime\state\instance.json"
    python -c "import json,sys; p=json.load(open(r'$($statePath -replace '\\','/')',encoding='utf-8')); print('state revision',p.get('revision'),'pos', (p.get('position') or {}).get('state'),'reason',p.get('last_reason'))"
} else {
    Info "No instance state yet (engine not started or fresh install)"
}

python (Join-Path $Root "tools\inspect_bridge.py") --root $Root
if ($LASTEXITCODE -ne 0) { $failed++ }

if ($failed -gt 0) {
    Write-Host "Health FAILED ($failed)" -ForegroundColor Red
    exit 1
}
Write-Host "Health OK" -ForegroundColor Green
exit 0
