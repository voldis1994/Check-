# CHECK SYSTEM v2 — run pytest suites
# Usage: .\scripts\run_tests.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$paths = @(
    "tests\unit",
    "tests\integration",
    "tests\protocol",
    "tests\strategy",
    "tests\risk",
    "tests\trailing",
    "tests\state",
    "tests\e2e"
)

Write-Host "== pytest v2 ==" -ForegroundColor Cyan
python -m pytest @paths -q --junitxml=pytest-results.xml
exit $LASTEXITCODE
