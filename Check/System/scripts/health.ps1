param(
  [string]$Bridge = "runtime\bridge",
  [string]$Audit = "runtime\audit.jsonl"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

Write-Host "CHECK SYSTEM v3 health"
Write-Host "Root: $Root"

$StopFile = Join-Path $Root "runtime\STOP_TRADING"
Write-Host ("STOP_TRADING: " + $(if (Test-Path $StopFile) { "PRESENT" } else { "absent" }))

$BridgePath = Join-Path $Root $Bridge
if (Test-Path $BridgePath) {
  Write-Host "Bridge: $BridgePath"
  foreach ($Sub in @("market", "status", "commands", "acknowledgements", "archive")) {
    $Dir = Join-Path $BridgePath $Sub
    if (Test-Path $Dir) {
      $Latest = Get-ChildItem $Dir -Filter "*.json" -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
      if ($Latest) {
        Write-Host "$Sub latest: $($Latest.Name) $($Latest.LastWriteTimeUtc.ToString("yyyy-MM-ddTHH:mm:ssZ"))"
      } else {
        Write-Host "$Sub latest: none"
      }
    } else {
      Write-Host "$Sub: missing"
    }
  }
} else {
  Write-Host "Bridge missing: $BridgePath"
}

$AuditPath = Join-Path $Root $Audit
if (Test-Path $AuditPath) {
  $Last = Get-Content $AuditPath -Tail 1
  Write-Host "Audit last:"
  Write-Host $Last
} else {
  Write-Host "Audit missing: $AuditPath"
}
