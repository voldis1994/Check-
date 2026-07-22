param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

$Config = Join-Path $Root "config\system.json"
$Example = Join-Path $Root "config\system.example.json"
if (!(Test-Path $Config) -and (Test-Path $Example)) {
  Copy-Item $Example $Config
  Write-Host "Created config\system.json from example."
}

$OldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($OldPythonPath)) { Join-Path $Root "src" } else { (Join-Path $Root "src") + ";" + $OldPythonPath }

try {
  python .\tools\sync_system_config.py --config $Config --example $Example
  python .\tools\dashboard.py
} finally {
  $env:PYTHONPATH = $OldPythonPath
}
