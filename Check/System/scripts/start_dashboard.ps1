param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

$Exe = Join-Path $Root "dist\CHECK_SYSTEM\CHECK_SYSTEM.exe"
if (Test-Path $Exe) {
  Start-Process $Exe
  return
}

$Config = Join-Path $Root "config\system.json"
$Example = Join-Path $Root "config\system.example.json"
if (!(Test-Path $Config) -and (Test-Path $Example)) {
  Copy-Item $Example $Config
  Write-Host "Created config\system.json from example."
}

$OldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($OldPythonPath)) {
  ((Join-Path $Root "src") + ";" + (Join-Path $Root "tools"))
} else {
  ((Join-Path $Root "src") + ";" + (Join-Path $Root "tools") + ";" + $OldPythonPath)
}

try {
  python .\tools\sync_system_config.py --config $Config --example $Example
  python .\tools\check_app.py
} finally {
  $env:PYTHONPATH = $OldPythonPath
}
