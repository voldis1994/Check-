# CHECK SYSTEM v2 — install (Windows)
# Usage: .\scripts\install.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "== CHECK SYSTEM v2 install ==" -ForegroundColor Cyan
Write-Host "Root: $Root"

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    throw "Python not found on PATH. Install Python 3.12+ and retry."
}

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.12+ required."
}

python -m pip install --upgrade pip
pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) {
    throw "pip install -e `".[dev]` failed."
}

$dirs = @(
    "runtime\bridge\market",
    "runtime\bridge\status",
    "runtime\bridge\commands",
    "runtime\bridge\acknowledgements",
    "runtime\bridge\archive",
    "runtime\state",
    "runtime\logs",
    "config\local"
)
foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Root $d) | Out-Null
}

$localConfig = Join-Path $Root "config\local\system.json"
$example = Join-Path $Root "config\system.example.json"
if (-not (Test-Path $localConfig)) {
    Copy-Item $example $localConfig
    Write-Host "Created config\local\system.json from example." -ForegroundColor Yellow
    Write-Host "Edit allowed_account_numbers before live start." -ForegroundColor Yellow
} else {
    Write-Host "Keeping existing config\local\system.json"
}

Write-Host "Install complete. Next: edit config, attach MT4 EA, then .\scripts\start_live.ps1" -ForegroundColor Green
