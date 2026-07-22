param(
  [switch]$Install,
  [switch]$Dev
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

$RuntimeDirs = @(
  "runtime",
  "runtime\history",
  "runtime\bridge",
  "runtime\bridge\market",
  "runtime\bridge\status",
  "runtime\bridge\commands",
  "runtime\bridge\acknowledgements",
  "runtime\bridge\archive"
)

foreach ($Dir in $RuntimeDirs) {
  New-Item -ItemType Directory -Force -Path (Join-Path $Root $Dir) | Out-Null
}

$Config = Join-Path $Root "config\system.json"
$Example = Join-Path $Root "config\system.example.json"
if (!(Test-Path $Config) -and (Test-Path $Example)) {
  Copy-Item $Example $Config
  Write-Host "Created config\system.json from config\system.example.json"
}

$OldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($OldPythonPath)) { Join-Path $Root "src" } else { (Join-Path $Root "src") + ";" + $OldPythonPath }
try {
  python .\tools\sync_system_config.py --config $Config --example $Example
} finally {
  $env:PYTHONPATH = $OldPythonPath
}

if ($Install) {
  python -m pip install --upgrade pip
  if ($Dev) {
    python -m pip install -e ".[dev]"
  } else {
    python -m pip install -e .
  }
}

python .\tools\validate_config.py --config $Config
Write-Host "CHECK SYSTEM v3 setup complete."
