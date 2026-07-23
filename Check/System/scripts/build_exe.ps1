param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

Write-Host "Building CHECK_SYSTEM.exe …"
python -m pip install --upgrade pyinstaller | Out-Null
if (Test-Path (Join-Path $Root "build")) { Remove-Item -Recurse -Force (Join-Path $Root "build") }
$DistApp = Join-Path $Root "dist\CHECK_SYSTEM"
if (Test-Path $DistApp) { Remove-Item -Recurse -Force $DistApp }

python -m PyInstaller --noconfirm --clean (Join-Path $Root "CHECK_SYSTEM.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$CfgDir = Join-Path $DistApp "config"
New-Item -ItemType Directory -Force -Path $CfgDir | Out-Null
Copy-Item (Join-Path $Root "config\system.example.json") (Join-Path $CfgDir "system.example.json") -Force
if (Test-Path (Join-Path $Root "config\system.json")) {
  Copy-Item (Join-Path $Root "config\system.json") (Join-Path $CfgDir "system.json") -Force
}

Write-Host "DONE → $DistApp\CHECK_SYSTEM.exe"
