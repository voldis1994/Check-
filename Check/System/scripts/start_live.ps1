param(
  [string]$Config = "config\system.json",
  [switch]$ConfirmLive,
  [switch]$Once
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (!$ConfirmLive) {
  throw "Live mode requires -ConfirmLive. Confirm MT4 AutoTrading, DLL imports, bridge health, and live risk before starting."
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

if (!(Test-Path $Config)) {
  throw "Config not found: $Config"
}

$OldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($OldPythonPath)) { Join-Path $Root "src" } else { (Join-Path $Root "src") + ";" + $OldPythonPath }

try {
  python .\tools\sync_system_config.py --config $Config
  python .\tools\validate_config.py --config $Config --live

  $Args = @("-m", "checktrader", "--config", $Config, "--mode", "live")
  if ($Once) {
    $Args += "--once"
  }
  python @Args
} finally {
  $env:PYTHONPATH = $OldPythonPath
}
