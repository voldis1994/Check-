param(
  [string]$RuntimeDir = "runtime"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RuntimePath = Join-Path $Root $RuntimeDir
New-Item -ItemType Directory -Force -Path $RuntimePath | Out-Null

$StopFile = Join-Path $RuntimePath "STOP_TRADING"
$Timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
Set-Content -Path $StopFile -Value "STOP_TRADING created_at_utc=$Timestamp" -Encoding ASCII
Write-Host "Created $StopFile"
Write-Host "For live trading, also disable AutoTrading in MT4."
