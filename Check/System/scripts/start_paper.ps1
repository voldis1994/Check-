param(
  [string]$Config = "config\system.json",
  [switch]$Once
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

if (!(Test-Path $Config)) {
  $Config = "config\system.example.json"
}

$OldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($OldPythonPath)) { Join-Path $Root "src" } else { (Join-Path $Root "src") + ";" + $OldPythonPath }

try {
  if ((Split-Path -Leaf $Config) -eq "system.json") {
    python .\tools\sync_system_config.py --config $Config
  }
  $Args = @("-m", "checktrader", "--config", $Config, "--mode", "paper")
  if ($Once) {
    $Args += "--once"
  }
  python @Args
} finally {
  $env:PYTHONPATH = $OldPythonPath
}
