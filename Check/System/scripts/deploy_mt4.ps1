param(
  [string]$TerminalRoot = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ExpertsSource = Join-Path $Root "mt4\Experts\CHECK_SYSTEM_V3.mq4"
$IncludesSource = Join-Path $Root "mt4\Include\CHECK_V3_*.mqh"

if (!(Test-Path $ExpertsSource)) {
  throw "Missing EA source: $ExpertsSource"
}

if ($TerminalRoot -eq "") {
  if ([string]::IsNullOrWhiteSpace($env:APPDATA)) {
    throw "APPDATA is not set. Provide -TerminalRoot."
  }
  $TerminalRoot = Join-Path $env:APPDATA "MetaQuotes\Terminal"
}

if (!(Test-Path $TerminalRoot)) {
  throw "Terminal root not found: $TerminalRoot"
}

$Terminals = Get-ChildItem -Path $TerminalRoot -Directory
if ($Terminals.Count -eq 0) {
  throw "No MT4 terminal directories found under $TerminalRoot"
}

foreach ($Terminal in $Terminals) {
  $Mql4 = Join-Path $Terminal.FullName "MQL4"
  if (!(Test-Path $Mql4)) {
    continue
  }

  $ExpertsDest = Join-Path $Mql4 "Experts"
  $IncludesDest = Join-Path $Mql4 "Include"
  New-Item -ItemType Directory -Force -Path $ExpertsDest | Out-Null
  New-Item -ItemType Directory -Force -Path $IncludesDest | Out-Null

  Copy-Item $ExpertsSource $ExpertsDest -Force
  Copy-Item $IncludesSource $IncludesDest -Force
  Write-Host "Deployed CHECK_SYSTEM_V3 to $Mql4"
}
