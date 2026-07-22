param(
  [string]$Config = "config\system.example.json",
  [switch]$SkipLint
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

$OldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($OldPythonPath)) { Join-Path $Root "src" } else { (Join-Path $Root "src") + ";" + $OldPythonPath }

try {
  python .\tools\validate_config.py --config $Config
  python -m pytest

  if (!$SkipLint) {
    python -m ruff check src tools
    python -m mypy src/checktrader
  }
} finally {
  $env:PYTHONPATH = $OldPythonPath
}
